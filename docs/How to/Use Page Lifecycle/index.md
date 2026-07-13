# 🌱 Use Page Lifecycle

Camomilla pages have a **derived lifecycle** plus a dedicated drafting and scheduling workflow: edit without touching the live site, preview pending changes, plan content swaps for a future moment, and (optionally) keep a full revision history.

There is **no `status` column**. A page's lifecycle state is computed from two timestamps — `published_at` (translatable: when *this language* goes live) and `deleted_at` (global: soft-delete) — combined with the separate `Draft` table for pending edits.

## 🚦 Lifecycle states

| State | Code | When |
|---|---|---|
| Published | `PUB` | `deleted_at` is null **and** `published_at <= now()` for the active language |
| Draft | `DRF` | `deleted_at` is null **and** `published_at` is null |
| Planned | `PLA` | `deleted_at` is null **and** `published_at > now()` (first publish scheduled for the future) |
| Trashed | `TRS` | `deleted_at` is set (applies to **every** language at once) |

You read the state from a page instance:

```python
page.status      # "PUB" / "DRF" / "PLA" / "TRS" (for the active language)
page.is_public   # True only when status == "PUB"
```

`published_at` is **per-language**: a page can be live in Italian and still a draft in English. `deleted_at` is **global**: trashing hides every language.

## 👀 Public vs. preview

Every public surface serves only the **public** state of a page. Trashed, draft, and planned pages return `404` everywhere:

- **HTML render route** (`dynamic_pages_urls`)
- **JSON router** — `GET /api/camomilla/pages-router/<page_url>`

To look at unpublished content, authenticated editors use the **preview** surfaces, which bypass the public gate and overlay any pending draft:

| Surface | What it serves |
|---|---|
| `GET /api/camomilla/pages-router-preview/<page_url>` | JSON, by URL — the mirror of `pages-router` for headless frontends |
| `GET /api/camomilla/pages/{id}/preview/` | JSON, by id — live page + draft overlay merged per language |
| `GET /api/camomilla/pages/{id}/render/` | HTML, by id — renders the page template with `draft_data` in context |

::: tip Headless preview
`pages-router-preview` returns the same payload shape as `pages-router`, so a headless frontend can resolve a page by URL for preview with a single request — no list-then-detail round trip. The [Astro integration](../Use%20Astro%20Integration/README.md) speaks this endpoint directly — use **`@camomillacms/astro-integration` ≥ 0.7** with camomilla 6.5.
:::

## ✏️ Drafts

A **draft** is a staged future state of a page, stored in a dedicated `Draft` table — **one pending draft per page, per language**. The draft body is shaped like a partial `PATCH` on the page; publishing replays it onto the live row.

The presence of a draft does **not** change the page's lifecycle label — a published page with a pending draft is still `PUB`. Observe drafts explicitly:

```python
page.has_draft            # a pending draft exists for the active language
page.has_scheduled_draft  # …and it has a scheduled_for moment
page.draft_data           # the pending draft payload (dict), or {}
```

### Editor API actions

All page-lifecycle actions live on the standard pages viewset and require staff authentication.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/camomilla/pages/{id}/draft/` | `PATCH` / `PUT` | Save the active-language draft. `PATCH` merges into the existing payload; `PUT` replaces it wholesale. |
| `/api/camomilla/pages/{id}/discard-draft/` | `POST` | Delete the active-language draft row. |
| `/api/camomilla/pages/{id}/publish/` | `POST` | Apply the active-language draft (if any) and stamp `published_at = now()`. Optional body `{"comment": "…"}`. |
| `/api/camomilla/pages/{id}/schedule/` | `POST` | Body `{"publish_at": "<ISO 8601>"}` — see [Scheduling](#⏰-scheduling). |
| `/api/camomilla/pages/{id}/preview/` | `GET` | Author-only JSON: live page + draft overlay. |
| `/api/camomilla/pages/{id}/render/` | `GET` | Author-only HTML: page template rendered with `draft_data`. |
| `/api/camomilla/pages/{id}/revisions/` | `GET` | List revision snapshots (see [Revisions](#🕰️-revisions-optional)). |
| `/api/camomilla/pages/{id}/revert/{version_id}/` | `POST` | Roll back to a revision. |

::: warning Drafts are per active language
The draft endpoints always act on the **active language** (resolved from the request the same way the rest of camomilla resolves it). A payload that carries both `translations.en` and `translations.it` lands wholesale in the active language's draft row, and publishing that language applies only what its row carries.
:::

## ⏰ Scheduling

Schedule a publish moment with `POST /api/camomilla/pages/{id}/schedule/` and a body of `{"publish_at": "<ISO 8601 datetime>"}`. The behavior depends on whether the active language has ever been public:

- **Never public** (`published_at` is null) → sets `published_at = publish_at`. The page becomes `PLA` (Planned) and the **live row itself** is what appears at that moment. No draft required.
- **Already public** → attaches `scheduled_for = publish_at` to the existing draft (save it first via `/draft/`). The live content stays visible until the moment passes, then the draft's payload swaps in.

### Lazy materialization

When a scheduled moment passes, the swap happens **lazily on first read**: the first public visitor of that page (HTML or JSON router) applies the due draft, refreshes the page, and serves the new content. Concurrent readers see the page already flipped. No background worker is strictly required for pages that get traffic.

### Cron safety net — `camomilla_publish_scheduled`

For pages that nobody visits, run the management command on a schedule (cron, Celery beat, systemd timer):

```bash
python manage.py camomilla_publish_scheduled

# preview what would be published without changing anything
python manage.py camomilla_publish_scheduled --dry-run
```

It applies every draft whose `scheduled_for` moment has passed, activating the right language for each so the `published_at` stamp lands in the correct per-language column. Idempotent and safe to run frequently.

## 🗑️ Trashing and per-language dismiss

Trashing is a **global** soft-delete — it hides every language and is reversible:

```python
page.trash()    # soft-delete: deleted_at = now(); status becomes "TRS"
page.restore()  # undo: deleted_at = None; status returns to whatever the timestamps describe
```

To dismiss (`404`) **only one language** without touching the others, clear that language's `published_at` — it's translatable:

```python
from camomilla.utils import set_nofallbacks

# 404 the English page, keep Italian (and any other language) live
set_nofallbacks(page, "published_at", None, language="en")
page.save()
```

`deleted_at` is intentionally **not** translatable: there is no "trash only one language" — use the per-language `published_at` for that.

## 🕰️ Revisions (optional)

Revision history is powered by [`django-reversion`](https://django-reversion.readthedocs.io/) and is **opt-in**. When enabled, `publish()`, scheduled publishes, and reverts all create revision snapshots, and the `/revisions/` and `/revert/{version_id}/` endpoints become functional. Without it, those two endpoints return `501 Not Implemented` and the rest of the lifecycle works unchanged.

To enable it:

```python
# settings.py
INSTALLED_APPS = [
    # …
    "reversion",
]
```

```bash
python manage.py migrate
```

Camomilla auto-registers every concrete `AbstractPage` model with reversion at startup — you don't need to register your page models by hand.

## 🔎 QuerySet helpers

`Page.objects` (and any `AbstractPage` manager) expose lifecycle-aware filters. All of them respect the active language for `published_at`:

```python
Page.objects.public()                # deleted_at IS NULL AND published_at <= now()
Page.objects.alive()                 # deleted_at IS NULL
Page.objects.trashed()               # deleted_at IS NOT NULL
Page.objects.draft()                 # has any pending Draft (any language)
Page.objects.scheduled()             # has a scheduled Draft OR published_at > now()
Page.objects.due_for_publish()       # has a Draft with scheduled_for <= now()
Page.objects.first_publish_pending() # never-public with a future published_at
Page.objects.with_lifecycle()        # annotates the computed status for ORDER BY / .values()
```

## 🧰 Programmatic API

Every editor action has a model-level counterpart, handy for data migrations, management commands, and tests:

```python
page.save_draft({"translations": {"en": {"title": "edited"}}})  # stage an edit (active language)
page.save_draft({"title": "edited"}, scheduled_for=when)        # stage and schedule the swap
page.discard_draft()                                            # delete the draft row
page.publish(comment="Editor approved")                         # apply draft + mark live
page.schedule(when)                                             # schedule (see semantics above)
page.trash()                                                    # soft-delete (global)
page.restore()                                                  # undo trash
page.list_revisions()                                           # reversion history (if enabled)
page.revert_to_revision(version_id)                             # rollback (if enabled)
```
