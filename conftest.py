import os
import shutil
from django.core.management import call_command
from django.db import connections
import pytest


def clean_migration_folders():
    from django.conf import settings

    for dir in settings.MIGRATION_MODULES.values():
        if os.path.exists(dir):
            shutil.rmtree(dir)


def create_migration_folders():
    from django.conf import settings

    for dir in settings.MIGRATION_MODULES.values():
        if not os.path.exists(dir):
            os.makedirs(dir)
            open(os.path.join(dir, "__init__.py"), "w").close()


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    from django.conf import settings

    create_migration_folders()
    with django_db_blocker.unblock():
        # For some databases initial flush may fail before migrate, run migrations first.
        call_command("makemigrations", interactive=False)
        call_command("migrate", interactive=False)
        # Only flush for sqlite to mirror previous behaviour; other engines get a clean DB container.
        if "sqlite" in settings.DATABASES["default"]["ENGINE"]:
            call_command("sqlflush")
    yield
    for connection in connections.all():
        connection.close()
    # clean_migration_folders()
