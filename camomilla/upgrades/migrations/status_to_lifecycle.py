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

from django.db.migrations.operations import RemoveField
from django.utils import timezone

from camomilla.upgrades.base import (
    DataMigrationOperation,
    default_language,
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


def migrate_model_status_to_lifecycle(model, now=None, default_lang=None):
    """Migrate a **single** (historical) model's rows: legacy ``status`` /
    ``publication_date`` → ``published_at`` / ``deleted_at``.

    No-op unless the model actually carries both a legacy ``status`` column and
    a new ``published_at`` column, so it's safe to call on any model. Writes
    **only** the lifecycle columns with a direct ``UPDATE`` — never a full
    ``save()`` — so no field ``pre_save`` / signals fire. That matters: a full
    save would touch every field, and a structured/JSON field validating its
    relational links queries *other* page tables that may not have gained their
    new columns yet at this point in the migration graph. ``deleted_at``
    (global) is set only when **every** language is trashed.
    """
    field_names = {f.name for f in model._meta.get_fields()}
    if "status" not in field_names or "published_at" not in field_names:
        return  # not a legacy page model mid-transition — nothing to do

    now = now or timezone.now()
    default_lang = default_lang or default_language()
    langs = model_lang_codes(model, "status")

    for obj in model.objects.all().iterator():
        publication_date = getattr(obj, "publication_date", None)
        updates = {}
        if langs:
            trashed = []
            for lang in langs:
                status = getattr(obj, f"status_{lang}", None)
                updates[f"published_at_{lang}"] = published_at_from_status(
                    status, publication_date, now
                )
                trashed.append(status == OLD_STATUS_TRASHED)
            # Keep the non-suffixed base column mirroring the default language
            # (modeltranslation's base/default-language contract).
            base_lang = default_lang if default_lang in langs else langs[0]
            updates["published_at"] = published_at_from_status(
                getattr(obj, f"status_{base_lang}", None), publication_date, now
            )
            fully_trashed = bool(trashed) and all(trashed)
        else:
            status = getattr(obj, "status", None)
            updates["published_at"] = published_at_from_status(
                status, publication_date, now
            )
            fully_trashed = status == OLD_STATUS_TRASHED

        if fully_trashed:
            updates["deleted_at"] = now

        # Direct UPDATE of just the lifecycle columns — never obj.save(). A full
        # save runs every field's pre_save (e.g. a structured field resolving
        # links into page tables not yet migrated) and would crash or corrupt
        # unrelated columns. This is a plain data backfill: only these cols.
        model.objects.filter(pk=obj.pk).update(**updates)


class MigrateStatusToLifecycle(DataMigrationOperation):
    """Custom migration operation that backfills ``published_at`` /
    ``deleted_at`` from the legacy ``status`` / ``publication_date`` columns for
    **one model** — ``model_name`` within the migration's own app.

    Targeting a single model is what lets the operation appear safely in several
    apps' migrations at once: each app's migration carries one
    ``MigrateStatusToLifecycle`` per page model it defines, and each op only ever
    touches that one model.

    ``camomilla_makemigrations`` inserts these automatically; by hand, place each
    one **after** its model's ``AddField`` ops and **before** its ``RemoveField``
    ops::

        from camomilla.upgrades.migrations import MigrateStatusToLifecycle

        operations = [
            migrations.AddField("page", "published_at", ...),   # + per-language, deleted_at
            MigrateStatusToLifecycle("page"),
            migrations.RemoveField("page", "status"),           # + per-language, publication_date
        ]
    """

    def __init__(self, model_name):
        self.model_name = model_name

    def run(self, apps, schema_editor, app_label):
        # Resolve the one model this op is responsible for, in its own app.
        model = apps.get_model(app_label, self.model_name)
        migrate_model_status_to_lifecycle(model)

    def describe(self):
        return (
            f"Backfill {self.model_name} published_at/deleted_at from legacy "
            "status/publication_date"
        )

    @property
    def migration_name_fragment(self):
        return f"migrate_{self.model_name}_status_to_lifecycle"


# -- makemigrations auto-injection -----------------------------------------

_LEGACY_REMOVE_NAMES = ("status", "publication_date")


def _is_legacy_status_remove(op):
    return isinstance(op, RemoveField) and (
        op.name in _LEGACY_REMOVE_NAMES or op.name.startswith("status_")
    )


@register_injector
def inject_status_to_lifecycle(migration):
    """Insert one :class:`MigrateStatusToLifecycle` **per model** whose legacy
    ``status`` / ``publication_date`` columns ``migration`` drops. Registered so
    ``camomilla_makemigrations`` wires it in automatically.

    The trigger is the **removal** of the legacy columns, not their pairing with
    the lifecycle ``AddField`` ops. The ``AddField`` may have landed in an
    earlier migration (e.g. a plain ``makemigrations`` was run first), leaving a
    later migration that only drops ``status`` — without a backfill in between,
    that drop would silently strip every page's publication state. The operation
    no-ops at runtime when ``published_at`` isn't present yet, so triggering on
    the removal alone is safe in every ordering.

    One op per model (not per migration) so a single migration can carry several
    — e.g. camomilla's handles both ``page`` and ``article`` — each touching only
    its own model, with no overlap across apps. Placement is guaranteed by
    **partitioning**: legacy ``RemoveField`` ops are moved to the end and the
    data ops sit just before them, so every ``AddField`` (and
    ``CreateModel("Draft")``) runs before the transforms, which run before any
    legacy column is dropped — regardless of the autodetector's ordering. An
    already-present op is re-sequenced too, so a hand-edited/merged migration
    self-heals instead of leaving the data op stranded after a ``RemoveField``.

    Returns a label per **newly** inserted op (re-sequencing an existing one
    reports nothing); idempotent.
    """
    ops = migration.operations
    legacy_removes = [o for o in ops if _is_legacy_status_remove(o)]
    if not legacy_removes:
        return []  # no legacy columns dropped here → nothing to back-fill

    existing = [o for o in ops if isinstance(o, MigrateStatusToLifecycle)]
    have = {o.model_name for o in existing}
    new_models = sorted({o.model_name for o in legacy_removes} - have)
    data_ops = existing + [MigrateStatusToLifecycle(m) for m in new_models]

    rest = [
        o
        for o in ops
        if not _is_legacy_status_remove(o)
        and not isinstance(o, MigrateStatusToLifecycle)
    ]
    migration.operations = rest + data_ops + legacy_removes
    return [f"MigrateStatusToLifecycle({m})" for m in new_models]
