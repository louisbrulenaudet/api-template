---
name: pydantic-best-practices
description: Pydantic v2 performance and contract practices for this api-template. Use when writing or reviewing models under app/dtos/ or Settings in app/core/config.py.
---

# Pydantic (project skill)

Follow `.claude/rules/contracts/pydantic-dtos.md` and the Cursor skill at `.cursor/skills/pydantic-best-practices/SKILL.md` when available.

## Essentials for this repo

- One owner per wire shape under `app/dtos/` / `app/enums/` — no duplicate mirrors.
- No business logic in DTO modules; keep Field descriptions OpenAPI-friendly and client-safe.
- Prefer `model_validate` / reuse adapters as in the Cursor skill; avoid slow validator anti-patterns.
- Settings stay in `app/core/config.py`; never commit real secrets — sync `.env.template` only.
- Use `docs-researcher` / Context7 for version-sensitive Pydantic questions.
