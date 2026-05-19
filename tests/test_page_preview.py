from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from camomilla.models import Page
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

        ``status`` is a computed property now, so we mark a page public by
        stamping ``published_at`` in the past via a direct DB update — the
        same effect that ``publish()`` would have, without going through the
        serializer machinery.
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

    def test_draft_does_not_touch_live(self):
        page_id = self._create_published_page("live title")
        resp = self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "draft title"}}},
            format="json",
        )
        assert resp.status_code == 200
        page = Page.objects.get(pk=page_id)
        assert page.has_draft is True
        assert page.draft_data != {}
        # live field untouched
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

        ``draft_data`` is per-language and the view trims the body to the
        active language at save time, so the stored draft only carries
        ``translations[<active>]``. A naive ``overlay.update(draft)`` would
        replace the response's full ``{en, it}`` translations map with the
        draft's one-language map, dropping IT's live title from the preview.
        Pin the merge-by-language behaviour.
        """
        page_id = self._create_published_page("live en")
        # Stamp IT live too so the response carries both translations.
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
        # EN slot reflects the draft overlay…
        assert data["translations"]["en"]["title"] == "draft en"
        # …IT slot still shows the un-touched live content.
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
        assert page.has_draft is False
        assert page.draft_data == {}
        assert page.title_en == "draft title"
        assert page.publish_at is None

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
        assert page.has_draft is False
        assert page.draft_data == {}

    def test_schedule_first_publish_makes_published_at_future(self):
        # Page has never been public → schedule defines first-appearance too.
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
        # published_at and publish_at coincide for a first-publish schedule
        assert page.publish_at is not None
        assert page.published_at is not None
        assert page.published_at > timezone.now()
        # Not yet public — published_at is in the future
        assert page.is_public is False
        assert page.status == "PLA"

    def test_schedule_swap_keeps_page_public_until_date(self):
        page_id = self._create_published_page("live title")
        # set a draft + schedule a swap in the future
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
        # The page was already public → published_at is preserved in the past
        assert page.is_public is True
        assert page.published_at <= timezone.now()
        assert page.publish_at is not None
        assert page.publish_at > timezone.now()
        # And status reads as PUB despite the queued swap
        assert page.status == "PUB"
        assert page.title_en == "live title"

        # Public route still serves OLD content
        anon = APIClient()
        resp = anon.get(f"/api/camomilla/pages-router{page.permalink}")
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
        page.publish_at = timezone.now() - timedelta(minutes=1)
        page.save(update_fields=["publish_at"])
        assert page.overlay_due is True
        anon = APIClient()
        resp = anon.get(f"/api/camomilla/pages-router{page.permalink}?cache_bust=1")
        assert resp.status_code == 200
        # The first public read wins the publish — DB row is flipped, the
        # draft is gone, the live title is the formerly-drafted one. Mirrors
        # the HTML route's lazy-materialisation behaviour.
        page.refresh_from_db()
        assert page.title_en == "swap title"
        assert page.has_draft is False
        assert page.publish_at is None
        assert page.is_public is True

    def test_scheduled_publish_command_promotes_first_publish(self):
        resp = self.client.post(
            "/api/camomilla/pages/",
            {"translations": {"en": {"title": "first publish"}}},
            format="json",
        )
        page_id = resp.json()["id"]
        # Stage a pending publish in the past (no draft → page just becomes
        # public when the cron runs publish()).
        past = timezone.now() - timedelta(minutes=1)
        page = Page.objects.get(pk=page_id)
        page.publish_at = past
        page.published_at = past
        # Need a non-empty draft to enter the cron's worklist
        page.draft_data = {"breadcrumbs_title": "first"}
        page.has_draft = True
        page.save(
            update_fields=["publish_at", "published_at", "draft_data", "has_draft"]
        )

        call_command("camomilla_publish_scheduled")

        page.refresh_from_db()
        assert page.status == "PUB"
        assert page.is_public is True
        assert page.publish_at is None

    def test_scheduled_publish_command_materialises_swap(self):
        page_id = self._create_published_page("live title")
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "swap title"}}},
            format="json",
        )
        page = Page.objects.get(pk=page_id)
        page.publish_at = timezone.now() - timedelta(minutes=1)
        page.save(update_fields=["publish_at"])

        call_command("camomilla_publish_scheduled")

        page.refresh_from_db()
        assert page.title_en == "swap title"
        assert page.has_draft is False
        assert page.publish_at is None
        assert page.status == "PUB"

    def test_revisions_and_revert_roundtrip(self):
        page_id = self._create_published_page("v1")
        # publish v1 to create a revision
        self.client.post(f"/api/camomilla/pages/{page_id}/publish/")
        # then edit + publish v2
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
        # Oldest revision is v1 (list is newest first)
        v1_id = revs[-1]["id"]

        resp = self.client.post(f"/api/camomilla/pages/{page_id}/revert/{v1_id}/")
        assert resp.status_code == 200, resp.content
        page = Page.objects.get(pk=page_id)
        assert page.title_en == "v1"

    def test_public_router_never_exposes_draft(self):
        page_id = self._create_published_page("router-leak-page")
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "secret draft"}}},
            format="json",
        )
        page = Page.objects.get(pk=page_id)
        anon = APIClient()
        resp = anon.get(f"/api/camomilla/pages-router{page.permalink}?cb=1")
        assert resp.status_code == 200
        data = resp.json()
        assert "draft_data" not in data
        assert "has_draft" not in data

    def test_patch_cannot_write_draft_fields_directly(self):
        page_id = self._create_published_page("live title")
        resp = self.client.patch(
            f"/api/camomilla/pages/{page_id}/",
            {"draft_data": {"hacked": True}, "has_draft": True},
            format="json",
        )
        assert resp.status_code == 200
        page = Page.objects.get(pk=page_id)
        assert page.draft_data == {}
        assert page.has_draft is False

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
        resp = anon.get(f"/api/camomilla/pages-router{page.permalink}?preview=true")
        assert resp.status_code == 200
        data = resp.json()
        assert "draft_data" not in data

    def test_lazy_materialisation_on_first_html_visit(self):
        """A scheduled swap whose moment has passed is materialised by the
        first HTML render — no cron needed for visited pages."""
        page_id = self._create_published_page("live title")
        # stage a draft + schedule a swap in the past
        self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/",
            {"translations": {"en": {"title": "new live title"}}},
            format="json",
        )
        page = Page.objects.get(pk=page_id)
        page.publish_at = timezone.now() - timedelta(minutes=1)
        page.save(update_fields=["publish_at"])
        assert page.overlay_due is True

        # First public HTML hit should trigger materialisation.
        anon = APIClient()
        resp = anon.get(page.permalink + "/?cb=1", follow=True)
        # Render result doesn't matter for this test (template specifics);
        # the materialisation side-effect on the row is what we verify below.
        assert resp.status_code == 200, resp.content

        page.refresh_from_db()
        # Draft has been applied to live fields; the swap is no longer pending.
        assert page.title_en == "new live title"
        assert page.has_draft is False
        assert page.draft_data == {}
        assert page.publish_at is None
        assert page.is_public is True

    def test_publish_if_due_is_noop_when_not_due(self):
        # No draft pending → no mutation, no error.
        page_id = self._create_published_page("stable")
        page = Page.objects.get(pk=page_id)
        assert page.publish_if_due() is False
        page.refresh_from_db()
        assert page.title_en == "stable"

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

    def test_lifecycle_property_matches_db_layer(self):
        """Contract test: the Python-side properties (``status`` /
        ``is_public`` / ``overlay_due``) must agree with the DB layer
        (``with_lifecycle().computed_status`` and the filter helpers
        ``.public()`` / ``.due_for_publish()``) for every lifecycle state.

        Why: there are two implementations of the same rule — one in
        Python (``AbstractPage._lifecycle_label``), one in SQL (the
        Case/When in ``with_lifecycle`` plus the Q-builders in the filter
        helpers). The duplication is structural (Python and SQL are
        different runtimes for the same rule) but pinned here so any
        future drift breaks CI.
        """
        from django.utils.translation.trans_real import activate

        now = timezone.now()
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)

        scenarios = [
            ("never_published_no_draft", {}),
            ("never_published_with_draft", {"has_draft": True, "draft_data": {"x": 1}}),
            ("published_long_ago", {"published_at": past}),
            (
                "scheduled_first_publish",
                {"published_at": future, "publish_at": future},
            ),
            (
                "live_with_scheduled_swap",
                {
                    "published_at": past,
                    "publish_at": future,
                    "has_draft": True,
                    "draft_data": {"x": 1},
                },
            ),
            (
                "live_with_overlay_due",
                {
                    "published_at": past,
                    "publish_at": past,
                    "has_draft": True,
                    "draft_data": {"x": 1},
                },
            ),
            (
                "trashed_after_being_published",
                {"published_at": past, "deleted_at": now},
            ),
            ("trashed_never_published", {"deleted_at": now}),
        ]

        # Each language has its own ``published_at`` / ``publish_at``
        # column; exercise both to cover the per-language SQL path.
        for lang in ("en", "it"):
            activate(lang)
            for label, fields in scenarios:
                page = Page.objects.create()
                for f, v in fields.items():
                    setattr(page, f, v)
                page.save()
                pk = page.pk

                # status: property vs. computed_status annotation (via
                # .values() so the annotation doesn't try to hydrate onto
                # the instance and collide with the property descriptor).
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

                # is_public: property vs. .public() filter helper
                sql_public = Page.objects.public().filter(pk=pk).exists()
                assert sql_public == page.is_public, (
                    f"[{lang}/{label}] is_public mismatch: "
                    f".public()={sql_public!r} property={page.is_public!r}"
                )

                # overlay_due: property vs. .due_for_publish() filter helper
                sql_due = Page.objects.due_for_publish().filter(pk=pk).exists()
                assert sql_due == page.overlay_due, (
                    f"[{lang}/{label}] overlay_due mismatch: "
                    f".due_for_publish()={sql_due!r} "
                    f"property={page.overlay_due!r}"
                )

                page.delete()

    def test_full_bundle_draft_keeps_only_active_language(self):
        """Backoffice forms commonly PATCH the full ``translations`` bundle
        on every save. With per-language drafts, the server must trim the
        body to the active language so publishing EN doesn't drag IT's
        translations along for the ride.
        """
        from camomilla.utils import get_nofallbacks

        page_id = self._create_published_page("live en title")
        Page.objects.filter(pk=page_id).update(
            title_it="live it title",
            published_at_it=timezone.now(),
        )

        # Backoffice sends both EN + IT translations to the EN draft endpoint
        # (typical "send the whole edit-form back" pattern).
        resp = self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/?language=en",
            {"translations": {
                "en": {"title": "draft en"},
                "it": {"title": "draft it (not intended yet)"},
            }},
            format="json",
        )
        assert resp.status_code == 200, resp.content

        page = Page.objects.get(pk=page_id)
        en_draft = get_nofallbacks(page, "draft_data", language="en")
        # IT's content was dropped — only the active language's entry survives.
        assert "en" in en_draft["translations"]
        assert "it" not in en_draft["translations"]
        # IT's own draft column stays untouched.
        assert get_nofallbacks(page, "has_draft", language="it") is False

        # Publishing EN now must not touch the IT live title.
        from django.utils.translation import override
        with override("en"):
            page.publish()
        page.refresh_from_db()
        assert page.title_en == "draft en"
        assert page.title_it == "live it title"  # untouched, no leak

    def test_drafts_are_isolated_per_language(self):
        """Saving a draft in EN must not surface as a draft in IT.

        ``draft_data`` and ``has_draft`` are translatable, so each language
        carries its own pending overlay. A regression here would mean
        publishing EN clobbers IT's queued edits, or that viewing IT
        accidentally shows EN's draft. Pin both directions.
        """
        from camomilla.utils import get_nofallbacks

        page_id = self._create_published_page("live en title")
        # Stamp IT live too so we have a true bilingual baseline.
        Page.objects.filter(pk=page_id).update(
            title_it="live it title",
            published_at_it=timezone.now(),
        )

        # Save a draft against EN only.
        resp = self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/?language=en",
            {"translations": {"en": {"title": "draft en title"}}},
            format="json",
        )
        assert resp.status_code == 200, resp.content

        page = Page.objects.get(pk=page_id)
        # EN sees the draft, IT does not — read raw per-language columns to
        # bypass modeltranslation's fallback chain (which could otherwise
        # smear EN's value onto IT or vice versa).
        assert get_nofallbacks(page, "has_draft", language="en") is True
        assert get_nofallbacks(page, "draft_data", language="en") != {}
        assert get_nofallbacks(page, "has_draft", language="it") is False
        assert get_nofallbacks(page, "draft_data", language="it") in (None, {})

        # Now save a different draft in IT, EN's draft must persist.
        resp = self.client.patch(
            f"/api/camomilla/pages/{page_id}/draft/?language=it",
            {"translations": {"it": {"title": "draft it title"}}},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        page = Page.objects.get(pk=page_id)
        assert get_nofallbacks(page, "has_draft", language="en") is True
        assert get_nofallbacks(page, "has_draft", language="it") is True
        en_draft = get_nofallbacks(page, "draft_data", language="en")
        it_draft = get_nofallbacks(page, "draft_data", language="it")
        assert en_draft["translations"]["en"]["title"] == "draft en title"
        assert it_draft["translations"]["it"]["title"] == "draft it title"

        # Publish EN — clears EN's draft only, IT's draft still queued.
        from django.utils.translation import override

        with override("en"):
            page.publish()
        page.refresh_from_db()
        assert get_nofallbacks(page, "has_draft", language="en") is False
        assert get_nofallbacks(page, "draft_data", language="en") in (None, {})
        assert page.title_en == "draft en title"
        assert get_nofallbacks(page, "has_draft", language="it") is True
        it_draft_after = get_nofallbacks(page, "draft_data", language="it")
        assert it_draft_after["translations"]["it"]["title"] == "draft it title"

    def test_auto_created_homepage_is_publicly_published(self):
        """Auto-created homepages must land in PUB lifecycle state.

        Otherwise ``fetch()`` renders the row to anonymous visitors while
        ``Page.objects.public()`` / sitemap / admin all classify it as
        DRAFT — a confusing split where the public sees content the
        lifecycle layer thinks isn't published.
        """
        from camomilla.utils import get_nofallbacks

        page, created = Page.get_or_create_homepage()
        assert created is True
        # Every language's published_at column is stamped, not just the
        # active one — otherwise reading the homepage under another
        # language activation would still report DRAFT.
        for lang in ("en", "it"):
            stamp = get_nofallbacks(page, "published_at", language=lang)
            assert stamp is not None, f"published_at_{lang} not stamped"
        assert page.is_public is True
        assert Page.objects.public().filter(pk=page.pk).exists()

    def test_queryset_filter_helpers(self):
        # Build three pages in distinct lifecycle states and verify the
        # PageQuerySet shortcuts return the right buckets.
        live_id = self._create_published_page("live one")
        Page.objects.create()  # never-published draft
        scheduled = Page.objects.create(
            publish_at=timezone.now() + timedelta(hours=1),
            published_at=timezone.now() + timedelta(hours=1),
        )

        assert Page.objects.public().filter(pk=live_id).exists()
        assert not Page.objects.public().filter(pk=scheduled.pk).exists()
        assert Page.objects.scheduled().filter(pk=scheduled.pk).exists()
        assert Page.objects.first_publish_pending().filter(pk=scheduled.pk).exists()
        # All three alive
        assert Page.objects.alive().count() == 3

        Page.objects.filter(pk=live_id).update(deleted_at=timezone.now())
        assert Page.objects.alive().count() == 2
        assert Page.objects.trashed().filter(pk=live_id).exists()
