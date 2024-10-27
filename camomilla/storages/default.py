from django.utils.module_loading import import_string
from django.conf import settings


def get_default_storage_class():
    return import_string(settings.STORAGES["default"]["BACKEND"])
