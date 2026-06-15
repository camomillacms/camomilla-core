# ⬆️ Upgrading from status-based publication

Older camomilla releases (**≤ 6.4**) stored a page's publication state in two columns:

- `status` — a translatable `CharField` (`PUB` / `DRF` / `PLA` / `TRS`)
- `publication_date` — a global `DateTimeField`

The new lifecycle **derives** that state from timestamps instead:

- `published_at` — translatable; when *this language* went / goes live
- `deleted_at` — global soft-delete marker
- a separate [`Draft`](../How%20to/Use%20Page%20Lifecycle/) table (no old equivalent — drafts simply start empty)

This page is **only** relevant if you're upgrading an existing project that already has data in the old `status` / `publication_date` columns. New installs need nothing here.

::: danger Back up your database first
This migration drops the old columns. Take a full backup (or snapshot) before you start. The data step is **forward-only** — to roll back you restore the backup.
:::

## What the data step does

For every concrete page model (`Page`, `Article`, and any custom `AbstractPage` subclass), per language:

| Old `status` | New `published_at` |
|---|---|
| `PUB` Published | `publication_date` if it's in the past, otherwise *now* (stays live) |
| `PLA` Planned | `publication_date` verbatim — a future date stays `PLA`, a past date becomes `PUB`, an empty one becomes `DRF` |
| `DRF` Draft | `NULL` (draft) |
| `TRS` Trashed | `NULL` (hidden) |

`deleted_at` is **global** now, so it's set only when **every** language of a page is `TRS`. A page trashed in one language but live in another keeps its live languages; the trashed language just becomes "not published". The mapping preserves the old `is_public` result exactly for every combination (there's a test pinning this).

## Procedure

### 1. Upgrade the package

```bash
pip install -U django-camomilla-cms
```

Add `django-reversion` to `INSTALLED_APPS` (new hard dependency that powers page revisions):

```python
INSTALLED_APPS = [
    # …
    "reversion",
]
```

### 2. Generate the schema migration

```bash
python manage.py makemigrations camomilla
```

This produces one migration that **adds** `published_at` / `deleted_at`, **removes** `status` / `publication_date`, and **creates** the `Draft` table.

### 3. Insert the data step into that migration

camomilla ships the transform as a ready-made **migration operation** — `MigrateStatusToLifecycle`. Open the generated migration and:

1. Import it at the top.
2. Make sure the `AddField` operations for `published_at*` / `deleted_at` come **before** the data step.
3. Insert `MigrateStatusToLifecycle()` **before** the `RemoveField` operations for `status*` / `publication_date`.

```python
from django.db import migrations, models
from camomilla.upgrades import MigrateStatusToLifecycle   # ← add

class Migration(migrations.Migration):
    dependencies = [ ... ]

    operations = [
        # 1) add the new columns
        migrations.AddField("page", "published_at", models.DateTimeField(null=True, blank=True)),
        migrations.AddField("page", "published_at_en", models.DateTimeField(null=True, blank=True)),
        migrations.AddField("page", "published_at_it", models.DateTimeField(null=True, blank=True)),
        migrations.AddField("page", "deleted_at", models.DateTimeField(null=True, blank=True)),
        # … the same AddField ops for Article and any custom page models …

        # 2) transform the data while BOTH old and new columns exist
        MigrateStatusToLifecycle(),   # ← add

        # 3) drop the old columns
        migrations.RemoveField("page", "status"),
        migrations.RemoveField("page", "publication_date"),
        # … plus the per-language status_* removals, and CreateModel("Draft", …) …
    ]
```

The exact field/model names depend on your `LANGUAGES` setting and which page models you've defined — keep whatever `makemigrations` generated, and only **move** the `MigrateStatusToLifecycle()` line into position and add the import. The operation auto-discovers every page model that has both columns, so you don't list them anywhere.

::: tip Prefer a plain function?
The same logic is also exposed as a `RunPython`-compatible callable, if you'd rather not use a custom operation:
`migrations.RunPython(camomilla.upgrades.migrate_status_to_lifecycle, migrations.RunPython.noop)`.
:::

### 4. Apply it

```bash
python manage.py migrate
```

### 5. Verify

```python
from camomilla.models import Page
Page.objects.public().count()    # pages that were PUB (or PLA whose date has passed)
Page.objects.trashed().count()   # pages that were TRS in every language
Page.objects.draft().count()     # (drafts start empty — this counts pending Draft rows)
```

`Page.objects.filter(status="PUB")` still works too — the manager rewrites derived-status lookups into timestamp conditions, so most existing query code keeps running unchanged. See [Use Page Lifecycle](../How%20to/Use%20Page%20Lifecycle/).

## Notes

- **Drafts start empty.** The old system had no draft storage, so there's nothing to backfill into the `Draft` table. The draft / preview / scheduling workflow is available immediately for new edits.
- **One-way.** The data step's reverse is a no-op (`migrations.RunPython.noop`) — rolling the migration back restores the columns but not their values. Restore from your backup if you need to revert.
- **Custom page models** are handled automatically — the transform runs against every model that carries both the old `status` and new `published_at` columns at migration time.
