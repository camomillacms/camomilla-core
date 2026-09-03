"""Articles get the same draft workflow as pages.

``Draft`` is generic and every lifecycle method lives on ``AbstractPage``, but
the API actions used to sit on ``PageViewSet`` alone — so an editor could stage
an edit on a Page and not on an Article. ``PageLifecycleMixin`` is what makes
them peers; this pins the whole loop (draft → preview overlay → publish) on the
subclass, which is where a regression would land first.
"""

import pytest
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from camomilla.models import Article, Draft

from .utils.api import login_superuser


@pytest.mark.django_db(transaction=True, reset_sequences=True)
class ArticleLifecycleTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + login_superuser())
        resp = self.client.post(
            "/api/camomilla/articles/",
            {"translations": {"en": {"title": "live title"}}},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        self.article_id = resp.json()["id"]
        Article.objects.filter(pk=self.article_id).update(published_at=timezone.now())

    def test_draft_publish_round_trip(self):
        base = f"/api/camomilla/articles/{self.article_id}/"

        resp = self.client.patch(
            f"{base}draft/",
            {"translations": {"en": {"title": "drafted title"}}},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)

        # The live row is untouched — a draft is staged, not applied.
        self.assertEqual(Article.objects.get(pk=self.article_id).title, "live title")
        self.assertEqual(Draft.objects.count(), 1)

        # The preview action overlays it.
        preview = self.client.get(f"{base}preview/").json()
        self.assertTrue(preview["has_draft"])
        self.assertEqual(preview["translations"]["en"]["title"], "drafted title")

        resp = self.client.post(f"{base}publish/", {}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(Article.objects.get(pk=self.article_id).title, "drafted title")

    def test_discard_draft(self):
        base = f"/api/camomilla/articles/{self.article_id}/"
        self.client.patch(
            f"{base}draft/",
            {"translations": {"en": {"title": "throwaway"}}},
            format="json",
        )
        self.assertEqual(Draft.objects.count(), 1)

        resp = self.client.post(f"{base}discard-draft/", {}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(Draft.objects.count(), 0)
        self.assertEqual(Article.objects.get(pk=self.article_id).title, "live title")
