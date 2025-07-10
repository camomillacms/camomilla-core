import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from tests.utils.media import load_asset_and_remove_media
from .utils.api import login_superuser
from camomilla.models import Page, Media
from example.website.models import CustomPageMetaModel, InvalidPageMetaModel


class PagaMetaTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        token = login_superuser()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token)

    @pytest.mark.django_db
    def test_page_meta_rendering(self):
        asset = load_asset_and_remove_media("37059501.png")
        Media.objects.create(
            file=asset,
            alt_text="Test Media",
            title="Test Media",
            description="Description of test media",
        )
        page = CustomPageMetaModel.objects.create(
            title="Test Page",
            custom_field="Custom Data",
            permalink="test-page",
            status="PUB",
            autopermalink=False,
        )
        page.save()
        response = self.client.get("/test-page/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "👻 I&#x27;m beeing injected!" in content
        assert "<h1>I'm the custom template!</h1>" in content
        assert "<ul><li>Test Media</li></ul>" in content

    @pytest.mark.django_db
    def test_page_meta_custom_parent_page(self):
        parent_page = Page.objects.create(
            title="Parent Page",
            permalink="parent-page",
            status="PUB",
            autopermalink=False,
        )
        child_page = CustomPageMetaModel.objects.create(
            title="Child Page",
            custom_field="Child Data",
            status="PUB",
            custom_parent_page=parent_page,
        )
        assert child_page.permalink == "/parent-page/child-page"

    @pytest.mark.django_db
    def test_page_meta_custom_serializer(self):

        CustomPageMetaModel.objects.create(
            title="Test Page with Custom Serializer",
            custom_field="Custom Data",
            permalink="test-page-custom-serializer",
            status="PUB",
            autopermalink=False,
        )

        response = self.client.get(
            "/api/camomilla/pages-router/test-page-custom-serializer"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Page with Custom Serializer"
        assert data["custom_field"] == "Custom Data"
        assert data["permalink"] == "/test-page-custom-serializer"
        assert (
            data["serializer_custom_field"]
            == "I'm coming from CustomPageSerializer! 🫡"
        )

    @pytest.mark.django_db
    def test_page_meta_custom_serializer_error(self):
        with pytest.raises(ValueError) as exc_info:
            InvalidPageMetaModel.get_serializer()
            assert (
                str(exc_info.value)
                == "Standard serializer <class 'example.website.serializers.InvalidSerializer'> must be a subclass of AbstractPageMixin"
            )
