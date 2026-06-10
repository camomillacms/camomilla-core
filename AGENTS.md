# AGENTS.md

Camomilla is a Django-based headless CMS (v6.x): REST APIs, media handling, multilingual support via `modeltranslation`, and a flexible `AbstractPage` system with URL routing. Supports Django 4.2–5.2 and Python 3.10–3.14.

This file is the **canonical, tool-agnostic guide** for AI coding agents (and humans) working in this repo. Most agentic tools read it automatically (Cursor, OpenAI Codex, Aider, Gemini CLI, GitHub Copilot, Zed, …). The per-tool entry points — [`CLAUDE.md`](./CLAUDE.md) and [`.github/copilot-instructions.md`](./.github/copilot-instructions.md) — are **thin adapters that defer here**. Keep the substance in this file so there's a single source of truth.

## Dev commands

```bash
make install          # install deps with uv (uv sync --dev)
make test             # flake8 camomilla + pytest (with coverage)
make format           # black .
make lint             # flake8 camomilla
make migrations       # generate Django migrations for the camomilla app
```

## Run the example app (manual testing)

The repo ships a runnable demo project under `example/` (it's also the test project). `manage.py` at the repo root uses `example.camomilla_example.settings`.

```bash
uv run python manage.py migrate
uv run python manage.py seed_demo --reset   # demo pages/articles/menus/drafts + an admin/admin user
uv run python manage.py runserver
# Admin:  http://localhost:8000/admin/                          (admin / admin)
# API:    http://localhost:8000/api/camomilla/pages-router/about
# Docs:   `make docs-dev` (VitePress)
```

## Conventions

- **Commits:** Conventional Commits — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- **Formatting / linting:** `black` for formatting; `flake8 camomilla` for linting (`max-line-length = 160`).
- **New endpoints:** extend `BaseModelSerializer` + `BaseModelViewset` (and `AbstractPageMixin` for page-like models).
- **Tests:** `pytest`, typically `@pytest.mark.django_db(transaction=True, reset_sequences=True)`. Test settings: `example/camomilla_example/settings.py`.

## Repository map

```
camomilla/
├── models/              # AbstractPage/Page, Draft, Media, Article, Menu, Content (+ UrlNode, UrlRedirect)
├── serializers/         # DRF serializers — base/ (BaseModelSerializer, mixin composition), mixins/, fields/
├── views/               # DRF viewsets — base/ (BaseModelViewset), mixins/, pages.py (pages_router + pages_router_preview), decorators.py
├── managers/            # PageQuerySet, UrlNodeManager (DraftQuerySet lives in models/draft.py)
├── templatetags/        # menus (render_menu / node_url), camomilla_filters (localized_url)
├── templates_context/   # page context injection (@register)
├── types.py             # Permalink / LinkTypes — typed template_data link primitive
├── translation.py       # modeltranslation registrations for core models
├── urls.py              # API router (also mounts the external structured_metaobjects viewsets)
├── dynamic_pages_urls.py# HTML page render route (catch-all)
├── settings.py · permissions.py · preview.py · sitemap.py · redirects.py · model_api.py · apps.py
└── theme/ · storages/ · fields/ · openapi/ · utils/ · management/commands/
example/                 # runnable demo + test project (settings, website app, seed_demo command)
tests/                   # pytest suite (plus example/website/test_*.py)
docs/                    # VitePress documentation site (publishes llms.txt for AI tools)
```

## Gotchas (read before touching these areas)

- **Lifecycle status is derived, not a DB column** (computed from `published_at` + `deleted_at` + the `Draft` table). `Page.objects.filter(status="PUB")` / `.exclude(status="TRS")` / `.filter(is_public=True)` still work — the manager rewrites those lookups into timestamp conditions (`PageQuerySet._filter_or_exclude`). The explicit helpers `.public()` / `.draft()` / `.scheduled()` / `.trashed()` are the canonical equivalents; for `order_by` / `values("status")` use `.with_lifecycle()` (the `computed_status` annotation).
- **Meta Models are external.** They live in the `django-structured-metaobjects` package, not in `camomilla/` — there is no `camomilla/meta/`. Camomilla only mounts its viewsets in `camomilla/urls.py`.
- **URL localization in `template_data` is type-driven** via `camomilla.types.Permalink` — do not add a serializer JSON-tree walk to rewrite links.
- **Translatable columns are dynamic** (`title_en`, `permalink_it`, …). Use `camomilla.utils.set_nofallbacks` / `get_nofallbacks` (or `getattr(obj, f"{field}_{lang}")`) rather than hand-built attribute strings.
- **Camomilla has its own migrations dir** injected via `MIGRATION_MODULES` (`camomilla_migrations/`) — generate with `make migrations`.

## Deep references

Two curated knowledge bases. **They are plain Markdown** — open them with any agent or editor. (Claude Code additionally auto-loads them as Skills; no other tool needs to.)

| When you are… | Read |
|---|---|
| **Using** camomilla as a dependency in your own project | [`.claude/skills/camomilla-usage/SKILL.md`](./.claude/skills/camomilla-usage/SKILL.md) + the [docs site](https://camomillacms.github.io/camomilla-core/) (machine-readable: [`/llms.txt`](https://camomillacms.github.io/camomilla-core/llms.txt)) |
| **Contributing** to camomilla's own source | [`.claude/skills/camomilla-internal-architecture/SKILL.md`](./.claude/skills/camomilla-internal-architecture/SKILL.md) |

Rule of thumb: editing `camomilla/...` → the internal-architecture reference; building a downstream `myapp/...` → the usage reference.

## Using your agent of choice

- **Most tools** auto-detect this `AGENTS.md` — nothing to configure.
- **Claude Code** reads `CLAUDE.md` (which imports this file) and auto-loads the two skills.
- **GitHub Copilot** reads `.github/copilot-instructions.md` (which points here).
- **Anything else** (Cursor / Codex / Aider / Gemini CLI / Zed): point it at `AGENTS.md` if it isn't picked up automatically.
