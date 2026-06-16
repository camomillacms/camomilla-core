"""Tests for the migration auto-injection used by ``camomilla_makemigrations``.

The injector mutates an in-memory ``Migration`` — no DB needed — so these test
the positioning/idempotency/skip/multi-model logic directly, without invoking
the full ``makemigrations`` machinery.
"""

from django.db import migrations, models

from camomilla.upgrades.migrations import MigrateStatusToLifecycle
from camomilla.upgrades.injection import inject_upgrade_operations


def _transition_migration():
    """A migration shaped like what ``makemigrations`` emits for the upgrade —
    deliberately with an AddField placed AFTER a RemoveField to prove the
    partition reorders correctly."""
    m = migrations.Migration("0010_lifecycle", "camomilla")
    m.operations = [
        migrations.AddField("page", "published_at", models.DateTimeField(null=True)),
        migrations.AddField("page", "published_at_en", models.DateTimeField(null=True)),
        migrations.RemoveField("page", "status"),
        # interleaved: a lifecycle AddField sitting after a legacy RemoveField
        migrations.AddField("page", "deleted_at", models.DateTimeField(null=True)),
        migrations.CreateModel("Draft", fields=[("id", models.AutoField(primary_key=True))]),
        migrations.RemoveField("page", "status_en"),
        migrations.RemoveField("page", "publication_date"),
    ]
    return m


def _index(ops, predicate):
    return [i for i, o in enumerate(ops) if predicate(o)]


def test_injection_inserts_one_op_targeting_the_model():
    m = _transition_migration()
    inserted = inject_upgrade_operations(m)
    assert inserted == ["MigrateStatusToLifecycle(page)"]

    ops = m.operations
    data_ops = [o for o in ops if isinstance(o, MigrateStatusToLifecycle)]
    assert len(data_ops) == 1
    assert data_ops[0].model_name == "page"  # targets a single, specific model

    op_idx = _index(ops, lambda o: isinstance(o, MigrateStatusToLifecycle))[0]
    last_add = max(_index(ops, lambda o: isinstance(o, migrations.AddField)))
    first_legacy_remove = min(_index(ops, lambda o: isinstance(o, migrations.RemoveField)))
    assert last_add < op_idx < first_legacy_remove
    # CreateModel("Draft") stays before the data op (never moves to the end).
    draft_idx = _index(ops, lambda o: isinstance(o, migrations.CreateModel))[0]
    assert draft_idx < op_idx


def test_injection_one_op_per_model_in_a_multi_model_migration():
    """A single migration touching several page models (e.g. camomilla's Page +
    Article) gets ONE op per model, each targeting only its own model — so the
    operation never sweeps across models/apps."""
    m = migrations.Migration("0010_lifecycle", "camomilla")
    m.operations = [
        migrations.AddField("page", "published_at", models.DateTimeField(null=True)),
        migrations.AddField("article", "published_at", models.DateTimeField(null=True)),
        migrations.AddField("page", "deleted_at", models.DateTimeField(null=True)),
        migrations.AddField("article", "deleted_at", models.DateTimeField(null=True)),
        migrations.RemoveField("page", "status"),
        migrations.RemoveField("article", "status"),
        migrations.RemoveField("page", "publication_date"),
        migrations.RemoveField("article", "publication_date"),
    ]
    inserted = inject_upgrade_operations(m)
    assert sorted(inserted) == [
        "MigrateStatusToLifecycle(article)",
        "MigrateStatusToLifecycle(page)",
    ]

    ops = m.operations
    targeted = sorted(o.model_name for o in ops if isinstance(o, MigrateStatusToLifecycle))
    assert targeted == ["article", "page"]
    # Both data ops sit after every AddField and before every legacy RemoveField.
    op_indices = _index(ops, lambda o: isinstance(o, MigrateStatusToLifecycle))
    last_add = max(_index(ops, lambda o: isinstance(o, migrations.AddField)))
    first_remove = min(_index(ops, lambda o: isinstance(o, migrations.RemoveField)))
    assert last_add < min(op_indices)
    assert max(op_indices) < first_remove


def test_injection_is_idempotent():
    m = _transition_migration()
    inject_upgrade_operations(m)
    before = list(m.operations)
    assert inject_upgrade_operations(m) == []
    assert m.operations == before
    assert sum(isinstance(o, MigrateStatusToLifecycle) for o in m.operations) == 1


def test_injection_skips_unrelated_migration():
    m = migrations.Migration("0011_other", "camomilla")
    m.operations = [
        migrations.AddField("page", "subtitle", models.CharField(max_length=10, null=True)),
    ]
    assert inject_upgrade_operations(m) == []
    assert not any(isinstance(o, MigrateStatusToLifecycle) for o in m.operations)


def test_injection_skips_when_only_adds_present():
    # Adding the lifecycle columns without removing the legacy ones is not the
    # upgrade transition (e.g. a brand-new model) — don't inject.
    m = migrations.Migration("0012_addonly", "camomilla")
    m.operations = [
        migrations.AddField("page", "published_at", models.DateTimeField(null=True)),
        migrations.AddField("page", "deleted_at", models.DateTimeField(null=True)),
    ]
    assert inject_upgrade_operations(m) == []


def test_injection_only_targets_models_in_transition():
    """If one model is mid-transition and another only gains columns, only the
    transitioning model gets an op."""
    m = migrations.Migration("0013_mixed", "camomilla")
    m.operations = [
        migrations.AddField("page", "published_at", models.DateTimeField(null=True)),
        migrations.AddField("page", "deleted_at", models.DateTimeField(null=True)),
        migrations.RemoveField("page", "status"),
        # 'article' only gains a lifecycle column — no legacy removal → not in transition
        migrations.AddField("article", "published_at", models.DateTimeField(null=True)),
    ]
    inserted = inject_upgrade_operations(m)
    assert inserted == ["MigrateStatusToLifecycle(page)"]
    targeted = [o.model_name for o in m.operations if isinstance(o, MigrateStatusToLifecycle)]
    assert targeted == ["page"]


def test_injection_backfills_when_only_legacy_removes_present():
    """Split upgrade: the lifecycle AddFields already landed in an earlier
    migration (e.g. a plain ``makemigrations`` was run first), so this one only
    drops the legacy columns. The backfill must STILL be injected — and before
    the removes — otherwise ``status`` is dropped with ``published_at`` left NULL
    = silent loss of every page's publication state."""
    m = migrations.Migration("0014_dropstatus", "camomilla")
    m.operations = [
        migrations.RemoveField("page", "status"),
        migrations.RemoveField("page", "status_en"),
        migrations.RemoveField("page", "publication_date"),
    ]
    inserted = inject_upgrade_operations(m)
    assert inserted == ["MigrateStatusToLifecycle(page)"]

    ops = m.operations
    data_ops = [o for o in ops if isinstance(o, MigrateStatusToLifecycle)]
    assert len(data_ops) == 1 and data_ops[0].model_name == "page"
    # The backfill runs BEFORE any legacy column is dropped (status still exists).
    op_idx = _index(ops, lambda o: isinstance(o, MigrateStatusToLifecycle))[0]
    first_remove = min(_index(ops, lambda o: isinstance(o, migrations.RemoveField)))
    assert op_idx < first_remove


def test_injection_resequences_a_misordered_existing_op():
    """A hand-edited / merged / squashed migration with the data op placed AFTER
    the legacy RemoveField self-heals: the injector re-sequences it before the
    removes so the backfill reads ``status`` while it still exists (it would
    otherwise no-op against the already-dropped column)."""
    m = migrations.Migration("0015_handedited", "camomilla")
    m.operations = [
        migrations.AddField("page", "published_at", models.DateTimeField(null=True)),
        migrations.RemoveField("page", "status"),
        MigrateStatusToLifecycle("page"),  # mis-placed: sits after the remove
    ]
    # Re-sequencing an existing op reports nothing new, but still reorders.
    assert inject_upgrade_operations(m) == []

    ops = m.operations
    data_ops = [o for o in ops if isinstance(o, MigrateStatusToLifecycle)]
    assert len(data_ops) == 1  # not duplicated
    op_idx = _index(ops, lambda o: isinstance(o, MigrateStatusToLifecycle))[0]
    first_remove = min(_index(ops, lambda o: isinstance(o, migrations.RemoveField)))
    assert op_idx < first_remove


def test_registry_is_generic_runs_any_registered_injector():
    """The injection system isn't coupled to the status upgrade — any module can
    register an injector and `camomilla_makemigrations` will run it."""
    from camomilla.upgrades.injection import (
        _INJECTORS,
        inject_upgrade_operations,
        register_injector,
    )

    calls = []

    def _dummy_injector(migration):
        calls.append(migration)
        return ["DummyOperation"]

    register_injector(_dummy_injector)
    try:
        m = migrations.Migration("0001_x", "someapp")
        m.operations = []
        labels = inject_upgrade_operations(m)
        assert "DummyOperation" in labels
        assert calls == [m]
        # registering the same injector twice is a no-op
        register_injector(_dummy_injector)
        assert _INJECTORS.count(_dummy_injector) == 1
    finally:
        _INJECTORS.remove(_dummy_injector)
