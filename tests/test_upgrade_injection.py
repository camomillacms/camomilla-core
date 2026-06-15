"""Tests for the migration auto-injection used by ``camomilla_makemigrations``.

The injector mutates an in-memory ``Migration`` — no DB needed — so these test
the positioning/idempotency/skip logic directly, without invoking the full
``makemigrations`` machinery.
"""

from django.db import migrations, models

from camomilla.upgrades import MigrateStatusToLifecycle
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


def test_injection_places_op_after_all_adds_and_before_all_legacy_removes():
    m = _transition_migration()
    inserted = inject_upgrade_operations(m)
    assert inserted == ["MigrateStatusToLifecycle"]

    ops = m.operations
    op_idx = _index(ops, lambda o: isinstance(o, MigrateStatusToLifecycle))[0]
    last_add = max(_index(ops, lambda o: isinstance(o, migrations.AddField)))
    first_legacy_remove = min(_index(ops, lambda o: isinstance(o, migrations.RemoveField)))
    assert last_add < op_idx < first_legacy_remove
    # CreateModel("Draft") stays before the data op (and never moves to the end).
    draft_idx = _index(ops, lambda o: isinstance(o, migrations.CreateModel))[0]
    assert draft_idx < op_idx


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
        return "DummyOperation"

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
