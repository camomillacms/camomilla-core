"""Tests for the legacy status → timestamp-lifecycle upgrade.

The DB-touching transform runs inside a downstream project's migration (it
needs the old ``status`` / ``publication_date`` columns, which this repo's
schema no longer has), so most tests pin the pure mapping logic; the two
end-to-end tests build a synthetic model with both column sets and run the
per-model transform against it.
"""

from datetime import timedelta

import pytest
from django.db import connection
from django.db import models as dj_models
from django.test.utils import isolate_apps
from django.utils import timezone

from camomilla.upgrades.migrations import (
    MigrateStatusToLifecycle,
    migrate_model_status_to_lifecycle,
    published_at_from_status,
)


def test_published_maps_past_publication_date_verbatim():
    now = timezone.now()
    past = now - timedelta(days=3)
    # PUB with a past publication_date keeps the historical go-live date.
    assert published_at_from_status("PUB", past, now) == past


def test_published_with_future_or_missing_date_stamps_now():
    now = timezone.now()
    future = now + timedelta(days=3)
    # Old PUB ignored publication_date entirely (always public), so to stay
    # live the new published_at must be <= now → stamped to now.
    assert published_at_from_status("PUB", future, now) == now
    assert published_at_from_status("PUB", None, now) == now


def test_planned_carries_publication_date_through():
    now = timezone.now()
    future = now + timedelta(days=2)
    past = now - timedelta(days=2)
    # Future → stays PLA; past → becomes PUB; None → DRF. In every case the
    # value carried over reproduces the old PLA visibility exactly.
    assert published_at_from_status("PLA", future, now) == future
    assert published_at_from_status("PLA", past, now) == past
    assert published_at_from_status("PLA", None, now) is None


def test_draft_and_trashed_are_not_published():
    now = timezone.now()
    past = now - timedelta(days=1)
    for date in (past, now, None):
        assert published_at_from_status("DRF", date, now) is None
        assert published_at_from_status("TRS", date, now) is None


def test_unknown_status_is_not_published():
    now = timezone.now()
    assert published_at_from_status("", None, now) is None
    assert published_at_from_status(None, None, now) is None


def test_visibility_is_preserved_across_the_mapping():
    """The new ``published_at <= now`` visibility must equal the old
    ``is_public`` for the same inputs."""
    now = timezone.now()
    future = now + timedelta(days=1)
    past = now - timedelta(days=1)

    def new_is_public(status, pub):
        pa = published_at_from_status(status, pub, now)
        return pa is not None and pa <= now

    def old_is_public(status, pub):
        if status == "PUB":
            return True
        if status == "PLA":
            return bool(pub) and now > pub
        return False

    for status in ("PUB", "PLA", "DRF", "TRS"):
        for pub in (past, future, None):
            assert new_is_public(status, pub) == old_is_public(status, pub), (
                f"visibility drift for status={status!r} pub={pub!r}"
            )


def test_operation_serializes_into_a_migration():
    """``makemigrations`` must be able to write the custom op into a migration
    file — so it has to deconstruct, round-tripping its ``model_name`` arg."""
    from django.db.migrations.writer import OperationWriter

    op = MigrateStatusToLifecycle("page")
    assert op.describe()
    assert op.migration_name_fragment == "migrate_page_status_to_lifecycle"
    # deconstruct round-trips the model name so the serialized op rebuilds itself.
    _name, args, kwargs = op.deconstruct()
    assert list(args) == ["page"] and kwargs == {}
    string, imports = OperationWriter(op, indentation=0).serialize()
    assert "MigrateStatusToLifecycle(" in string
    assert "'page'" in string
    assert any(imp.startswith("import camomilla.upgrades.migrations") for imp in imports)


class _SaveNotAllowed(Exception):
    """Raised if the backfill ever full-saves a row instead of UPDATE-ing it."""


# Armed only while the transform runs (not during fixture setup), so any
# ``pre_save`` on the guarded field during the backfill means a full save slipped
# through. A direct UPDATE never calls ``pre_save`` on unrelated columns.
_BACKFILL_GUARD = {"armed": False}


class _GuardedField(dj_models.TextField):
    def pre_save(self, model_instance, add):
        if _BACKFILL_GUARD["armed"]:
            raise _SaveNotAllowed("lifecycle backfill must not full-save the row")
        return super().pre_save(model_instance, add)


@pytest.mark.django_db(transaction=True)
@isolate_apps("tests")
def test_transform_updates_columns_without_full_save():
    """Regression: the backfill must write the lifecycle columns with a direct
    UPDATE, not ``obj.save()``. A full save runs every field's ``pre_save`` —
    e.g. a structured/JSON field resolving relational links into *other* page
    tables that haven't gained their new columns yet — which crashed real
    upgrades with ``column project_project.published_at does not exist``."""

    class LegacySideEffectPage(dj_models.Model):
        status = dj_models.CharField(max_length=3, null=True)
        publication_date = dj_models.DateTimeField(null=True)
        published_at = dj_models.DateTimeField(null=True)
        deleted_at = dj_models.DateTimeField(null=True)
        payload = _GuardedField(null=True)

        class Meta:
            app_label = "tests"

    now = timezone.now()
    past = now - timedelta(days=2)

    with connection.schema_editor() as se:
        se.create_model(LegacySideEffectPage)
    try:
        pub = LegacySideEffectPage.objects.create(
            status="PUB", publication_date=past, payload="keep me"
        )

        _BACKFILL_GUARD["armed"] = True
        try:
            # With the old obj.save() this raised _SaveNotAllowed (payload.pre_save).
            migrate_model_status_to_lifecycle(LegacySideEffectPage)
        finally:
            _BACKFILL_GUARD["armed"] = False

        pub.refresh_from_db()
        assert pub.published_at == past   # lifecycle column written
        assert pub.payload == "keep me"   # unrelated field never touched
    finally:
        with connection.schema_editor() as se:
            se.delete_model(LegacySideEffectPage)


@pytest.mark.django_db(transaction=True)
@isolate_apps("tests")
def test_transform_monolingual_end_to_end():
    class LegacyPage(dj_models.Model):
        status = dj_models.CharField(max_length=3, null=True)
        publication_date = dj_models.DateTimeField(null=True)
        published_at = dj_models.DateTimeField(null=True)
        deleted_at = dj_models.DateTimeField(null=True)

        class Meta:
            app_label = "tests"

    now = timezone.now()
    past = now - timedelta(days=2)
    future = now + timedelta(days=2)

    with connection.schema_editor() as se:
        se.create_model(LegacyPage)
    try:
        pub = LegacyPage.objects.create(status="PUB", publication_date=past)
        pub_future = LegacyPage.objects.create(status="PUB", publication_date=future)
        drf = LegacyPage.objects.create(status="DRF")
        pla = LegacyPage.objects.create(status="PLA", publication_date=future)
        trs = LegacyPage.objects.create(status="TRS", publication_date=past)

        migrate_model_status_to_lifecycle(LegacyPage)

        for obj in (pub, pub_future, drf, pla, trs):
            obj.refresh_from_db()

        assert pub.published_at == past and pub.deleted_at is None
        # PUB with a future date stays live → stamped to ~now (>= our `now`).
        assert pub_future.published_at is not None and pub_future.published_at >= now
        assert pub_future.deleted_at is None
        assert drf.published_at is None and drf.deleted_at is None
        assert pla.published_at == future and pla.deleted_at is None
        assert trs.published_at is None and trs.deleted_at is not None
    finally:
        with connection.schema_editor() as se:
            se.delete_model(LegacyPage)


@pytest.mark.django_db(transaction=True)
@isolate_apps("tests")
def test_transform_bilingual_trash_aggregation():
    class LegacyTransPage(dj_models.Model):
        status = dj_models.CharField(max_length=3, null=True)
        status_en = dj_models.CharField(max_length=3, null=True)
        status_it = dj_models.CharField(max_length=3, null=True)
        publication_date = dj_models.DateTimeField(null=True)
        published_at = dj_models.DateTimeField(null=True)
        published_at_en = dj_models.DateTimeField(null=True)
        published_at_it = dj_models.DateTimeField(null=True)
        deleted_at = dj_models.DateTimeField(null=True)

        class Meta:
            app_label = "tests"

    now = timezone.now()
    past = now - timedelta(days=2)

    with connection.schema_editor() as se:
        se.create_model(LegacyTransPage)
    try:
        # Trashed in EVERY language → whole page trashed (global deleted_at).
        all_trs = LegacyTransPage.objects.create(
            status="TRS", status_en="TRS", status_it="TRS"
        )
        # Live in EN, trashed in IT → page stays alive; IT just not published.
        mixed = LegacyTransPage.objects.create(
            status="PUB", status_en="PUB", status_it="TRS", publication_date=past
        )

        migrate_model_status_to_lifecycle(LegacyTransPage)
        all_trs.refresh_from_db()
        mixed.refresh_from_db()

        assert all_trs.deleted_at is not None
        assert all_trs.published_at_en is None and all_trs.published_at_it is None

        assert mixed.deleted_at is None
        assert mixed.published_at_en == past   # PUB + past date
        assert mixed.published_at_it is None   # TRS → hidden
        assert mixed.published_at == past      # base mirrors default language (en)
    finally:
        with connection.schema_editor() as se:
            se.delete_model(LegacyTransPage)
