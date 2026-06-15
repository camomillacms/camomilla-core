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

### 2. Generate the migration — with the data step already inserted

Use camomilla's `camomilla_makemigrations` command instead of `makemigrations`:

```bash
python manage.py camomilla_makemigrations
```

It's a drop-in wrapper around `makemigrations` (same flags — `--dry-run`, `--name`, …) that runs camomilla's migration injectors over the generated migrations and **auto-inserts the matching data step** in the correct position whenever it recognises a breaking change — here, the status → lifecycle transition. (It's a general mechanism: future camomilla upgrades register their own injectors, so the same command keeps handling them.) You get a ready-to-apply migration — no hand-editing. It prints a line when it injects:

```
  + auto-inserted MigrateStatusToLifecycle into the camomilla migration
```

::: tip Don't pass an app name
Run it **without** an app argument. The transition affects `camomilla.Page` / `camomilla.Article` **and** any custom `AbstractPage` subclass in your own apps — whose migrations are generated in *your* app, not in `camomilla`. A no-arg run injects the data step into every affected app's migration in one pass; `… camomilla` would skip your custom page models. Add `--dry-run` to preview without writing.
:::

::: details Prefer to do it by hand?
Run the normal `python manage.py makemigrations camomilla`, then open the generated migration and add the operation yourself: import it, and place `MigrateStatusToLifecycle()` **after** the `AddField` ops for `published_at*` / `deleted_at` and **before** the `RemoveField` ops for `status*` / `publication_date`.

```python
from camomilla.upgrades import MigrateStatusToLifecycle

operations = [
    migrations.AddField("page", "published_at", ...),   # + per-language, deleted_at
    MigrateStatusToLifecycle(),                          # ← between Add and Remove
    migrations.RemoveField("page", "status"),           # + per-language, publication_date
    # … CreateModel("Draft", …) …
]
```

The operation auto-discovers every page model that has both columns, so you don't list them anywhere. The same logic is also exposed as a `RunPython`-compatible callable if you prefer: `migrations.RunPython(camomilla.upgrades.migrate_status_to_lifecycle, migrations.RunPython.noop)`.
:::

### 3. Apply it

```bash
python manage.py migrate
```

### 4. Verify

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
