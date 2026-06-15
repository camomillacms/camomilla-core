"""Shared scaffolding for camomilla's data-migration upgrades.

Each breaking schema change that needs to transform existing data gets its own
module next to this one (see ``status_to_lifecycle.py`` for the reference
example). They all subclass :class:`DataMigrationOperation` and reuse the
helpers here, so a new upgrade is just "subclass + implement ``run``".
"""

from django.db.migrations.operations.base import Operation


def iter_models_with_fields(apps, *required_fields):
    """Yield every (historical) model that declares ALL of ``required_fields``.

    Lets a transform target the right tables without hard-coding model names —
    it naturally covers the core models (``Page``, ``Article``) and any
    downstream ``AbstractPage`` subclass. Use it from inside a migration with
    the historical ``apps`` registry so it sees the columns as they exist at
    that point in the migration graph.
    """
    wanted = set(required_fields)
    for model in apps.get_models():
        names = {f.name for f in model._meta.get_fields()}
        if wanted <= names:
            yield model


def model_lang_codes(model, base):
    """Language codes present as ``<base>_<lang>`` columns on a historical
    model, e.g. ``model_lang_codes(Page, "status") -> ["en", "it"]``.

    An empty list means a monolingual install (only the un-suffixed ``base``
    column exists) — callers branch on that.
    """
    names = {f.name for f in model._meta.get_fields()}
    prefix = f"{base}_"
    return sorted(n[len(prefix):] for n in names if n.startswith(prefix))


def default_language():
    """The project's default language code (``settings.LANGUAGE_CODE``)."""
    from camomilla.settings import DEFAULT_LANGUAGE

    return DEFAULT_LANGUAGE


class DataMigrationOperation(Operation):
    """Base class for camomilla's **data-only, forward-only** migration
    operations.

    Subclass it, implement :meth:`run` (the transform) plus ``describe()`` and
    ``migration_name_fragment``, then drop the operation into the migration
    ``makemigrations`` generates — positioned so the columns it reads/writes
    all exist when it runs.

    Behaviour provided here:

    * **No model-state change** — ``state_forwards`` is a no-op (these ops only
      move data; the schema is changed by the surrounding Add/Remove ops).
    * **Historical models** — ``database_forwards`` calls ``run`` with the
      ``apps`` registry from the pre-operation state, so the transform sees the
      tables exactly as they exist at that point in the migration.
    * **Forward-only** — ``database_backwards`` is a no-op; reverting means
      restoring from a backup. (``reversible`` stays ``True`` so a backward
      migration doesn't hard-error.)
    """

    reduces_to_sql = False
    reversible = True
    atomic = True

    def state_forwards(self, app_label, state):
        # Pure data move — the model state is unchanged by this operation.
        pass

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        # ``from_state`` is the project state just before this op runs.
        self.run(from_state.apps, schema_editor)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        # Forward-only: surrounding RemoveField reversals re-create columns,
        # but their values are not reconstructed here.
        pass

    def run(self, apps, schema_editor):
        """Perform the data transform. ``apps`` is the historical registry;
        use :func:`iter_models_with_fields` to find the tables to touch."""
        raise NotImplementedError
