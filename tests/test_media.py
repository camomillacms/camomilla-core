import pytest
import json
import os
from camomilla.models import Media
from .fixtures import load_asset
from .utils.api import login_superuser
from .utils.media import load_asset_and_remove_media
from rest_framework.test import APIClient
from django.conf import settings

client = APIClient()


@pytest.mark.django_db
def test_media_api_creation():
    token = login_superuser()
    client.credentials(HTTP_AUTHORIZATION='Token ' + token)
    asset = load_asset_and_remove_media("10595073.png")
    response = client.post(
        "/api/camomilla/media/",
        {
            "file": asset,
            "data": json.dumps({"translations": {"en": {"alt_text": "Test", "title": "Test", "description": "Test"}}}),
        },
        format="multipart",
    )
    assert response.status_code == 201
    assert Media.objects.count() == 1
    media = Media.objects.first()
    assert media.alt_text == "Test"
    assert media.title == "Test"
    assert media.description == "Test"
    assert media.file.name == "10595073.png"


@pytest.mark.django_db
def test_media_compression():
    token = login_superuser()
    client.credentials(HTTP_AUTHORIZATION='Token ' + token)
    asset = load_asset_and_remove_media("Sample-jpg-image-10mb.jpg")
    asset_size = asset.size
    response = client.post(
        "/api/camomilla/media/",
        {
            "file": asset,
            "data": json.dumps({"translations": {"en": {"alt_text": "Test", "title": "Test", "description": "Test"}}}),
        },
        format="multipart",
    )
    assert response.status_code == 201
    assert Media.objects.count() == 1
    media = Media.objects.first()
    assert media.file.size < asset_size
    assert media.file.size < 1000000  # 1MB


@pytest.mark.django_db
def test_inflating_prevent():
    token = login_superuser()
    client.credentials(HTTP_AUTHORIZATION='Token ' + token)
    asset = load_asset_and_remove_media("optimized.jpg")
    asset_size = asset.size
    response = client.post(
        "/api/camomilla/media/",
        {
            "file": asset,
            "data": json.dumps({"translations": {"en": {"alt_text": "Test", "title": "Test", "description": "Test"}}}),
        },
        format="multipart",
    )
    assert response.status_code == 201
    assert Media.objects.count() == 1
    media = Media.objects.first()
    assert media.file.size < asset_size
