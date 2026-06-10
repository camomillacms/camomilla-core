"""Add visibility timestamps to every concrete AbstractPage in the website app.

Drafts and scheduled publishes now live in :class:`camomilla.models.draft.Draft`
(a side table, generic FK to any AbstractPage subclass), so the page row
itself only needs:

* ``published_at`` (translatable) — when this language went / will go public.
* ``deleted_at`` (global) — soft-delete marker.

This migration removes the legacy ``status`` / ``publication_date`` fields
in the same operation.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("website", "0008_customapiserializermodel_defaultapiserializermodel"),
    ]

    operations = [
        # --- Remove legacy fields -------------------------------------
        migrations.RemoveField(
            model_name="customapiserializermodel",
            name="publication_date",
        ),
        migrations.RemoveField(
            model_name="customapiserializermodel",
            name="status",
        ),
        migrations.RemoveField(
            model_name="custompagemetamodel",
            name="publication_date",
        ),
        migrations.RemoveField(
            model_name="custompagemetamodel",
            name="status",
        ),
        migrations.RemoveField(
            model_name="defaultapiserializermodel",
            name="publication_date",
        ),
        migrations.RemoveField(
            model_name="defaultapiserializermodel",
            name="status",
        ),
        migrations.RemoveField(
            model_name="exposedrelatedpagemodel",
            name="publication_date",
        ),
        migrations.RemoveField(
            model_name="exposedrelatedpagemodel",
            name="status",
        ),
        migrations.RemoveField(
            model_name="relatedpagemodel",
            name="publication_date",
        ),
        migrations.RemoveField(
            model_name="relatedpagemodel",
            name="status",
        ),
        migrations.RemoveField(
            model_name="unexposedrelatedpagemodel",
            name="publication_date",
        ),
        migrations.RemoveField(
            model_name="unexposedrelatedpagemodel",
            name="status",
        ),
        # --- Add visibility timestamps --------------------------------
        migrations.AddField(
            model_name="customapiserializermodel",
            name="deleted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="customapiserializermodel",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="custompagemetamodel",
            name="deleted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="custompagemetamodel",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="defaultapiserializermodel",
            name="deleted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="defaultapiserializermodel",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="exposedrelatedpagemodel",
            name="deleted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="exposedrelatedpagemodel",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="relatedpagemodel",
            name="deleted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="relatedpagemodel",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="unexposedrelatedpagemodel",
            name="deleted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="unexposedrelatedpagemodel",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
