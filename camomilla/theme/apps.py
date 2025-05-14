from __future__ import unicode_literals
from collections import OrderedDict

from django.apps import AppConfig, apps
from django.conf import settings


def add_apps(*app_list):
    installed_apps = getattr(settings, "INSTALLED_APPS", [])
    changed = False
    for app in app_list:
        if app not in installed_apps:
            changed = True
            installed_apps = [app, *installed_apps]
    if changed:
        setattr(settings, "INSTALLED_APPS", installed_apps)
        apps.app_configs = OrderedDict()
        apps.apps_ready = apps.models_ready = apps.loading = apps.ready = False
        apps.clear_cache()
        apps.populate(settings.INSTALLED_APPS)


def set_default_settings(**kwargs):
    for key, value in kwargs.items():
        setattr(settings, key, getattr(settings, key, value))


class CamomillaThemeConfig(AppConfig):
    name = "camomilla.theme"

    def ready(self):
        add_apps(
            "tinymce",
            "django_jsonform",
            "admin_interface",
            "colorfield",
            "structured",
        )
