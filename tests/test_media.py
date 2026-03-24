import pytest
import json
from django.test import TransactionTestCase
from camomilla.models import Media
from .utils.api import login_superuser
from .utils.media import load_asset_and_remove_media
from rest_framework.test import APIClient

client = APIClient()


class MediaTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = APIClient()
        token = login_superuser()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token)

    def test_media_api_crud(self):
        # Create media 1
        asset = load_asset_and_remove_media("10595073.png")
        response = self.client.post(
            "/api/camomilla/media/",
            {
                "file": asset,
                "data": json.dumps(
                    {
                        "translations": {
                            "en": {
                                "alt_text": "Test 1",
                                "title": "Test 1",
                                "description": "Test 1",
                            }
                        }
                    }
                ),
            },
            format="multipart",
        )
        assert response.status_code == 201
        assert Media.objects.count() == 1
        media = Media.objects.first()
        assert media.alt_text == "Test 1"
        assert media.title == "Test 1"
        assert media.description == "Test 1"
        assert media.file.name == "10595073.png"

        # Create media 2
        asset = load_asset_and_remove_media("37059501.png")
        response = self.client.post(
            "/api/camomilla/media/",
            {
                "file": asset,
                "data": json.dumps(
                    {
                        "translations": {
                            "en": {
                                "alt_text": "Test 2",
                                "title": "Test 2",
                                "description": "Test 2",
                            }
                        }
                    }
                ),
            },
            format="multipart",
        )
        assert response.status_code == 201
        assert Media.objects.count() == 2
        media = Media.objects.first()  # Ordering in model is descending -pk
        assert media.alt_text == "Test 2"
        assert media.title == "Test 2"
        assert media.description == "Test 2"
        assert media.file.name == "37059501.png"

        # Read media
        response = self.client.get("/api/camomilla/media/2/")
        assert response.status_code == 200
        assert response.json()["id"] == 2
        assert response.json()["title"] == "Test 2"
        assert response.json()["file"] == "http://testserver/media/37059501.png"

        # Read medias
        response = self.client.get("/api/camomilla/media/")
        assert response.status_code == 200
        assert response.json()[0]["id"] == 2  # Ordering in model is descending -pk
        assert response.json()[0]["title"] == "Test 2"
        assert response.json()[1]["id"] == 1
        assert response.json()[1]["title"] == "Test 1"

        # Delete media
        response = self.client.delete("/api/camomilla/media/2/")
        assert response.status_code == 204
        assert len(Media.objects.all()) == 1
        media = Media.objects.last()
        assert media.id == 1
        assert media.title == "Test 1"

    def test_media_filtering(self):
        # Create media with PNG
        asset = load_asset_and_remove_media("10595073.png")
        response = self.client.post(
            "/api/camomilla/media/",
            {
                "file": asset,
                "data": json.dumps(
                    {
                        "translations": {
                            "en": {
                                "alt_text": "PNG Test",
                                "title": "PNG Test",
                                "description": "PNG Test",
                            }
                        }
                    }
                ),
            },
            format="multipart",
        )
        assert response.status_code == 201
        media_id = response.json()["id"]
        
        # Check that mime_type is set
        response = self.client.get(f"/api/camomilla/media/{media_id}/")
        assert response.status_code == 200
        media_data = response.json()
        print("Media data:", media_data)  # Debug print
        assert "mime_type" in media_data
        assert media_data["mime_type"] == "image/png"
        
        # Filter by title
        response = self.client.get("/api/camomilla/media/?fltr=title='PNG Test'")
        assert response.status_code == 200
        assert len(response.json()) == 1
        
        # Filter by mime_type image/* (should use startswith)
        response = self.client.get("/api/camomilla/media/?fltr=mime_type__startswith='image/'")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["mime_type"] == "image/png"
        
        # Filter by mime_type that doesn't match
        response = self.client.get("/api/camomilla/media/?fltr=mime_type='video/mp4'")
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_media_compression(self):
        asset = load_asset_and_remove_media("Sample-jpg-image-10mb.jpg")
        asset_size = asset.size
        response = self.client.post(
            "/api/camomilla/media/",
            {
                "file": asset,
                "data": json.dumps(
                    {
                        "translations": {
                            "en": {
                                "alt_text": "Test",
                                "title": "Test",
                                "description": "Test",
                            }
                        }
                    }
                ),
            },
            format="multipart",
        )
        assert response.status_code == 201
        assert Media.objects.count() == 1
        media = Media.objects.first()
        assert media.file.size < asset_size
        assert media.file.size < 1000000  # 1MB

    def test_inflating_prevent(self):
        asset = load_asset_and_remove_media("optimized.jpg")
        asset_size = asset.size
        response = self.client.post(
            "/api/camomilla/media/",
            {
                "file": asset,
                "data": json.dumps(
                    {
                        "translations": {
                            "en": {
                                "alt_text": "Test",
                                "title": "Test",
                                "description": "Test",
                            }
                        }
                    }
                ),
            },
            format="multipart",
        )
        assert response.status_code == 201
        assert Media.objects.count() == 1
        media = Media.objects.first()
        assert media.file.size < asset_size
