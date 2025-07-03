from django.test import TestCase
from rest_framework.test import APIClient
from .utils.api import login_superuser
from example.website.models import (
    ExposedRelatedPageModel,
    UnexposedRelatedPageModel,
    RelatedPageModel,
)

client = APIClient()


class PageRelationApi(TestCase):
    def setUp(self):
        token = login_superuser()
        client.credentials(HTTP_AUTHORIZATION="Token " + token)

    def test_exposed_relation(self):
        exposed_related_page_model = ExposedRelatedPageModel.objects.create(
            title="ExposedRelatedPageModel 1",
            permalink="exposed-related-page-model-1",
            status="PUB",
            autopermalink=False,
        )
        related_page_model = RelatedPageModel.objects.create(
            title="RelatedPageModel 1",
            permalink="related-page-model-1",
            status="PUB",
            autopermalink=False,
        )
        related_page_model.exposed_pages.add(exposed_related_page_model)
        related_page_model.save()

        response = client.get("/api/camomilla/pages-router/related-page-model-1")
        assert response.status_code == 200
        data = response.json()
        assert data["exposed_pages"][0]["id"] == exposed_related_page_model.id

        response = client.get(
            "/api/camomilla/pages-router/exposed-related-page-model-1"
        )
        assert response.status_code == 200
        data = response.json()
        assert (
            "related_pages" in data
        ), "Exposed related pages should be included in the API response"

    def test_unexposed_relation(self):
        unexposed_related_page_model = UnexposedRelatedPageModel.objects.create(
            title="UnexposedRelatedPageModel 1",
            permalink="unexposed-related-page-model-1",
            status="PUB",
            autopermalink=False,
        )
        related_page_model = RelatedPageModel.objects.create(
            title="RelatedPageModel 1",
            permalink="related-page-model-1",
            status="PUB",
            autopermalink=False,
        )

        related_page_model.unexposed_pages.add(unexposed_related_page_model)
        related_page_model.save()

        response = client.get("/api/camomilla/pages-router/related-page-model-1")
        assert response.status_code == 200
        data = response.json()
        assert data["unexposed_pages"][0]["id"] == unexposed_related_page_model.id

        response = client.get(
            "/api/camomilla/pages-router/unexposed-related-page-model-1"
        )
        assert response.status_code == 200
        data = response.json()
        assert (
            "related_pages" not in data
        ), "Unexposed related pages should not be included in the API response"
