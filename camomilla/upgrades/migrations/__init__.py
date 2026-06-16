"""Custom **migration operations** for camomilla's breaking schema changes.

Import a custom migration straight from here and drop it into a generated
migration::

    from camomilla.upgrades.migrations import MigrateStatusToLifecycle

Each breaking change lives in its own module in this package and exposes a
reusable :class:`camomilla.upgrades.base.DataMigrationOperation`. Importing this
package imports those modules, which is what registers their
``camomilla_makemigrations`` injectors.

Available migrations:

* :class:`MigrateStatusToLifecycle` (``status_to_lifecycle``) — camomilla ≤ 6.4
  ``status`` / ``publication_date`` → ``published_at`` / ``deleted_at``.
"""

from camomilla.upgrades.migrations.status_to_lifecycle import (
    MigrateStatusToLifecycle,
    migrate_model_status_to_lifecycle,
    published_at_from_status,
)

__all__ = [
    "MigrateStatusToLifecycle",
    "migrate_model_status_to_lifecycle",
    "published_at_from_status",
]
