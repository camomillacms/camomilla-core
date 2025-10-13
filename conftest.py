import os
import shutil
from django.core.management import call_command
from django.db import connections
import pytest


_DB_TEST_CONFIG = {}


def _configure_database(settings):
    """Allow selecting a different database backend for tests via env vars.

    Supported backends (env DB_BACKEND): sqlite (default), postgres, mysql.
    Other connection parameters read from: DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT.
    If postgres/mysql selected but required driver not installed tests will error naturally.
    """
    # Precedence: explicit pytest flag configuration (_DB_TEST_CONFIG) > env vars > hard defaults
    backend = (_DB_TEST_CONFIG.get("backend") or os.environ.get("DB_BACKEND") or "sqlite").lower()
    name = _DB_TEST_CONFIG.get("name") or os.environ.get("DB_NAME") or "test_camomilla"
    user = _DB_TEST_CONFIG.get("user") or os.environ.get("DB_USER") or "camomilla"
    password = _DB_TEST_CONFIG.get("password") or os.environ.get("DB_PASSWORD") or "camomilla"
    host = _DB_TEST_CONFIG.get("host") or os.environ.get("DB_HOST") or "127.0.0.1"
    port = _DB_TEST_CONFIG.get("port") or os.environ.get("DB_PORT")  # use default if not provided

    if backend == "sqlite":
        settings.DATABASES["default"].update(
            {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": os.environ.get("SQLITE_NAME", "test_db.sqlite3"),
            }
        )
    elif backend in {"postgres", "postgresql", "psql"}:
        settings.DATABASES["default"].update(
            {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": name,
                "USER": user,
                "PASSWORD": password,
                "HOST": host,
                **({"PORT": port} if port else {}),
            }
        )
    elif backend in {"mysql", "mariadb"}:
        settings.DATABASES["default"].update(
            {
                "ENGINE": "django.db.backends.mysql",
                "NAME": name,
                "USER": user,
                "PASSWORD": password,
                "HOST": host,
                **({"PORT": port} if port else {}),
                "OPTIONS": {"charset": "utf8mb4"},
            }
        )
    else:
        raise RuntimeError(f"Unsupported DB_BACKEND '{backend}'")


def pytest_addoption(parser):
    group = parser.getgroup("database")
    group.addoption(
        "--db-backend",
        action="store",
        dest="db_backend",
        default=None,
        help="Database backend for tests: sqlite (default), postgres, mysql",
    )


@pytest.fixture(autouse=True, scope="session")
def _db_cli_options(pytestconfig):
    """Capture the --db-backend flag into internal config without mutating environment.

    Other connection parameters can still be provided via env vars manually if needed.
    """
    backend = pytestconfig.getoption("db_backend")
    if backend:
        _DB_TEST_CONFIG["backend"] = backend.lower()
        if backend.lower() == "postgres":
            _DB_TEST_CONFIG.update(
                {
                    "name": "test_camomilla",
                    "user": "camomilla",
                    "password": "camomilla",
                    "host": "127.0.0.1",
                    "port": "5432",
                }
            )
        elif backend.lower() in {"mysql", "mariadb"}:
            _DB_TEST_CONFIG.update(
                {
                    "name": "test_camomilla",
                    "user": "camomilla",
                    "password": "camomilla",
                    "host": "127.0.0.1",
                    "port": "3306",
                }
            )
        # sqlite: no additional defaults


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

    # Ensure a DATABASES dict exists even if not defined (pytest-django usually sets one)
    if not settings.DATABASES:
        settings.DATABASES["default"] = {}

    _configure_database(settings)
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
