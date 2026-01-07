import pytest
from django.urls import reverse
from django.test import Client
from camomilla.models.page import Page


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_sitemap_xml_contains_pages():
    Page.objects.create(
        title="Test Page 1", permalink="test-page-1", status="PUB", autopermalink=False
    )
    Page.objects.create(
        title="Test Page 2", permalink="test-page-2", status="PUB", autopermalink=False
    )

    client = Client()
    response = client.get(reverse("django.contrib.sitemaps.views.sitemap"))
    assert response.status_code == 200
    assert b"<urlset" in response.content
    assert b"/test-page-1" in response.content
    assert b"/test-page-2" in response.content
