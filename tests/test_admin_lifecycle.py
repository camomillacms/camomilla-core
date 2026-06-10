"""Admin-side lifecycle UI: list badges, filters, action URLs, bulk actions.

These tests poke at the admin layer directly rather than rendering full
HTTP responses — that's faster and avoids depending on the admin theme's
CSS. The shape we care about is:

* Custom URLs are registered with ``admin:`` namespaces.
* List columns surface lifecycle status + the per-language has_draft
  indicator (now backed by the :class:`Draft` table).
* Filter options route through the ``PageQuerySet`` helpers.
* Bulk actions invoke the corresponding model methods.

The fixtures stamp ``published_at`` directly via ``.update()`` to bypass
the publish-time machinery — these tests don't care about the publish
side effects (revisions, draft application). They care about what the
admin shows once the lifecycle state is set.
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from camomilla.models import Draft, Page
from camomilla.theme.admin import PageAdmin


@pytest.mark.django_db(transaction=True, reset_sequences=True)
class AdminLifecycleTestCase(TestCase):
    def setUp(self):
        self.admin = PageAdmin(Page, AdminSite())
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser("admin", "a@a.io", "x")

    def _request(self, path="/admin/camomilla/page/"):
        request = self.factory.get(path)
        request.user = self.user
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "session", {})
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def test_lifecycle_badge_renders_status_label(self):
        page = Page.objects.create()
        Page.objects.filter(pk=page.pk).update(published_at=timezone.now())
        page.refresh_from_db()
        markup = self.admin.lifecycle_badge(page)
        assert "Published" in str(markup)

    def test_has_draft_indicator_reflects_active_language(self):
        """The indicator queries the Draft table for the active language."""
        page = Page.objects.create()
        page.save_draft({"x": 1})
        assert self.admin.has_draft_indicator(page) is True
        # Clear the draft and the indicator should go dark.
        page.discard_draft()
        assert self.admin.has_draft_indicator(page) is False

    def test_lifecycle_status_filter_is_wired_up(self):
        from camomilla.theme.admin.pages import LifecycleStatusFilter

        assert LifecycleStatusFilter in self.admin.list_filter
        lookups = LifecycleStatusFilter.lookups(None, self._request(), self.admin)
        assert {code for code, _ in lookups} == {"PUB", "DRF", "PLA", "TRS"}

    def test_custom_admin_urls_are_registered(self):
        page = Page.objects.create()
        for verb in ("publish", "discard_draft", "trash", "restore"):
            url = reverse(f"admin:camomilla_page_{verb}", args=(page.pk,))
            assert str(page.pk) in url
            assert verb.replace("_", "-") in url or verb in url

    def test_trash_view_soft_deletes_the_page(self):
        page = Page.objects.create()
        request = self._request()
        self.admin.trash_view(request, page.pk)
        page.refresh_from_db()
        assert page.deleted_at is not None

    def test_restore_view_undeletes_a_trashed_page(self):
        page = Page.objects.create()
        Page.objects.filter(pk=page.pk).update(deleted_at=timezone.now())
        request = self._request()
        self.admin.restore_view(request, page.pk)
        page.refresh_from_db()
        assert page.deleted_at is None

    def test_discard_draft_view_clears_pending_draft(self):
        page = Page.objects.create()
        page.save_draft({"translations": {"en": {"title": "x"}}})
        assert Draft.objects.for_(page).exists()

        request = self._request()
        self.admin.discard_draft_view(request, page.pk)
        assert not Draft.objects.for_(page, language="en").exists()

    def test_bulk_trash_and_restore(self):
        a = Page.objects.create()
        b = Page.objects.create()
        request = self._request()
        self.admin.admin_trash(request, Page.objects.filter(pk__in=[a.pk, b.pk]))
        a.refresh_from_db()
        b.refresh_from_db()
        assert a.deleted_at is not None
        assert b.deleted_at is not None

        self.admin.admin_restore(request, Page.objects.filter(pk__in=[a.pk, b.pk]))
        a.refresh_from_db()
        b.refresh_from_db()
        assert a.deleted_at is None
        assert b.deleted_at is None

    def test_draft_diff_per_language(self):
        """``_collect_draft_diff`` walks every Draft attached to ``obj`` and
        returns ``[(lang, [(field, live, draft), ...]), ...]``.

        * Translatable fields compare against the per-language live column.
        * Non-translatable top-level fields compare against the bare attr.
        * Languages without a Draft are skipped.
        """
        from django.utils import translation

        page = Page.objects.create()
        Page.objects.filter(pk=page.pk).update(
            title_en="live en", title_it="live it", ordering=3
        )
        page.refresh_from_db()

        with translation.override("en"):
            page.save_draft(
                {
                    "translations": {"en": {"title": "draft en"}},
                    "ordering": 9,
                },
                merge=False,
            )

        diffs = dict(self.admin._collect_draft_diff(page))
        assert "en" in diffs
        assert "it" not in diffs
        rows = {field: (live, draft) for field, live, draft in diffs["en"]}
        assert rows["title"] == ("live en", "draft en")
        assert rows["ordering"] == (3, 9)

        with translation.override("it"):
            page.save_draft(
                {"translations": {"it": {"title": "draft it"}}}, merge=False
            )
        diffs = dict(self.admin._collect_draft_diff(page))
        assert "en" in diffs and "it" in diffs

        # Clearing EN's Draft must drop EN from the inspector.
        Draft.objects.for_(page, language="en").delete()
        diffs = dict(self.admin._collect_draft_diff(page))
        assert "en" not in diffs
        assert "it" in diffs

    def test_render_url_only_resolves_for_page_subclass(self):
        from camomilla.theme.admin.pages import _render_url_for

        page = Page.objects.create()
        url = _render_url_for(page)
        assert url is not None
        assert url.endswith(f"/{page.pk}/render/")
        assert _render_url_for(None) is None
