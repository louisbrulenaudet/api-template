# api-template Agent Instructions

Lean always-on map for Cursor and Claude Code. Path-specific conventions live in `.cursor/rules/` and `.claude/rules/` — load those when editing matching files. Deep FastAPI/Pydantic guidance lives in skills under `.cursor/skills/` / `.claude/skills/`.

## Overview

Minimal production-ready **FastAPI** template: strict **Pydantic** validation, **Docker** containerization, optional **Cloudflare Tunnel**. Python 3.14+, uv, Ruff, pytest.

## Repo map

```
app/
  api/v1/endpoints/   # HTTP routes (thin handlers)
  core/               # Settings + shared httpx2 AsyncClient
  dtos/               # Wire DTOs (ping_response.py, health_response.py, …)
  enums/              # ErrorCodes
  exceptions/         # CoreError subclasses
  utils/              # retry / async_retry
  main.py             # App, middleware, CoreError handler
tests/                # pytest
make/                 # Makefile fragments (dev, docker, help, variables)
hooks/                # Shared Cursor + Claude agent hooks (not human git hooks)
```

Path rules: `backend/fastapi-routes`, `contracts/pydantic-dtos`, `quality/*`, `ops/docker`, `ops/ci`, plus always-on `core/guardrails`.

## Setup

```sh
make sync                          # uv sync --locked --extra dev (same idea as CI)
cp .env.template .env              # fill API_KEY, API_CLIENT, …
make dev                           # http://localhost:8000 — ping: /api/v1/ping
```

Required env (see `app/core/config.py`): `APP_NAME` (default `Backend`), `API_KEY`, `API_CLIENT`.

## Essential commands

| Command | Purpose |
|---------|---------|
| `make sync` / `make install` | Sync `.venv` from `uv.lock` (+ dev extra) |
| `make lock` / `make update` | Lock / upgrade dependencies |
| `make dev` / `make prod` | Dev (8000) / prod (8001) servers |
| `make check` / `make format` | Ruff lint / format (+ `--fix` on format) |
| `make type-check` | Ty |
| `make test` | pytest + coverage |
| `make ci` | Local gate: `format` (Ruff) + `type-check` (ty); no tests |
| `make pre-commit` | pre-commit all files |
| `make docker-*` | See `make/docker.mk` / `make help` |

## Critical gotchas

- **CORS** defaults to allow-all origins for local template use — **restrict in production**.
- **`get_settings()`** is `@lru_cache(maxsize=1)`. Tests that change env must call `get_settings.cache_clear()`.
- **`lru_cache`** only on `get_settings()`; use **aiocache** for async TTL caches (configured in app lifespan).
- **Outbound HTTP** uses a shared lifespan-scoped `httpx2.AsyncClient` on `app.state.http_client` (`app/core/http_client.py`); inject via `Depends(get_http_client)`. Do not create per-request clients.
- **Docker build context** is an allowlist in `.dockerignore` (`*` then `!pyproject.toml`, `!uv.lock`, `!app/`). New `COPY` paths need a matching `!` entry.
- **Do not hand-edit `uv.lock`** — use `make lock` / `uv lock`.
- **Logfire** send/plugin flags stay off via Makefile / Docker / CI unless explicitly enabled.
- **Never commit `.env`**, keys, or credentials. Agent hooks block secret staging/reads and destructive git when wired.
- Prefer **`CoreError`** subclasses + `ErrorCodes` for domain failures; DTO modules hold shapes only.

## API surface (template)

- `GET /api/v1/ping` → `PingResponse`
- `GET /api/v1/health` → `HealthResponse`

## Agent harness

| Tool | Entry | Path rules | Hooks / MCP | Shared scripts |
|------|-------|------------|-------------|----------------|
| Cursor | this file | `.cursor/rules/**/*.mdc` | `.cursor/hooks.json`, `.cursor/mcp.json` (Context7) | `hooks/` |
| Claude Code | `CLAUDE.md` → `@AGENTS.md` | `.claude/rules/**/*.md` | `.claude/settings.json`, `.mcp.json` (Context7) | `hooks/` |

Subagents: `.cursor/agents/` and `.claude/agents/` (`ci-verifier`, `test-runner`, `docs-researcher`). Slash review prompts: `.cursor/commands/`. Skills: `.cursor/skills/` and `.claude/skills/`.

Keep `.cursor/rules` and `.claude/rules` content in sync when changing conventions (dual trees, same intent).

### Context path hygiene

| Mechanism | Effect | Use for |
|-----------|--------|---------|
| `.cursorignore` | Blocks Agent, Tab, Inline Edit, `@` | Secrets + never-prompt paths (`.env`, keys, `.venv`, caches) |
| `.cursorindexingignore` | Index only; AI can still open | Heavy/generated noise (`htmlcov/`, `uv.lock`, build artifacts) |
| `.gitignore` | VCS + default Cursor index / Claude search | Standard ignore |
| Claude `permissions.deny` `Read(...)` | Excludes from discovery, search, and reads | Same noise/secrets for Claude Code |
| `.worktreeinclude` | Copies listed gitignored files into Claude worktrees | Local `.env` for worktree DX |

Do not put index-only noise in `.cursorignore` — that over-blocks the Agent. Optional Context7 API key stays in user MCP / local overlay — never commit it.

## Finish gate

Before considering work done: `make ci` for Ruff + ty, and run the narrowest relevant tests when behavior changes (`make test` or `uv run pytest …`). Do not silence lint/type/test failures — fix the cause (see `core/guardrails`).

## Contribution

- Follow path-scoped rules for the files you touch.
- Validate request/response data with Pydantic; keep handlers thin.
- Use Makefile targets for consistency with CI.
- Update this file only for always-relevant facts; put domain detail in rules or skills.
