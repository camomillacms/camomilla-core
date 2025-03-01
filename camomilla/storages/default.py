from django.utils.module_loading import import_string
from django.conf import settings

from django import VERSION as DJANGO_VERSION


def get_default_storage_class():
    if DJANGO_VERSION >= (4, 2):
        storage = settings.STORAGES["default"]["BACKEND"]
    else:
        storage = settings.DEFAULT_FILE_STORAGE
    return import_string(storage)
