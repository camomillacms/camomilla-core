# Camomilla — Copilot instructions

> This file intentionally just redirects. The canonical, tool-agnostic agent
> guide lives at **[`AGENTS.md`](../AGENTS.md)** in the repo root — read it
> first. (GitHub Copilot also reads `AGENTS.md` natively in recent versions.)
> Keeping the substance in one place avoids the per-tool drift this file used
> to suffer from.

Quick essentials (full detail + repo map + gotchas in `AGENTS.md`):

- Install: `make install` · Test: `make test` · Format: `make format` · Lint: `make lint` (`flake8 camomilla`, max-line-length 160).
- Run the demo: `uv run python manage.py seed_demo --reset && uv run python manage.py runserver`.
- Conventional Commits. New endpoints extend `BaseModelSerializer` + `BaseModelViewset` (+ `AbstractPageMixin` for pages).
- Deep references (plain Markdown): `.claude/skills/camomilla-usage/SKILL.md` (using camomilla) and `.claude/skills/camomilla-internal-architecture/SKILL.md` (contributing).

See [`AGENTS.md`](../AGENTS.md) for the full guide, including the "Gotchas" section every agent should read before editing lifecycle, Meta Models, or `template_data` URL handling.
