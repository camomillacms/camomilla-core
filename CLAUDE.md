# Camomilla CMS — Claude Code entry point

The canonical, tool-agnostic agent guide for this repo is **[AGENTS.md](./AGENTS.md)**. It is imported below — keep all shared instructions there, not here, so every agentic tool stays in sync.

@AGENTS.md

## Claude-specific

This repo ships two Claude Code skills under `.claude/skills/` — they load automatically:

- `/camomilla-usage` — using camomilla as a library (setup, REST API, pages, lifecycle/drafts/preview, media, menus, translations, settings).
- `/camomilla-internal-architecture` — contributing to camomilla's own source (architecture, conventions, testing).

These are the "Deep references" listed in AGENTS.md; Claude exposes them as invokable skills, but they are plain Markdown any tool can read.
