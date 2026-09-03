"""Which language's Draft row a ``/draft/`` call lands in.

A Draft is keyed by ``(record, language)`` while its payload names languages of
its own, so the two can disagree. The rule pinned here is the one the rest of
the API follows: ``?language=`` wins, then the language the body names, then the
request's own (``Accept-Language``).

The middle rule is the one that matters in practice — an admin whose UI is in
English editing the IT tab sends ``translations: {it: …}`` with
``Accept-Language: en``, and before it existed that staged IT content on an
``en`` row: the IT preview showed live content and publishing IT applied
nothing.
"""

import pytest
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from camomilla.models import Draft, Page

from .utils.api import login_superuser


@pytest.mark.django_db(transaction=True, reset_sequences=True)
class DraftLanguageResolutionTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + login_superuser())
        resp = self.client.post(
            "/api/camomilla/pages/",
            {"translations": {"en": {"title": "live en"}}},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        self.page_id = resp.json()["id"]
        Page.objects.filter(pk=self.page_id).update(published_at=timezone.now())

    def _draft(self, payload, query="", **extra):
        return self.client.patch(
            f"/api/camomilla/pages/{self.page_id}/draft/{query}",
            payload,
            format="json",
            **extra,
        )

    def test_body_language_wins_over_accept_language(self):
        resp = self._draft(
            {"translations": {"it": {"title": "bozza it"}}},
            HTTP_ACCEPT_LANGUAGE="en",
        )
        assert resp.status_code == 200, resp.content
        assert Draft.objects.get().language == "it"

    def test_explicit_query_param_wins_over_body(self):
        """An explicit ``?language=`` is a deliberate instruction — obey it.

        Staging one language's text under another row is occasionally what a
        caller means (a translation queue, say); the parameter is how you say so.
        """
        resp = self._draft(
            {"translations": {"it": {"title": "bozza it"}}},
            query="?language=en",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        assert resp.status_code == 200, resp.content
        assert Draft.objects.get().language == "en"

    def test_multi_language_body_falls_back_to_the_request(self):
        """Two languages in the body name no single row — infer nothing."""
        resp = self._draft(
            {"translations": {"it": {"title": "a"}, "en": {"title": "b"}}},
            HTTP_ACCEPT_LANGUAGE="en",
        )
        assert resp.status_code == 200, resp.content
        assert Draft.objects.get().language == "en"

    def test_preview_reports_the_draft_schedule(self):
        when = timezone.now() + timezone.timedelta(days=1)
        self._draft({"translations": {"en": {"title": "later"}}}, query="?language=en")
        self.client.post(
            f"/api/camomilla/pages/{self.page_id}/schedule/?language=en",
            {"publish_at": when.isoformat()},
            format="json",
        )
        data = self.client.get(
            f"/api/camomilla/pages/{self.page_id}/preview/?language=en"
        ).json()
        assert data["has_draft"] is True
        assert data["has_scheduled_draft"] is True
        assert data["draft_scheduled_for"] is not None

    def test_preview_reports_an_unscheduled_draft_as_unscheduled(self):
        self._draft({"translations": {"en": {"title": "now-ish"}}}, query="?language=en")
        data = self.client.get(
            f"/api/camomilla/pages/{self.page_id}/preview/?language=en"
        ).json()
        assert data["has_draft"] is True
        assert data["has_scheduled_draft"] is False
        assert data["draft_scheduled_for"] is None
