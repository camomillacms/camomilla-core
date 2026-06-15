"""Upgrade: legacy **status-based** publication → timestamp-derived lifecycle.

Applies to projects coming from camomilla ≤ 6.4.

Old schema (per concrete ``AbstractPage`` table)::

    status            CharField   PUB / DRF / PLA / TRS   (translatable)
    publication_date  DateTimeField                       (global)

New schema::

    published_at      DateTimeField  (translatable) — when this language went/goes live
    deleted_at        DateTimeField  (global)       — soft-delete marker
    + camomilla.Draft table          (no old equivalent; nothing to backfill)

Mapping, per language ``L`` (driven by the per-language ``status_L``):

==========  ==========================================================
old status  new ``published_at_L``
==========  ==========================================================
``PUB``     ``publication_date`` if it's a past timestamp, else ``now`` (stay live)
``PLA``     ``publication_date`` verbatim (future → PLA, past → PUB, NULL → DRF)
``DRF``     ``NULL`` (draft)
``TRS``     ``NULL`` (hidden)
==========  ==========================================================

``deleted_at`` is **global** in the new system, so it is set to ``now`` only
when **every** language is ``TRS`` (the whole page is in the trash). A page
trashed in some languages but live in others keeps its live languages; the
trashed ones simply become "not published" (``published_at_L = NULL``).
"""

from django.db.migrations.operations import AddField, RemoveField
from django.utils import timezone

from camomilla.upgrades.base import (
    DataMigrationOperation,
    default_language,
    iter_models_with_fields,
    model_lang_codes,
)
from camomilla.upgrades.injection import register_injector


OLD_STATUS_PUBLISHED = "PUB"
OLD_STATUS_DRAFT = "DRF"
OLD_STATUS_SCHEDULED = "PLA"
OLD_STATUS_TRASHED = "TRS"


def published_at_from_status(status, publication_date, now):
    """Map a single ``(status, publication_date)`` pair to ``published_at``.

    Pure function — no DB access — so it can be unit-tested directly and
    reused by both the migration and any custom tooling.
    """
    if status == OLD_STATUS_PUBLISHED:
        # Old PUB was public immediately, regardless of publication_date. The
        # new lifecycle needs published_at <= now to be public: preserve the
        # historical go-live date when it's in the past, otherwise stamp now
        # so the page stays live after the upgrade.
        if publication_date is not None and publication_date <= now:
            return publication_date
        return now
    if status == OLD_STATUS_SCHEDULED:
        # Old PLA became public once publication_date passed (and only if set).
        # Carrying publication_date straight over reproduces visibility exactly:
        # a future date stays PLA, a past date becomes PUB, a NULL becomes DRF.
        return publication_date
    # DRF / TRS / unknown → not published.
    return None


def migrate_status_to_lifecycle(apps, schema_editor):
    """Populate ``published_at`` / ``deleted_at`` from the legacy ``status`` /
    ``publication_date`` columns, for every page model in ``apps``.

    The shared core used by :class:`MigrateStatusToLifecycle` (and usable as a
    plain ``RunPython`` callable if you prefer). Must run while BOTH the old
    and new columns exist — i.e. after the ``AddField`` ops for
    ``published_at`` / ``deleted_at`` and before the ``RemoveField`` ops for
    ``status`` / ``publication_date``. Operates on historical models, so no
    custom ``save()`` / signals fire — plain column writes only.
    """
    now = timezone.now()
    default_lang = default_language()

    for model in iter_models_with_fields(apps, "status", "published_at"):
        langs = model_lang_codes(model, "status")
        for obj in model.objects.all().iterator():
            publication_date = getattr(obj, "publication_date", None)
            if langs:
                trashed = []
                for lang in langs:
                    status = getattr(obj, f"status_{lang}", None)
                    setattr(
                        obj,
                        f"published_at_{lang}",
                        published_at_from_status(status, publication_date, now),
                    )
                    trashed.append(status == OLD_STATUS_TRASHED)
                # Keep the non-suffixed base column mirroring the default
                # language (modeltranslation's base/default-language contract).
                base_lang = default_lang if default_lang in langs else langs[0]
                obj.published_at = published_at_from_status(
                    getattr(obj, f"status_{base_lang}", None), publication_date, now
                )
                fully_trashed = bool(trashed) and all(trashed)
            else:
                status = getattr(obj, "status", None)
                obj.published_at = published_at_from_status(
                    status, publication_date, now
                )
                fully_trashed = status == OLD_STATUS_TRASHED

            if fully_trashed:
                obj.deleted_at = now
            obj.save()


class MigrateStatusToLifecycle(DataMigrationOperation):
    """Custom migration operation that backfills ``published_at`` /
    ``deleted_at`` from the legacy ``status`` / ``publication_date`` columns.

    Drop it into the schema migration ``makemigrations`` generates, **after**
    the ``AddField`` ops for the new columns and **before** the ``RemoveField``
    ops for the old ones::

        from camomilla.upgrades import MigrateStatusToLifecycle

        operations = [
            migrations.AddField("page", "published_at", ...),   # + per-language
            migrations.AddField("page", "deleted_at", ...),
            MigrateStatusToLifecycle(),
            migrations.RemoveField("page", "status"),           # + per-language
            migrations.RemoveField("page", "publication_date"),
        ]
    """

    def run(self, apps, schema_editor):
        migrate_status_to_lifecycle(apps, schema_editor)

    def describe(self):
        return (
            "Backfill page published_at/deleted_at from legacy "
            "status/publication_date"
        )

    @property
    def migration_name_fragment(self):
        return "migrate_status_to_lifecycle"


# -- makemigrations auto-injection -----------------------------------------

_LEGACY_REMOVE_NAMES = ("status", "publication_date")
_LIFECYCLE_ADD_NAMES = ("published_at", "deleted_at")


def _is_legacy_status_remove(op):
    return isinstance(op, RemoveField) and (
        op.name in _LEGACY_REMOVE_NAMES or op.name.startswith("status_")
    )


def _adds_lifecycle_columns(operations):
    return any(
        isinstance(op, AddField)
        and (op.name in _LIFECYCLE_ADD_NAMES or op.name.startswith("published_at_"))
        for op in operations
    )


@register_injector
def inject_status_to_lifecycle(migration):
    """Insert :class:`MigrateStatusToLifecycle` when ``migration`` both adds the
    new lifecycle columns and removes the legacy ``status`` / ``publication_date``
    columns. Registered so ``camomilla_makemigrations`` wires it in automatically.

    Correctness is guaranteed by **partitioning** rather than index math: the
    legacy ``RemoveField`` ops are moved to the end and the data op inserted just
    before them, so every ``AddField`` (and ``CreateModel("Draft")``) runs before
    the transform, which runs before any legacy column is dropped — regardless of
    how the autodetector ordered them.
    """
    ops = migration.operations
    if any(isinstance(op, MigrateStatusToLifecycle) for op in ops):
        return None  # already wired up — idempotent
    if not (_adds_lifecycle_columns(ops) and any(_is_legacy_status_remove(o) for o in ops)):
        return None

    legacy_removes = [o for o in ops if _is_legacy_status_remove(o)]
    rest = [o for o in ops if not _is_legacy_status_remove(o)]
    migration.operations = rest + [MigrateStatusToLifecycle()] + legacy_removes
    return "MigrateStatusToLifecycle"
