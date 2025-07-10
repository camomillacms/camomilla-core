import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from .utils.api import login_superuser
from camomilla.models import Page
from camomilla.models.page import UrlRedirect
from datetime import datetime, timedelta


class PagesTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        token = login_superuser()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token)

    @pytest.mark.django_db
    def test_pages_api_no_access(self):
        client = APIClient()
        response = client.post("/api/camomilla/pages/")
        assert response.status_code == 401

    @pytest.mark.django_db
    def test_pages_api_crud(self):
        # Create page
        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "translations": {
                    "it": {
                        "title": "title_page_1",
                    }
                }
            },
            format="json",
        )

        assert response.status_code == 201
        assert len(Page.objects.all()) == 1
        page = Page.objects.first()
        assert page.id == 1
        assert page.title_it == "title_page_1"
        assert page.url_node.id == 1

        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "title_it": "title_page_2",
            },
        )

        assert response.status_code == 201
        assert len(Page.objects.all()) == 2
        page = Page.objects.last()
        assert page.id == 2
        assert page.title_it == "title_page_2"
        assert page.url_node.id == 2

        # Update page
        response = self.client.patch(
            "/api/camomilla/pages/2/",
            {
                "translations": {
                    "it": {
                        "title": "title_page_2_updated",
                    }
                }
            },
            format="json",
        )

        assert response.status_code == 200
        assert len(Page.objects.all()) == 2
        page = Page.objects.last()
        assert page.id == 2
        assert page.title_it == "title_page_2_updated"

        # Read page
        response = self.client.get("/api/camomilla/pages/2/")

        assert response.status_code == 200
        assert response.json()["id"] == 2
        assert response.json()["title"] == "title_page_2_updated"

        # Read pages
        response = self.client.get("/api/camomilla/pages/")

        assert response.status_code == 200
        assert response.json()[0]["id"] == 1
        assert response.json()[0]["title"] == "title_page_1"
        assert response.json()[1]["id"] == 2
        assert response.json()[1]["title"] == "title_page_2_updated"

        # Delete page
        response = self.client.delete("/api/camomilla/pages/2/")

        assert response.status_code == 204
        assert len(Page.objects.all()) == 1
        page = Page.objects.last()
        assert page.id == 1
        assert page.title_it == "title_page_1"

    @pytest.mark.django_db
    def test_pages_url_nodes(self):
        # Create page with automatic url creation
        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "title_en": "title_page_1",
                "title_it": "titolo_pagina_1",
            },
        )

        assert response.status_code == 201

        # EN automatic url creation
        response = self.client.get("/api/camomilla/pages/1/?language=en")
        assert response.json()["autopermalink"] == True
        assert response.json()["permalink"] == "/title_page_1"
        # IT automatic url creation
        response = self.client.get("/api/camomilla/pages/1/?language=it")
        assert response.json()["autopermalink"] == True
        assert response.json()["permalink"] == "/titolo_pagina_1"

        # Create page with manual url creation
        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "translations": {
                    "it": {
                        "title": "titolo_pagina_2",
                        "permalink": "permalink_manuale_it_2",
                        "autopermalink": False,
                    },
                    "en": {
                        "title": "title_page_2",
                        "permalink": "permalink_manual_en_2",
                        "autopermalink": False,
                    },
                }
            },
            format="json",
        )
        assert response.status_code == 201

        # EN manual url creation
        response = self.client.get("/api/camomilla/pages/2/?language=en")
        assert response.json()["autopermalink"] == False
        assert response.json()["permalink"] == "/permalink_manual_en_2"
        # IT manual url creation
        response = self.client.get("/api/camomilla/pages/2/?language=it")
        assert response.json()["autopermalink"] == False
        assert response.json()["permalink"] == "/permalink_manuale_it_2"

        # Create page with a parent page with automatic url creation
        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "title_en": "title_page_3",
                "title_it": "titolo_pagina_3",
                "parent_page": 2,
            },
        )
        assert response.status_code == 201

        # EN parent page with automatic url creation
        response = self.client.get("/api/camomilla/pages/3/?language=en")
        assert response.json()["autopermalink"] == True
        assert response.json()["permalink"] == "/permalink_manual_en_2/title_page_3"
        # IT parent page with automatic url creation
        response = self.client.get("/api/camomilla/pages/3/?language=it")
        assert response.json()["autopermalink"] == True
        assert response.json()["permalink"] == "/permalink_manuale_it_2/titolo_pagina_3"

        # Check url uniqueness and consistency EN
        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "autopermalink_en": False,
                "permalink_en": "permalink_manual_en_2",
            },
        )

        # Client error when url check uniqueness and consistency fail
        assert response.status_code == 400
        assert (
            response.data["permalink_en"][0]
            == "There is an other page with same permalink."
        )

        # Check url uniqueness and consistency IT
        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "translations": {
                    "it": {
                        "autopermalink": False,
                        "permalink": "permalink_manuale_it_2",
                    }
                }
            },
            format="json",
        )

        # Client error when url check uniqueness and consistency fail
        assert response.status_code == 400
        assert (
            response.data["permalink_it"][0]
            == "There is an other page with same permalink."
        )

    @pytest.mark.django_db
    def test_pages_url_nodes_navigation(self):
        # Test the camomilla.dynamic_pages_url handler for navigating and rendering UrlNodes
        self.client.post(
            "/api/camomilla/pages/",
            {
                "autopermalink_en": False,
                "permalink_en": "permalink_4_en",
                "status_en": "PUB",
                "autopermalink_it": False,
                "permalink_it": "permalink_4_it",
                "status_it": "PUB",
            },
        )

        response = self.client.get("/permalink_4_en/")
        assert response.status_code == 200
        response = self.client.get("/it/permalink_4_it/")
        assert response.status_code == 200

        # Test draft - published - planned and ?preview=true
        self.client.post(
            "/api/camomilla/pages/",
            {
                "translations": {
                    "it": {
                        "autopermalink": False,
                        "permalink": "permalink_5_it",
                        "status": "PLA",
                    },
                    "en": {
                        "autopermalink": False,
                        "permalink": "permalink_5_en",
                        "status": "DRF",
                    },
                }
            },
            format="json",
        )

        response = self.client.get("/permalink_5_en/")
        assert response.status_code == 404
        response = self.client.get("/permalink_5_en/?preview=true")
        assert response.status_code == 200
        response = self.client.get("/it/permalink_5_it/")
        assert response.status_code == 404

        self.client.patch(
            "/api/camomilla/pages/2/",
            {
                "publication_date": (datetime.now() - timedelta(1)).strftime("%Y-%m-%d")
                + " 00:00:00",
            },
        )

        response = self.client.get("/it/permalink_5_it/")
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_pages_url_nodes_navigation_redirects(self):
        # Test the camomilla.dynamic_pages_url handler for navigating and rendering UrlNodes
        self.client.post(
            "/api/camomilla/pages/",
            {
                "translations": {
                    "it": {
                        "autopermalink": False,
                        "permalink": "permalink_6_it",
                        "status": "PUB",
                    },
                    "en": {
                        "autopermalink": False,
                        "permalink": "permalink_6_en",
                        "status": "PUB",
                    },
                }
            },
            format="json",
        )

        # EN Insert Moved Permanently Redirect
        url_redirect = UrlRedirect.objects.create(
            language_code="en",
            from_url="/redirecting_1",
            to_url="/redirected_1",
            url_node_id=1,
        )

        response = self.client.get("/redirecting_1/")
        assert response.status_code == 301
        assert response.url == "/redirected_1/"

        # EN Change to Moved Temporarily Redirect
        url_redirect.permanent = False
        url_redirect.save()
        response = self.client.get("/redirecting_1/")
        assert response.status_code == 302

        # IT Insert Moved Permanently Redirect
        url_redirect = UrlRedirect.objects.create(
            language_code="it",
            from_url="/urlreindirizzamento_1",
            to_url="/urlreindirizzato_1",
            url_node_id=1,
        )

        response = self.client.get("/it/urlreindirizzamento_1/")
        assert response.status_code == 301
        assert response.url == "/it/urlreindirizzato_1/"

        # IT Change to Moved Temporarily Redirect
        url_redirect.permanent = False
        url_redirect.save()
        response = self.client.get("/it/urlreindirizzamento_1/")
        assert response.status_code == 302

        # Test auto redirect after permalink change
        self.client.patch(
            "/api/camomilla/pages/1/",
            {
                "translations": {
                    "it": {
                        "permalink": "permalink_6_it_changed",
                    },
                    "en": {
                        "permalink": "permalink_6_en_changed",
                    },
                }
            },
            format="json",
        )

        response = self.client.get("/permalink_6_en/")
        assert response.status_code == 301
        assert response.url == "/permalink_6_en_changed/"

        response = self.client.get("/it/permalink_6_it/")
        assert response.status_code == 301
        assert response.url == "/it/permalink_6_it_changed/"
