from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from camomilla.models import Draft, Page
from .utils.api import login_superuser


@pytest.mark.django_db(transaction=True, reset_sequences=True)
class PagePreviewTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = APIClient()
        token = login_superuser()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token)

    def _create_published_page(self, title="live title"):
        """Create a page and force-publish it so it's unambiguously live.

        We stamp ``published_at`` in the past via a direct DB update — the
        same effect that ``publish()`` would have, without going through
        the serializer machinery.
        """
        resp = self.client.post(
            "/api/camomilla/pages/",
            {"translations": {"en": {"title": title}}},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        page_id = resp.json()["id"]
        Page.objects.filter(pk=page_id).update(published_at=timezone.now())
        return page_id

    # ------------------------------------------------------------------
    # Draft creation and isolation from the live row
    # ------------------------------------------------------------------

    def test_draft_does_not_touch_live(self):
        page_id = self._create_published_page("live title")
        resp = self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "draft title"}}},
            format="json",
        )
        assert resp.status_code == 200
        page = Page.objects.get(pk=page_id)
        # Draft row exists in EN
        assert Draft.objects.for_(page, language="en").exists()
        # Live row untouched
        assert page.title_en == "live title"

    def test_preview_endpoint_overlays_draft(self):
        page_id = self._create_published_page("live title")
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "draft title"}}},
            format="json",
        )
        resp = self.client.get(f"/api/camomilla/pages/{page_id}/preview/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_draft"] is True

    def test_preview_overlay_preserves_other_language_translations(self):
        """The EN preview must NOT erase IT live content from the response.

        Each language's Draft only carries its own ``translations[<lang>]``
        slice. A naive ``overlay.update(draft)`` would replace the response's
        full ``{en, it}`` translations map with the draft's one-language map.
        Merge-by-language is the contract pinned here.
        """
        page_id = self._create_published_page("live en")
        Page.objects.filter(pk=page_id).update(
            title_it="live it",
            published_at_it=timezone.now(),
        )
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/?language=en",
            {"translations": {"en": {"title": "draft en"}}},
            format="json",
        )
        resp = self.client.get(f"/api/camomilla/pages/{page_id}/preview/?language=en")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_draft"] is True
        assert data["translations"]["en"]["title"] == "draft en"
        assert data["translations"]["it"]["title"] == "live it"

    def test_publish_applies_draft_and_clears_it(self):
        page_id = self._create_published_page("live title")
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "draft title"}}},
            format="json",
        )
        resp = self.client.post(f"/api/camomilla/pages/{page_id}/publish/")
        assert resp.status_code == 200
        page = Page.objects.get(pk=page_id)
        assert page.status == "PUB"
        assert page.is_public is True
        # Draft row deleted by publish()
        assert not Draft.objects.for_(page).exists()
        assert page.title_en == "draft title"

    def test_discard_draft(self):
        page_id = self._create_published_page()
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "other"}}},
            format="json",
        )
        resp = self.client.post(f"/api/camomilla/pages/{page_id}/discard-draft/")
        assert resp.status_code == 200
        page = Page.objects.get(pk=page_id)
        assert not Draft.objects.for_(page, language="en").exists()

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def test_schedule_first_publish_makes_published_at_future(self):
        """Never-public + ``schedule(when)`` → ``published_at = when``.

        No Draft is required for the first-appearance schedule: the live
        row IS the content that will go public at ``when``.
        """
        resp = self.client.post(
            "/api/camomilla/pages/",
            {"translations": {"en": {"title": "unpublished"}}},
            format="json",
        )
        assert resp.status_code == 201
        page_id = resp.json()["id"]
        future = (timezone.now() + timedelta(days=1)).isoformat()
        resp = self.client.post(
            f"/api/camomilla/pages/{page_id}/schedule/",
            {"publish_at": future},
            format="json",
        )
        assert resp.status_code == 200
        page = Page.objects.get(pk=page_id)
        assert page.published_at is not None
        assert page.published_at > timezone.now()
        assert page.is_public is False
        assert page.status == "PLA"

    def test_schedule_swap_keeps_page_public_until_date(self):
        """Already-public + draft + ``schedule(when)`` → Draft.scheduled_for.

        Public content stays visible; the Draft will swap in at ``when``.
        """
        page_id = self._create_published_page("live title")
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "swap title"}}},
            format="json",
        )
        future = (timezone.now() + timedelta(days=1)).isoformat()
        resp = self.client.post(
            f"/api/camomilla/pages/{page_id}/schedule/",
            {"publish_at": future},
            format="json",
        )
        assert resp.status_code == 200
        page = Page.objects.get(pk=page_id)
        assert page.is_public is True
        assert page.published_at <= timezone.now()
        assert page.status == "PUB"
        assert page.title_en == "live title"

        draft = Draft.objects.for_(page, language="en").first()
        assert draft is not None
        assert draft.scheduled_for is not None
        assert draft.scheduled_for > timezone.now()

        # Public route still serves OLD content.
        anon = APIClient()
        resp = anon.get(f"/api/camomilla/pages-router{page.permalink}/")
        assert resp.status_code == 200
        body = resp.json()
        translations = body.get("translations") or {}
        en = translations.get("en") or {}
        assert en.get("title") != "swap title"

    def test_scheduled_swap_materialises_at_read_time_when_due(self):
        page_id = self._create_published_page("swap-source-page")
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "swap title"}}},
            format="json",
        )
        page = Page.objects.get(pk=page_id)
        # Push the Draft's scheduled_for into the past so it's due.
        Draft.objects.for_(page, language="en").update(
            scheduled_for=timezone.now() - timedelta(minutes=1)
        )
        anon = APIClient()
        resp = anon.get(f"/api/camomilla/pages-router{page.permalink}/?cache_bust=1")
        assert resp.status_code == 200
        page.refresh_from_db()
        assert page.title_en == "swap title"
        assert not Draft.objects.for_(page).exists()
        assert page.is_public is True

    def test_scheduled_publish_command_promotes_first_publish(self):
        """Cron applies a Draft whose ``scheduled_for`` has passed and
        promotes a never-public page into the public state.

        The page itself was never publicly visible; the Draft carries both
        the content snapshot and the scheduled_for stamp. After cron runs,
        the page becomes public with the Draft's content applied.
        """
        resp = self.client.post(
            "/api/camomilla/pages/",
            {"translations": {"en": {"title": "first publish"}}},
            format="json",
        )
        page_id = resp.json()["id"]
        page = Page.objects.get(pk=page_id)
        # Stage a draft with a scheduled_for in the past.
        page.save_draft(
            {"translations": {"en": {"title": "first publish"}}},
            scheduled_for=timezone.now() - timedelta(minutes=1),
        )

        call_command("camomilla_publish_scheduled")

        page.refresh_from_db()
        assert page.status == "PUB"
        assert page.is_public is True
        assert not Draft.objects.for_(page).exists()

    def test_scheduled_publish_command_materialises_swap(self):
        page_id = self._create_published_page("live title")
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "swap title"}}},
            format="json",
        )
        page = Page.objects.get(pk=page_id)
        Draft.objects.for_(page, language="en").update(
            scheduled_for=timezone.now() - timedelta(minutes=1)
        )

        call_command("camomilla_publish_scheduled")

        page.refresh_from_db()
        assert page.title_en == "swap title"
        assert not Draft.objects.for_(page).exists()
        assert page.status == "PUB"

    # ------------------------------------------------------------------
    # Revisions / revert
    # ------------------------------------------------------------------

    def test_revisions_and_revert_roundtrip(self):
        page_id = self._create_published_page("v1")
        self.client.post(f"/api/camomilla/pages/{page_id}/publish/")
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "v2"}}},
            format="json",
        )
        self.client.post(f"/api/camomilla/pages/{page_id}/publish/")

        resp = self.client.get(f"/api/camomilla/pages/{page_id}/revisions/")
        assert resp.status_code == 200
        revs = resp.json()
        assert len(revs) >= 2
        v1_id = revs[-1]["id"]

        resp = self.client.post(f"/api/camomilla/pages/{page_id}/revert/{v1_id}/")
        assert resp.status_code == 200, resp.content
        page = Page.objects.get(pk=page_id)
        assert page.title_en == "v1"

    # ------------------------------------------------------------------
    # Public-route safety
    # ------------------------------------------------------------------

    def test_public_router_never_exposes_draft(self):
        page_id = self._create_published_page("router-leak-page")
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "secret draft"}}},
            format="json",
        )
        page = Page.objects.get(pk=page_id)
        anon = APIClient()
        resp = anon.get(f"/api/camomilla/pages-router{page.permalink}/?cb=1")
        assert resp.status_code == 200
        data = resp.json()
        assert "draft_data" not in data
        assert "has_draft" not in data or data["has_draft"] is False

    def test_preview_endpoint_requires_authentication(self):
        page_id = self._create_published_page("auth-gate-page")
        anon = APIClient()
        resp = anon.get(f"/api/camomilla/pages/{page_id}/preview/")
        assert resp.status_code in (401, 403), resp.status_code

    def test_preview_query_string_on_public_router_is_inert(self):
        page_id = self._create_published_page("inert-preview-page")
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "draft would be here"}}},
            format="json",
        )
        page = Page.objects.get(pk=page_id)
        anon = APIClient()
        resp = anon.get(f"/api/camomilla/pages-router{page.permalink}/?preview=true")
        assert resp.status_code == 200
        data = resp.json()
        assert "draft_data" not in data

    def test_lazy_materialisation_on_first_html_visit(self):
        """First HTML visitor after the Draft's ``scheduled_for`` triggers
        publish — no cron round-trip required for visited pages."""
        page_id = self._create_published_page("live title")
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "new live title"}}},
            format="json",
        )
        page = Page.objects.get(pk=page_id)
        Draft.objects.for_(page, language="en").update(
            scheduled_for=timezone.now() - timedelta(minutes=1)
        )

        anon = APIClient()
        resp = anon.get(page.permalink + "/?cb=1", follow=True)
        assert resp.status_code == 200, resp.content

        page.refresh_from_db()
        assert page.title_en == "new live title"
        assert not Draft.objects.for_(page).exists()
        assert page.is_public is True

    def test_publish_if_due_is_noop_when_not_due(self):
        page_id = self._create_published_page("stable")
        page = Page.objects.get(pk=page_id)
        assert page.publish_if_due() is False
        page.refresh_from_db()
        assert page.title_en == "stable"

    # ------------------------------------------------------------------
    # Soft-delete
    # ------------------------------------------------------------------

    def test_trash_and_restore(self):
        page_id = self._create_published_page("trashable")
        page = Page.objects.get(pk=page_id)
        assert page.is_public is True
        page.trash()
        page.refresh_from_db()
        assert page.deleted_at is not None
        assert page.is_public is False
        assert page.status == "TRS"
        page.restore()
        page.refresh_from_db()
        assert page.deleted_at is None
        assert page.is_public is True

    # ------------------------------------------------------------------
    # Lifecycle contract: Python property ↔ SQL annotation
    # ------------------------------------------------------------------

    def test_lifecycle_property_matches_db_layer(self):
        """The Python-side ``status`` / ``is_public`` / ``overlay_due``
        properties must agree with the DB layer (``with_lifecycle()``
        annotation, ``.public()`` / ``.due_for_publish()`` filter helpers)
        across every lifecycle state.

        Two implementations of the same rule (Python + SQL) coexist
        because they run on different substrates; this test pins the
        equivalence so future drift breaks CI.
        """
        from django.utils.translation.trans_real import activate

        now = timezone.now()
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)

        scenarios = [
            ("never_published_no_draft", {}, None),
            ("never_published_with_draft", {}, {"draft": True, "scheduled_for": None}),
            ("published_long_ago", {"published_at": past}, None),
            ("scheduled_first_publish", {"published_at": future}, None),
            (
                "live_with_pending_draft",
                {"published_at": past},
                {"draft": True, "scheduled_for": None},
            ),
            (
                "live_with_scheduled_swap",
                {"published_at": past},
                {"draft": True, "scheduled_for": future},
            ),
            (
                "live_with_overlay_due",
                {"published_at": past},
                {"draft": True, "scheduled_for": past},
            ),
            (
                "trashed_after_being_published",
                {"published_at": past, "deleted_at": now},
                None,
            ),
            ("trashed_never_published", {"deleted_at": now}, None),
        ]

        for lang in ("en", "it"):
            activate(lang)
            for label, fields, draft_spec in scenarios:
                page = Page.objects.create()
                for f, v in fields.items():
                    setattr(page, f, v)
                page.save()
                pk = page.pk
                if draft_spec:
                    page.save_draft(
                        {"x": 1}, scheduled_for=draft_spec.get("scheduled_for")
                    )

                # status: property vs computed_status annotation.
                row = (
                    Page.objects.with_lifecycle()
                    .values("computed_status")
                    .get(pk=pk)
                )
                assert row["computed_status"] == page.status, (
                    f"[{lang}/{label}] status mismatch: "
                    f"annotation={row['computed_status']!r} "
                    f"property={page.status!r}"
                )

                # is_public: property vs .public() filter helper
                sql_public = Page.objects.public().filter(pk=pk).exists()
                assert sql_public == page.is_public, (
                    f"[{lang}/{label}] is_public mismatch: "
                    f".public()={sql_public!r} property={page.is_public!r}"
                )

                # overlay_due: property vs .due_for_publish() filter helper
                sql_due = Page.objects.due_for_publish().filter(pk=pk).exists()
                assert sql_due == page.overlay_due, (
                    f"[{lang}/{label}] overlay_due mismatch: "
                    f".due_for_publish()={sql_due!r} "
                    f"property={page.overlay_due!r}"
                )

                page.delete()

    # ------------------------------------------------------------------
    # Per-language draft isolation (Draft row per language)
    # ------------------------------------------------------------------

    def test_full_bundle_draft_stays_in_active_language(self):
        """Backoffice forms commonly PATCH the full ``translations`` bundle.

        The Draft row's ``language`` column is the canonical scoping: an
        EN draft holds the whole bundle but publishing EN only applies
        EN's slice (the serializer chain handles the rest by ignoring
        irrelevant translation entries).
        """
        page_id = self._create_published_page("live en title")
        Page.objects.filter(pk=page_id).update(
            title_it="live it title",
            published_at_it=timezone.now(),
        )

        resp = self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/?language=en",
            {
                "translations": {
                    "en": {"title": "draft en"},
                    "it": {"title": "draft it"},
                }
            },
            format="json",
        )
        assert resp.status_code == 200, resp.content
        page = Page.objects.get(pk=page_id)
        # The EN Draft exists; the IT Draft does not.
        assert Draft.objects.for_(page, language="en").exists()
        assert not Draft.objects.for_(page, language="it").exists()

    def test_drafts_are_isolated_per_language(self):
        """A draft saved in EN must not surface as a draft in IT, and
        publishing EN must not consume IT's pending draft.
        """
        page_id = self._create_published_page("live en title")
        Page.objects.filter(pk=page_id).update(
            title_it="live it title",
            published_at_it=timezone.now(),
        )

        resp = self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/?language=en",
            {"translations": {"en": {"title": "draft en title"}}},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        page = Page.objects.get(pk=page_id)
        assert Draft.objects.for_(page, language="en").exists()
        assert not Draft.objects.for_(page, language="it").exists()

        resp = self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/?language=it",
            {"translations": {"it": {"title": "draft it title"}}},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        page = Page.objects.get(pk=page_id)
        assert Draft.objects.for_(page, language="en").exists()
        assert Draft.objects.for_(page, language="it").exists()

        from django.utils.translation import override

        with override("en"):
            page.publish()
        page.refresh_from_db()
        # EN Draft consumed, IT Draft preserved.
        assert not Draft.objects.for_(page, language="en").exists()
        assert Draft.objects.for_(page, language="it").exists()
        assert page.title_en == "draft en title"

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def test_auto_created_homepage_is_publicly_published(self):
        page, created = Page.get_or_create_homepage()
        assert created is True
        from camomilla.utils import get_nofallbacks

        for lang in ("en", "it"):
            stamp = get_nofallbacks(page, "published_at", language=lang)
            assert stamp is not None, f"published_at_{lang} not stamped"
        assert page.is_public is True
        assert Page.objects.public().filter(pk=page.pk).exists()

    def test_queryset_filter_helpers(self):
        live_id = self._create_published_page("live one")
        Page.objects.create()  # never-published draft
        scheduled = Page.objects.create(
            published_at=timezone.now() + timedelta(hours=1),
        )

        assert Page.objects.public().filter(pk=live_id).exists()
        assert not Page.objects.public().filter(pk=scheduled.pk).exists()
        assert Page.objects.scheduled().filter(pk=scheduled.pk).exists()
        assert Page.objects.first_publish_pending().filter(pk=scheduled.pk).exists()
        assert Page.objects.alive().count() == 3

        Page.objects.filter(pk=live_id).update(deleted_at=timezone.now())
        assert Page.objects.alive().count() == 2
        assert Page.objects.trashed().filter(pk=live_id).exists()

    def test_filter_by_derived_status(self):
        """``.filter(status=...)`` / ``.filter(is_public=...)`` work again
        even though ``status`` is a derived property, not a column.

        The manager rewrites the derived lookups into timestamp conditions
        (see ``PageQuerySet._filter_or_exclude``), so upgrading code that
        used the old ``status`` column keeps working without a data change.
        """
        live = self._create_published_page("live")
        draft = Page.objects.create()  # never published → DRF
        planned = Page.objects.create(  # future publish → PLA
            published_at=timezone.now() + timedelta(hours=1),
        )
        trashed = self._create_published_page("trashed")
        Page.objects.filter(pk=trashed).update(deleted_at=timezone.now())  # → TRS

        def ids(qs):
            return set(qs.values_list("pk", flat=True))

        all_ids = ids(Page.objects.all())

        # filter(status=...) mirrors the dedicated helper querysets.
        assert ids(Page.objects.filter(status="PUB")) == ids(Page.objects.public())
        assert ids(Page.objects.filter(status="TRS")) == ids(Page.objects.trashed())
        assert ids(Page.objects.filter(status="PLA")) == ids(
            Page.objects.first_publish_pending()
        )
        assert draft.pk in ids(Page.objects.filter(status="DRF"))
        assert planned.pk in ids(Page.objects.filter(status="PLA"))

        # The four labels partition every page exactly once.
        partition = (
            ids(Page.objects.filter(status="PUB"))
            | ids(Page.objects.filter(status="DRF"))
            | ids(Page.objects.filter(status="PLA"))
            | ids(Page.objects.filter(status="TRS"))
        )
        assert partition == all_ids
        assert (
            sum(Page.objects.filter(status=s).count() for s in ("PUB", "DRF", "PLA", "TRS"))
            == Page.objects.count()
        )

        # status__in unions; exclude negates.
        assert ids(Page.objects.filter(status__in=["PUB", "TRS"])) == (
            ids(Page.objects.filter(status="PUB"))
            | ids(Page.objects.filter(status="TRS"))
        )
        assert ids(Page.objects.exclude(status="TRS")) == (
            all_ids - ids(Page.objects.filter(status="TRS"))
        )

        # is_public mirrors .public(); False is its complement.
        assert ids(Page.objects.filter(is_public=True)) == ids(Page.objects.public())
        assert ids(Page.objects.filter(is_public=False)) == (
            all_ids - ids(Page.objects.public())
        )

        # The rewrite doesn't annotate on fetch — the property still agrees,
        # and plain .all()/instantiation is unaffected.
        assert all(p.status == "PUB" for p in Page.objects.filter(status="PUB"))
        assert Page.objects.all().count() == Page.objects.count()
        assert Page.objects.get(pk=live).status == "PUB"

        # An unknown label is a loud error, not a silent empty queryset.
        with self.assertRaises(ValueError):
            list(Page.objects.filter(status="NOPE"))

    # ------------------------------------------------------------------
    # Public route lifecycle gating — nothing non-public must leak
    # ------------------------------------------------------------------
    #
    # The two public surfaces (HTML render in ``dynamic_pages_urls.fetch``
    # and JSON router in ``pages_router``) must both 404 trashed, draft,
    # and future-scheduled rows. Lazy materialisation of a due Draft is
    # the only path that's allowed to flip a non-public row to public on
    # the way in.

    def test_pages_router_404s_trashed_page(self):
        page_id = self._create_published_page("about-to-trash")
        Page.objects.filter(pk=page_id).update(deleted_at=timezone.now())
        page = Page.objects.get(pk=page_id)
        anon = APIClient()
        resp = anon.get(f"/api/camomilla/pages-router{page.permalink}/")
        assert resp.status_code == 404

    def test_pages_router_404s_never_published_page(self):
        resp = self.client.post(
            "/api/camomilla/pages/",
            {"translations": {"en": {"title": "never-public"}}},
            format="json",
        )
        page = Page.objects.get(pk=resp.json()["id"])
        anon = APIClient()
        resp = anon.get(f"/api/camomilla/pages-router{page.permalink}/")
        assert resp.status_code == 404

    def test_pages_router_404s_scheduled_first_publish(self):
        resp = self.client.post(
            "/api/camomilla/pages/",
            {"translations": {"en": {"title": "scheduled-page"}}},
            format="json",
        )
        page_id = resp.json()["id"]
        Page.objects.filter(pk=page_id).update(
            published_at=timezone.now() + timedelta(hours=1),
        )
        page = Page.objects.get(pk=page_id)
        anon = APIClient()
        resp = anon.get(f"/api/camomilla/pages-router{page.permalink}/")
        assert resp.status_code == 404

    def test_pages_router_promotes_never_public_with_due_draft(self):
        """Lazy first-publish: page never publicly visible, Draft with a
        past ``scheduled_for``. The first public read must apply the
        Draft, flip the page to public, and serve it 200."""
        resp = self.client.post(
            "/api/camomilla/pages/",
            {"translations": {"en": {"title": "lazy-publish"}}},
            format="json",
        )
        page_id = resp.json()["id"]
        page = Page.objects.get(pk=page_id)
        page.save_draft(
            {"translations": {"en": {"title": "lazy-publish"}}},
            scheduled_for=timezone.now() - timedelta(minutes=1),
        )
        anon = APIClient()
        resp = anon.get(f"/api/camomilla/pages-router{page.permalink}/")
        assert resp.status_code == 200
        page.refresh_from_db()
        assert page.is_public is True
        assert not Draft.objects.for_(page).exists()

    def test_fetch_404s_trashed_page_via_html_route(self):
        page_id = self._create_published_page("html-trashable")
        Page.objects.filter(pk=page_id).update(deleted_at=timezone.now())
        page = Page.objects.get(pk=page_id)
        from django.test import Client

        anon = Client()
        # ``follow=True`` resolves the APPEND_SLASH 302 so the assertion
        # sees the final status from the ``fetch`` view, not the redirect.
        resp = anon.get(page.permalink, follow=True)
        assert resp.status_code == 404

    def test_fetch_404s_trashed_homepage(self):
        """An existing homepage that was later trashed must not be
        re-served via ``/``. The auto-create branch only kicks in when
        the homepage doesn't exist at all."""
        homepage, _ = Page.get_or_create_homepage()
        Page.objects.filter(pk=homepage.pk).update(deleted_at=timezone.now())
        from django.test import Client

        anon = Client()
        resp = anon.get("/")
        assert resp.status_code == 404

    # ------------------------------------------------------------------
    # pages-router-preview — single-shot authenticated preview by permalink
    # ------------------------------------------------------------------
    #
    # Designed for external rendering frontends (e.g. the astro integration)
    # that need to resolve a preview by URL in one round-trip instead of
    # listing pages + fetching detail. Same response shape as
    # ``pages_router``, but auth-required, bypasses ``is_public``, overlays
    # the active-language Draft, and does NOT call ``publish_if_due``.

    def test_pages_router_preview_requires_authentication(self):
        page_id = self._create_published_page("preview-auth")
        page = Page.objects.get(pk=page_id)
        anon = APIClient()
        resp = anon.get(f"/api/camomilla/pages-router-preview{page.permalink}/")
        assert resp.status_code in (401, 403)

    def test_pages_router_preview_returns_trashed_page(self):
        """Trashed rows 404 on the public router but ARE returned here so
        editors can recover them."""
        page_id = self._create_published_page("trash-preview")
        Page.objects.filter(pk=page_id).update(deleted_at=timezone.now())
        page = Page.objects.get(pk=page_id)
        resp = self.client.get(
            f"/api/camomilla/pages-router-preview{page.permalink}/"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "TRS"

    def test_pages_router_preview_returns_never_published_page(self):
        resp = self.client.post(
            "/api/camomilla/pages/",
            {"translations": {"en": {"title": "never-public-preview"}}},
            format="json",
        )
        page = Page.objects.get(pk=resp.json()["id"])
        resp = self.client.get(
            f"/api/camomilla/pages-router-preview{page.permalink}/"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "DRF"

    def test_pages_router_preview_overlays_active_language_draft(self):
        page_id = self._create_published_page("live-with-overlay")
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "drafted title"}}},
            format="json",
        )
        page = Page.objects.get(pk=page_id)
        resp = self.client.get(
            f"/api/camomilla/pages-router-preview{page.permalink}/"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("has_draft") is True
        translations = body.get("translations") or {}
        assert (translations.get("en") or {}).get("title") == "drafted title"

    def test_pages_router_preview_does_not_consume_due_draft(self):
        """``publish_if_due`` would apply + delete a due Draft as a side
        effect. The preview endpoint must NOT trigger that — the editor
        is looking at the pending state, not asking to materialise it."""
        page_id = self._create_published_page("due-preview")
        page = Page.objects.get(pk=page_id)
        page.save_draft(
            {"translations": {"en": {"title": "due title"}}},
            scheduled_for=timezone.now() - timedelta(minutes=1),
        )
        resp = self.client.get(
            f"/api/camomilla/pages-router-preview{page.permalink}/"
        )
        assert resp.status_code == 200
        # The Draft must still be on disk after the preview call.
        assert Draft.objects.for_(page, language="en").exists()

    # ------------------------------------------------------------------
    # Canonical-URL trailing-slash handling
    # ------------------------------------------------------------------
    #
    # ``UrlNode.permalink`` is stored without a trailing slash (homepage
    # excepted). The HTML route's canonical form follows Django's
    # ``APPEND_SLASH`` setting (with-slash by default). The API must
    # honor the same canonical so an external renderer doesn't end up
    # with two valid URLs for the same content — when the visitor asks
    # for the non-canonical form, the API returns a 301 redirect
    # descriptor in the response body, the same shape ``UrlRedirect``
    # matches already emit.

    def test_pages_router_serves_with_slash_when_append_slash_is_true(self):
        # APPEND_SLASH defaults to True. The canonical for /about is /about/.
        self._create_published_page("trailing-slash")
        Page.objects.filter(title="trailing-slash").update(published_at=timezone.now())
        # Pin a stable permalink so the test asserts on a known URL.
        page = Page.objects.get(title="trailing-slash")
        from camomilla.utils import set_nofallbacks
        for lang in ("en", "it"):
            set_nofallbacks(page, "autopermalink", False, language=lang)
            set_nofallbacks(page, "permalink", "/canonical-test", language=lang)
        page.save()

        anon = APIClient()
        # With-slash form: served 200 directly.
        resp = anon.get("/api/camomilla/pages-router/canonical-test/")
        assert resp.status_code == 200, resp.content

    def test_pages_router_redirects_without_slash_to_with_slash(self):
        page_id = self._create_published_page("trailing-redirect")
        page = Page.objects.get(pk=page_id)
        from camomilla.utils import set_nofallbacks
        for lang in ("en", "it"):
            set_nofallbacks(page, "autopermalink", False, language=lang)
            set_nofallbacks(page, "permalink", "/redirect-test", language=lang)
        page.save()

        anon = APIClient()
        # No-slash request → API returns the redirect descriptor.
        resp = anon.get("/api/camomilla/pages-router/redirect-test")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body.get("status") == 301
        assert body.get("redirect", "").endswith("/redirect-test/")

    def test_pages_router_homepage_never_redirects(self):
        # The homepage permalink is ``/`` — adding/removing a trailing
        # slash here would produce nonsense. Make sure the canonical-form
        # comparison treats ``/`` as a fixed point.
        Page.get_or_create_homepage()
        anon = APIClient()
        resp = anon.get("/api/camomilla/pages-router/")
        assert resp.status_code == 200
        body = resp.json()
        # Not a redirect descriptor — actual page response.
        assert "redirect" not in body or body.get("status") != 301

    def test_pages_router_preview_redirects_too(self):
        page_id = self._create_published_page("preview-redirect")
        page = Page.objects.get(pk=page_id)
        from camomilla.utils import set_nofallbacks
        for lang in ("en", "it"):
            set_nofallbacks(page, "autopermalink", False, language=lang)
            set_nofallbacks(page, "permalink", "/preview-redirect-test", language=lang)
        page.save()

        # Authenticated, no-slash request → 301 descriptor (same as the
        # public router so the editor preview URL canonical matches live).
        resp = self.client.get("/api/camomilla/pages-router-preview/preview-redirect-test")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body.get("status") == 301
        assert body.get("redirect", "").endswith("/preview-redirect-test/")

    def test_pages_router_redirects_bare_language_prefix(self):
        """A bare ``/it`` (no trailing slash) should redirect to ``/it/``.

        Without the bare-lang-prefix handling in ``url_lang_decompose``,
        ``/it`` falls through as a regular permalink lookup and 404s,
        which is hostile UX (especially when external links drop the
        trailing slash). The redirect lets the visitor land on the
        canonical italian-homepage URL.
        """
        Page.get_or_create_homepage()
        anon = APIClient()
        # ``/it/`` (italian homepage) serves directly.
        resp = anon.get("/api/camomilla/pages-router/it/")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert "redirect" not in body or body.get("status") != 301
        # ``/it`` (no slash) gets a 301 descriptor.
        resp = anon.get("/api/camomilla/pages-router/it")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body.get("status") == 301
        assert body.get("redirect", "").endswith("/it/")

    def test_pages_router_honors_append_slash_false(self):
        # When APPEND_SLASH is False, canonical is no-slash. With-slash
        # requests then get redirected to the no-slash form.
        from django.test import override_settings

        page_id = self._create_published_page("append-slash-off")
        page = Page.objects.get(pk=page_id)
        from camomilla.utils import set_nofallbacks
        for lang in ("en", "it"):
            set_nofallbacks(page, "autopermalink", False, language=lang)
            set_nofallbacks(page, "permalink", "/no-slash-canonical", language=lang)
        page.save()

        anon = APIClient()
        with override_settings(APPEND_SLASH=False):
            # No-slash served 200
            resp = anon.get("/api/camomilla/pages-router/no-slash-canonical")
            assert resp.status_code == 200
            # With-slash redirected to no-slash
            resp = anon.get("/api/camomilla/pages-router/no-slash-canonical/")
            assert resp.status_code == 200
            body = resp.json()
            assert body.get("status") == 301
            assert body.get("redirect", "").rstrip("/").endswith("/no-slash-canonical")
