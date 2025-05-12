import os
from tests.fixtures import load_asset
from django.conf import settings


def load_asset_and_remove_media(filename):
    asset = load_asset(filename)
    if os.path.exists(f"{settings.MEDIA_ROOT}/{filename}"):
        os.remove(f"{settings.MEDIA_ROOT}/{filename}")
    return asset
