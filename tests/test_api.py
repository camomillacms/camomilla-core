import pytest
from rest_framework.test import APIClient
from .utils.api import login_superuser
from camomilla.models import Tag

client = APIClient()


@pytest.mark.django_db
def test_create_tag_no_access():
    response = client.post("/api/camomilla/tags/", {"name_en": "First tag"})
    assert response.status_code == 401


@pytest.mark.django_db
def test_crud_tag():
    # Create
    token = login_superuser()
    client.credentials(HTTP_AUTHORIZATION="Token " + token)
    response = client.post("/api/camomilla/tags/", {"name_en": "First tag"})

    assert response.json()["name"] == "First tag"
    assert len(Tag.objects.all()) == 1
    assert response.status_code == 201

    # Create another with a different language
    response = client.post("/api/camomilla/tags/", {"name_it": "Secondo tag"})
    assert response.json()["translations"]["it"]["name"] == "Secondo tag"
    assert len(Tag.objects.all()) == 2
    assert response.status_code == 201

    # Translate the second one in english
    response = client.patch(
        "/api/camomilla/tags/2/",
        {"translations": {"en": {"name": "Second tag"}}},
        format="json",
    )
    assert response.json()["translations"]["en"]["name"] == "Second tag"
    assert response.json()["translations"]["it"]["name"] == "Secondo tag"
    assert len(Tag.objects.all()) == 2

    assert response.status_code == 200

    # Get the tags in english
    response = client.get("/api/camomilla/tags/")

    assert response.json()[0]["name"] == "Second tag"

    # Get the tags in italianith fallbacks!
    response = client.get("/api/camomilla/tags/?language=it")

    assert response.json()[0]["name"] == "Secondo tag"

    # Delete the tag
    response = client.delete("/api/camomilla/tags/2/")

    assert len(Tag.objects.all()) == 1

    assert response.status_code == 204
