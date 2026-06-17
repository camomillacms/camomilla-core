# ⬆️ Upgrading

This page collects the breaking changes you need to know about when moving an
existing project to a newer camomilla. Each section is independent — read the
one(s) that match the version you're coming from. New installs need none of it.

- [**Routing & query-performance changes**](#routing-query-performance-changes) — the latest release reworks page/URL routing for speed. It changes three public contracts but needs **no database migration**.
- [**From status-based publication**](#from-status-based-publication) — older releases (**≤ 6.4**) stored publication state in a `status` column; the lifecycle now derives it from timestamps. This one **does** need a data migration.

## Routing & query-performance changes

The latest release rewrites how pages and URLs are resolved and serialized to
eliminate a class of N+1 queries. The wins are transparent, but three public
contracts changed in the process.

::: tip No migration needed
These are **code and API-output** changes only — there is no schema change and
nothing to backfill. Upgrade the package and adjust the call sites below.

```bash
pip install -U django-camomilla-cms
```
:::

### 1. `UrlNode.objects` is lean by default — opt into lifecycle data

Previously *every* `UrlNode` query `LEFT JOIN`ed every concrete page table and
annotated `is_public` / `status` / `indexable` / `published_at` / `deleted_at` /
`date_updated_at` onto each row — even simple permalink-uniqueness lookups. The
default queryset is now **join-free**, and that page-derived data is opt-in via
two chainable methods:

- **`.with_lifecycle()`** — adds the `is_public` / `status` / `indexable` /
  `published_at` / `deleted_at` / `date_updated_at` annotations. Use it for SQL
  filtering / ordering and cheap scalar reads.
- **`.with_page()`** — `select_related`s the concrete page row so `node.page`
  resolves with no extra query. Use it wherever you read `node.page` over a set.

If you query `UrlNode` directly anywhere in your project, update those call sites:

| Before (≤ 6.4) | After |
|---|---|
| `UrlNode.objects.filter(is_public=True)` | `UrlNode.objects.with_lifecycle().filter(is_public=True)` |
| `UrlNode.objects.filter(status="PUB")` | `UrlNode.objects.with_lifecycle().filter(status="PUB")` |
| `UrlNode.objects.order_by("status")` | `UrlNode.objects.with_lifecycle().order_by("status")` |
| `node.is_public` / `node.status` / `node.indexable` | `.with_lifecycle()` first — **or** read it off the page: `node.page.is_public` |

Without `.with_lifecycle()`, filtering or ordering on those names raises a
`FieldError`, and reading `node.is_public` / `node.status` / `node.indexable`
raises `AttributeError` — they were annotations, never model fields.

`node.page` itself still works on a lean node (it's a model property), but it
fires **one query per node**. When you iterate a `UrlNode` queryset and touch
`node.page`, chain `.with_page()` to collapse that into a single query:

```python
for node in UrlNode.objects.with_page():   # was an N+1 of node.page lookups
    node.page                              # cached — no query
```

::: warning Language caveat for `with_lifecycle()`
The annotation resolves the active-language column at queryset **build** time,
so evaluate the queryset under the same active language you built it with
(camomilla's own callers run inside the request language). For access-time,
per-instance-correct values regardless of active language, read the page
property — `node.page.is_public` / `node.page.status`.
:::

### 2. Relational `Permalink` links no longer embed `page` / `content_type`

The typed link primitive (`camomilla.types.Permalink` — what powers links in
`template_data`, menus, and any `StructuredJSONField`) used to serialize two
**derived** keys into its JSON for relational links: `page` (a
`{id, name, model}` blob) and `content_type`. A relational link now stores and
emits only its canonical value — `url_node` — plus the derived `url`.

`page` and `content_type` are still available **server-side** as Python
properties (`permalink.page`, `permalink.content_type`), computed on demand from
`url_node` — they're just no longer part of the serialized payload.

**Frontend impact:** read a link's target from `url_node` / `url`, not from
`link.page` / `link.content_type` (those keys are gone from API responses).
Already-stored JSON that still carries the old keys is read back safely — they're
ignored, not an error — so there is nothing to migrate.

### 3. Sensitive auth-user columns are stripped from nested API output

This is also a **security fix**. When a depth-based read serializer auto-nests a
foreign key to `AUTH_USER_MODEL` — e.g. an `Article.author` surfaced on the
public, unauthenticated pages router — camomilla now strips the known-sensitive
default columns:

```
password, last_login, is_superuser, is_staff, is_active, email, groups, user_permissions
```

Previously the full user row (including the password hash and privilege flags)
could be exposed in that nested output.

**Consumer impact:** a nested `author` (or any nested user) no longer includes
those fields. The filter is a **fail-open blacklist** — everything *not* listed,
**including your own custom user columns**, is still exposed automatically. So if
your custom `AUTH_USER_MODEL` carries secret columns (`api_key`, `stripe_id`,
`totp_secret`, …), add their names to keep them out of public responses:

```python
CAMOMILLA = {
    "API": {
        "SAFE_NESTING": {
            "SENSITIVE_USER_FIELDS": (
                "password", "last_login", "is_superuser", "is_staff",
                "is_active", "email", "groups", "user_permissions",
                "api_key", "totp_secret",   # ← your custom secret columns
            )
        }
    }
}
```

See [Use Settings](../How%20to/Use%20Settings/) and [Use API](../How%20to/Use%20API/).

### Also in this release (non-breaking)

- **`Page.objects.with_urls()`** is the new canonical fast path for listing
  pages and rendering their URLs — it `select_related`s the whole routing chain
  (`url_node` + a bounded ancestor chain) so reading `routerlink` / `permalink` /
  `breadcrumbs` over the result set costs no extra queries. The page list/detail
  API endpoints already use it; reach for it in your own views, sitemaps, and
  template loops. See [Use Page Lifecycle](../How%20to/Use%20Page%20Lifecycle/).
- **Ordering defaults are now lazy.** A serializer's ordering field used to run a
  `MAX(ordering)` aggregate every time it built its fields (i.e. on every read);
  it's now a create-only default, evaluated only when a new row needs one. No
  behavior change — just no aggregate on reads.

## From status-based publication

Older camomilla releases (**≤ 6.4**) stored a page's publication state in two columns:

- `status` — a translatable `CharField` (`PUB` / `DRF` / `PLA` / `TRS`)
- `publication_date` — a global `DateTimeField`

The new lifecycle **derives** that state from timestamps instead:

- `published_at` — translatable; when *this language* went / goes live
- `deleted_at` — global soft-delete marker
- a separate [`Draft`](../How%20to/Use%20Page%20Lifecycle/) table (no old equivalent — drafts simply start empty)

This section is **only** relevant if you're upgrading an existing project that already has data in the old `status` / `publication_date` columns. New installs need nothing here.

::: danger Back up your database first
This migration drops the old columns. Take a full backup (or snapshot) before you start. The data step is **forward-only** — to roll back you restore the backup.
:::

### What the data step does

For every concrete page model (`Page`, `Article`, and any custom `AbstractPage` subclass), per language:

| Old `status` | New `published_at` |
|---|---|
| `PUB` Published | `publication_date` if it's in the past, otherwise *now* (stays live) |
| `PLA` Planned | `publication_date` verbatim — a future date stays `PLA`, a past date becomes `PUB`, an empty one becomes `DRF` |
| `DRF` Draft | `NULL` (draft) |
| `TRS` Trashed | `NULL` (hidden) |

`deleted_at` is **global** now, so it's set only when **every** language of a page is `TRS`. A page trashed in one language but live in another keeps its live languages; the trashed language just becomes "not published". The mapping preserves the old `is_public` result exactly for every combination (there's a test pinning this).

### Procedure

#### 1. Upgrade the package

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

#### 2. Generate the migration — with the data step already inserted

Use camomilla's `camomilla_makemigrations` command instead of `makemigrations`:

```bash
python manage.py camomilla_makemigrations
```

It's a drop-in wrapper around `makemigrations` (same flags — `--dry-run`, `--name`, …) that runs camomilla's migration injectors over the generated migrations and **auto-inserts the matching data step** in the correct position whenever it recognises a breaking change — here, the status → lifecycle transition. (It's a general mechanism: future camomilla upgrades register their own injectors, so the same command keeps handling them.) You get a ready-to-apply migration — no hand-editing. It prints a line when it injects:

```
  + auto-inserted MigrateStatusToLifecycle(page) into the camomilla migration
  + auto-inserted MigrateStatusToLifecycle(article) into the camomilla migration
```

(one per page model — your own apps' custom page models get their own, in their own migrations)

::: tip Don't pass an app name
Run it **without** an app argument. The transition affects `camomilla.Page` / `camomilla.Article` **and** any custom `AbstractPage` subclass in your own apps — whose migrations are generated in *your* app, not in `camomilla`. A no-arg run injects the data step into every affected app's migration in one pass; `… camomilla` would skip your custom page models. Add `--dry-run` to preview without writing.
:::

::: warning Already ran plain `makemigrations`?
If you ran the stock `python manage.py makemigrations` **before** this step, it wrote a migration that drops `status` with **no backfill** in between — applying it would lose your publication state. Delete that just-generated migration and regenerate it with `camomilla_makemigrations` (the injector only rewrites migrations as they're generated, not ones already on disk). The data step *is* re-inserted automatically if the lifecycle columns were added in one migration and the legacy ones are dropped in a later one — but a single migration that does both without the backfill is unsafe to apply.
:::

::: details Prefer to do it by hand?
Run the normal `python manage.py makemigrations`, then open each generated migration and add **one operation per page model**, naming the model. Place each `MigrateStatusToLifecycle("<model>")` **after** that model's `AddField` ops (`published_at*` / `deleted_at`) and **before** its `RemoveField` ops (`status*` / `publication_date`).

```python
from camomilla.upgrades.migrations import MigrateStatusToLifecycle

operations = [
    migrations.AddField("page", "published_at", ...),       # + per-language, deleted_at
    migrations.AddField("article", "published_at", ...),
    MigrateStatusToLifecycle("page"),                        # one op per model
    MigrateStatusToLifecycle("article"),
    migrations.RemoveField("page", "status"),               # + per-language, publication_date
    migrations.RemoveField("article", "status"),
]
```

Each op migrates only its own model, so the same operation appears safely in several apps' migrations (yours, for custom page models, plus camomilla's) without overlapping.
:::

#### 3. Apply it

```bash
python manage.py migrate
```

#### 4. Verify

```python
from camomilla.models import Page
Page.objects.public().count()    # pages that were PUB (or PLA whose date has passed)
Page.objects.trashed().count()   # pages that were TRS in every language
Page.objects.draft().count()     # (drafts start empty — this counts pending Draft rows)
```

`Page.objects.filter(status="PUB")` still works too — the manager rewrites derived-status lookups into timestamp conditions, so most existing query code keeps running unchanged. See [Use Page Lifecycle](../How%20to/Use%20Page%20Lifecycle/).

### Notes

- **Drafts start empty.** The old system had no draft storage, so there's nothing to backfill into the `Draft` table. The draft / preview / scheduling workflow is available immediately for new edits.
- **One-way.** The data step's reverse is a no-op (`migrations.RunPython.noop`) — rolling the migration back restores the columns but not their values. Restore from your backup if you need to revert.
- **Custom page models** are handled automatically — the transform runs against every model that carries both the old `status` and new `published_at` columns at migration time.
