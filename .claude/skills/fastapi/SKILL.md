---
name: fastapi
description: FastAPI best practices for this api-template. Use when writing or reviewing FastAPI routes, dependencies, or OpenAPI models. Prefer Annotated params, thin handlers, and Pydantic DTOs under app/dtos/.
---

# FastAPI (project skill)

Follow `.claude/rules/backend/fastapi-routes.md` and the Cursor skill at `.cursor/skills/fastapi/SKILL.md` when available.

## Essentials for this repo

- Validate path/query/body with `Annotated[..., Path|Query|Body]` or request models — never leave API inputs loosely typed.
- Return DTOs from `app/dtos/`; keep handlers thin; use `Depends` + `get_settings` from `app/core/config.py`.
- Raise `CoreError` subclasses for domain failures.
- Prefer Context7 / `docs-researcher` for version-sensitive FastAPI API questions over training memory.
- Finish with `make check` and affected pytest modules.
