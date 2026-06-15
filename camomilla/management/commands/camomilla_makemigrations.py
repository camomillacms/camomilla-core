"""``makemigrations``, but with camomilla's upgrade data-steps auto-inserted.

A thin subclass of Django's ``makemigrations`` that reuses all of its change
detection, then runs camomilla's registered migration *injectors* over the
generated migrations **before** they're written to disk. Whenever an injector
recognises the breaking change it manages, it inserts the matching data
operation in the right place — so the result is a ready-to-apply migration with
no hand-editing.

The set of injectors is open: each breaking change registers its own (see
``camomilla.upgrades.injection``), so this command keeps working for future
upgrades without changes here.

It is a separate, opt-in command on purpose: shipping a command literally named
``makemigrations`` would silently override Django's for the whole project,
which a CMS dependency should never do. Run it explicitly when upgrading,
**without** an app argument so it covers camomilla's models and any custom
``AbstractPage`` subclass in your own apps in one pass::

    python manage.py camomilla_makemigrations

It accepts every flag ``makemigrations`` does (``--dry-run``, ``--name``, …),
so you can preview the injected migration with ``--dry-run`` first.
"""

from django.core.management.commands.makemigrations import (
    Command as MakeMigrationsCommand,
)

from camomilla.upgrades.injection import inject_upgrade_operations


class Command(MakeMigrationsCommand):
    help = (
        "Like makemigrations, but auto-inserts camomilla's data-migration "
        "operations for breaking schema changes, so the generated migration is "
        "ready to apply without hand-editing."
    )

    def write_migration_files(self, changes, *args, **kwargs):
        # ``changes`` maps app_label -> [Migration, ...]; the Migration objects
        # are still in memory here, so we can rewrite their operations before
        # the parent serializes them. Signature varies across Django versions
        # (the trailing arg is new in 5.0) — pass through with *args/**kwargs.
        for app_label, app_migrations in changes.items():
            for migration in app_migrations:
                for label in inject_upgrade_operations(migration):
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  + auto-inserted {label} into the {app_label} migration"
                        )
                    )
        return super().write_migration_files(changes, *args, **kwargs)
