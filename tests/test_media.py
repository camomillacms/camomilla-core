import pytest
import json
import os
from unittest import mock
from django.conf import settings as django_settings
from django.core.management import call_command
from django.template import Context, Template
from django.test import TransactionTestCase
from camomilla import settings as camomilla_settings
from camomilla.models import Media
from .utils.api import login_superuser
from .utils.media import load_asset_and_remove_media
from rest_framework.test import APIClient

client = APIClient()


def _clean_renditions_dir():
    folder = os.path.join(
        django_settings.MEDIA_ROOT, camomilla_settings.MEDIA_RENDITIONS_FOLDER
    )
    if os.path.isdir(folder):
        for root, dirs, files in os.walk(folder, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))


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


class MediaRenditionsTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = APIClient()
        token = login_superuser()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token)
        _clean_renditions_dir()

    def tearDown(self):
        _clean_renditions_dir()

    def _upload(self, filename="37059501.png"):
        asset = load_asset_and_remove_media(filename)
        response = self.client.post(
            "/api/camomilla/media/",
            {
                "file": asset,
                "data": json.dumps(
                    {"translations": {"en": {"alt_text": "x", "title": "x"}}}
                ),
            },
            format="multipart",
        )
        assert response.status_code == 201, response.content
        return Media.objects.get(pk=response.json()["id"])

    def test_renditions_generated_on_upload(self):
        media = self._upload("37059501.png")
        assert isinstance(media.renditions, dict)
        assert "sm-webp" in media.renditions
        assert "md-webp" in media.renditions
        sm = media.renditions["sm-webp"]
        assert sm["width"] == 400
        assert sm["format"] == "webp"
        assert sm["size"] > 0
        assert "url" in sm and "path" in sm
        full_path = os.path.join(django_settings.MEDIA_ROOT, sm["path"])
        assert os.path.exists(full_path)

    def test_renditions_skip_upscaling(self):
        media = self._upload("10595073.png")
        assert "sm-webp" in media.renditions
        assert "md-webp" not in media.renditions
        assert "lg-webp" not in media.renditions

    def test_renditions_wiped_on_delete(self):
        media = self._upload("37059501.png")
        paths = [
            os.path.join(django_settings.MEDIA_ROOT, e["path"])
            for e in media.renditions.values()
        ]
        assert paths and all(os.path.exists(p) for p in paths)
        pk = media.pk
        self.client.delete(f"/api/camomilla/media/{pk}/")
        assert not any(os.path.exists(p) for p in paths)

    def test_regenerate_endpoint(self):
        media = self._upload("37059501.png")
        sm_path = os.path.join(
            django_settings.MEDIA_ROOT, media.renditions["sm-webp"]["path"]
        )
        os.remove(sm_path)
        assert not os.path.exists(sm_path)
        response = self.client.post(
            f"/api/camomilla/media/{media.pk}/regenerate-renditions/"
        )
        assert response.status_code == 200, response.content
        assert os.path.exists(sm_path)
        assert "sm-webp" in response.json()["renditions"]

    def test_regenerate_renditions_command(self):
        media = self._upload("37059501.png")
        sm_path = os.path.join(
            django_settings.MEDIA_ROOT, media.renditions["sm-webp"]["path"]
        )
        os.remove(sm_path)
        Media.objects.filter(pk=media.pk).update(renditions={})
        call_command("regenerate_renditions")
        media.refresh_from_db()
        assert "sm-webp" in media.renditions
        assert os.path.exists(sm_path)

    def test_per_instance_config_override(self):
        media = self._upload("37059501.png")
        media.renditions_config = [
            {"name": "tiny", "width": 100, "format": "webp"}
        ]
        media.save()
        media.refresh_from_db()
        media.regenerate_renditions()
        media.refresh_from_db()
        assert list(media.renditions.keys()) == ["tiny"]
        assert media.renditions["tiny"]["width"] == 100

    def test_srcset_field_shape(self):
        media = self._upload("37059501.png")
        response = self.client.get(f"/api/camomilla/media/{media.pk}/")
        assert response.status_code == 200
        data = response.json()
        assert "renditions" in data
        assert "srcset" in data
        assert isinstance(data["srcset"], dict)
        assert "webp" in data["srcset"]
        assert "400w" in data["srcset"]["webp"]

    def test_renditions_disabled_via_setting(self):
        with mock.patch.object(camomilla_settings, "MEDIA_RENDITIONS_ENABLE", False):
            media = self._upload("37059501.png")
            assert media.renditions == {}

    def test_template_tag_srcset_filter(self):
        media = self._upload("37059501.png")
        tpl = Template("{% load media_extras %}{{ media|srcset:'webp' }}")
        rendered = tpl.render(Context({"media": media}))
        assert "400w" in rendered
        assert "800w" in rendered

    def test_template_tag_picture(self):
        media = self._upload("37059501.png")
        tpl = Template(
            '{% load media_extras %}{% media_picture media alt="x" %}'
        )
        rendered = tpl.render(Context({"media": media}))
        assert "<picture>" in rendered
        assert 'type="image/webp"' in rendered
        assert '<img ' in rendered
        assert 'alt="x"' in rendered

    def test_template_tag_picture_degrades(self):
        media = self._upload("37059501.png")
        Media.objects.filter(pk=media.pk).update(renditions={})
        media.refresh_from_db()
        tpl = Template(
            '{% load media_extras %}{% media_picture media alt="x" %}'
        )
        rendered = tpl.render(Context({"media": media}))
        assert "<picture>" not in rendered
        assert "<img " in rendered
