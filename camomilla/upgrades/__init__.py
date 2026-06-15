"""Data-migration upgrades for breaking schema changes.

Camomilla ships no migrations of its own (they're generated downstream into
``camomilla_migrations`` via ``MIGRATION_MODULES``), so the supported way to
ship a data transform for a breaking change is a reusable migration
**operation** that a project drops into the migration ``makemigrations``
generates. Each change lives in its own module here and exposes such an
operation; the public API is re-exported below so downstream migrations can do::

    from camomilla.upgrades import MigrateStatusToLifecycle

Available upgrades:

* :class:`MigrateStatusToLifecycle` (``status_to_lifecycle``) — camomilla ≤ 6.4
  ``status`` / ``publication_date`` → ``published_at`` / ``deleted_at``.

To add a new one:

1. Create ``camomilla/upgrades/<change>.py``.
2. Subclass :class:`camomilla.upgrades.base.DataMigrationOperation`; implement
   ``run(apps, schema_editor)``, ``describe()`` and ``migration_name_fragment``.
   Reuse the helpers in ``base`` (``iter_models_with_fields``,
   ``model_lang_codes``, ``default_language``).
3. Re-export the operation from this ``__init__``.
4. Document the procedure on the docs "Upgrading" page.
"""

from camomilla.upgrades.base import DataMigrationOperation
from camomilla.upgrades.status_to_lifecycle import (
    MigrateStatusToLifecycle,
    migrate_status_to_lifecycle,
    published_at_from_status,
)

__all__ = [
    "DataMigrationOperation",
    "MigrateStatusToLifecycle",
    "migrate_status_to_lifecycle",
    "published_at_from_status",
]
