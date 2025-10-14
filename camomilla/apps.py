from __future__ import unicode_literals

from django.apps import AppConfig
from django.conf import settings
from camomilla.utils.mysql import monkey_patch_mysql_datetime


class CamomillaConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "camomilla"

    def ready(self):
        migration_modules = getattr(settings, "MIGRATION_MODULES", {})
        if "camomilla" not in migration_modules:
            migration_modules["camomilla"] = "camomilla_migrations"
        setattr(settings, "MIGRATION_MODULES", migration_modules)
        self.module.autodiscover()
        monkey_patch_mysql_datetime()
