import pytest
import json
import re
from django.test import TestCase
from rest_framework.test import APIClient
from .utils.api import login_superuser
from .utils.media import load_asset_and_remove_media


class TemoplateContextTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        token = login_superuser()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token)

    @pytest.mark.django_db
    def test_page_context_template_based(self):
        # Create page with custom context template
        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "title_en": "Page custom context template",
                "autopermalink_en": False,
                "permalink_en": "permalink_context_template",
                "template": "website/page_context_template_based.html",
                "status_en": "PUB",
            },
            format="multipart",
        )
        assert response.status_code == 201

        # Create media for custom context
        asset = load_asset_and_remove_media("10595073.png")
        response = self.client.post(
            "/api/camomilla/media/",
            {
                "file": asset,
                "data": json.dumps(
                    {
                        "translations": {
                            "en": {
                                "alt_text": "Test media",
                                "title": "Test media",
                                "description": "Description media",
                            }
                        }
                    }
                ),
            },
            format="multipart",
        )
        assert response.status_code == 201

        response = self.client.get("/permalink_context_template/")
        assert response.status_code == 200
        assert (
            re.sub(r"[\s+]", "", response.content.decode())
            == "<!DOCTYPEhtml><html><body><h1>Titlepageforpagecontexttemplatebased</h1><p>Contentpageforpagecontexttemplatebased</p><ul><li>Testmedia</li></ul></body></html>"
        )

    @pytest.mark.django_db
    def test_model_context_template_based(self):
        # Create page with custom context template
        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "title_en": "Page custom context template",
                "autopermalink_en": False,
                "permalink_en": "permalink_context_template",
                "template": "website/page_context_model_based.html",
                "status_en": "PUB",
            },
            format="multipart",
        )
        assert response.status_code == 201

        # Create media for custom context
        asset = load_asset_and_remove_media("10595073.png")
        response = self.client.post(
            "/api/camomilla/media/",
            {
                "file": asset,
                "data": json.dumps(
                    {
                        "translations": {
                            "en": {
                                "alt_text": "Test media",
                                "title": "Test media",
                                "description": "Description media",
                            }
                        }
                    }
                ),
            },
            format="multipart",
        )
        assert response.status_code == 201

        response = self.client.get("/permalink_context_template/")
        assert response.status_code == 200
        assert (
            re.sub(r"[\s+]", "", response.content.decode())
            == "<!DOCTYPEhtml><html><body><h1>Titlepageforpagecontextmodelbased</h1><p>Contentpageforpagecontextmodelbased</p><ul><li>Testmedia</li></ul></body></html>"
        )

    @pytest.mark.django_db
    def test_mixed_context_template(self):
        # Create page with custom context template
        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "title_en": "Page custom context template",
                "autopermalink_en": False,
                "permalink_en": "permalink_context_template",
                "template": "website/page_context_mixed.html",
                "status_en": "PUB",
            },
            format="multipart",
        )
        assert response.status_code == 201

        # Create media for custom context
        asset = load_asset_and_remove_media("10595073.png")
        response = self.client.post(
            "/api/camomilla/media/",
            {
                "file": asset,
                "data": json.dumps(
                    {
                        "translations": {
                            "en": {
                                "alt_text": "Test media",
                                "title": "Test media",
                                "description": "Description media",
                            }
                        }
                    }
                ),
            },
            format="multipart",
        )
        assert response.status_code == 201

        response = self.client.get("/permalink_context_template/")
        assert response.status_code == 200
        assert (
            re.sub(r"[\s+]", "", response.content.decode())
            == "<!DOCTYPEhtml><html><body><!--Templatecontext--><h1>Titlepageforpagecontexttemplatebased</h1><p>Contentpageforpagecontexttemplatebased</p><ul><li>Testmedia</li></ul><!--Modelcontext--><h1>Titlepageforpagecontextmodelbased</h1><p>Contentpageforpagecontextmodelbased</p><ul><li>Testmedia</li></ul></body></html>"
        )
