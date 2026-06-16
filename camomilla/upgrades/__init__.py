"""Data-migration upgrades for breaking schema changes.

Camomilla ships no migrations of its own (they're generated downstream into
``camomilla_migrations`` via ``MIGRATION_MODULES``), so the supported way to
ship a data transform for a breaking change is a reusable migration
**operation** that a project drops into the migration ``makemigrations``
generates.

Layout:

* ``camomilla.upgrades.base`` — :class:`DataMigrationOperation` and helpers.
* ``camomilla.upgrades.injection`` — the ``camomilla_makemigrations``
  auto-injection registry.
* ``camomilla.upgrades.migrations`` — the **custom migrations** themselves, one
  module per breaking change. This is what you import::

      from camomilla.upgrades.migrations import MigrateStatusToLifecycle

The public API is also re-exported here for convenience.

To add a new one:

1. Create ``camomilla/upgrades/migrations/<change>.py``.
2. Subclass :class:`camomilla.upgrades.base.DataMigrationOperation`; implement
   ``run(apps, schema_editor, app_label)``, ``describe()`` and
   ``migration_name_fragment``. Reuse the helpers in ``base``
   (``iter_models_with_fields``, ``model_lang_codes``, ``default_language``).
3. Define an injector in the same module and decorate it with
   ``@camomilla.upgrades.injection.register_injector`` so
   ``camomilla_makemigrations`` wires the operation into a generated migration
   automatically.
4. Re-export the operation from ``camomilla/upgrades/migrations/__init__.py``
   (importing the module there is what registers its injector).
5. Document the procedure on the docs "Upgrading" page.
"""

from camomilla.upgrades.base import DataMigrationOperation
from camomilla.upgrades.injection import (
    inject_upgrade_operations,
    register_injector,
)
from camomilla.upgrades.migrations import (
    MigrateStatusToLifecycle,
    migrate_model_status_to_lifecycle,
    published_at_from_status,
)

__all__ = [
    "DataMigrationOperation",
    "inject_upgrade_operations",
    "register_injector",
    "MigrateStatusToLifecycle",
    "migrate_model_status_to_lifecycle",
    "published_at_from_status",
]
