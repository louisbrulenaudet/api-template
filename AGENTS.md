# api-template Agent Instructions

Lean always-on map for Cursor and Claude Code. Path-specific conventions live in `.cursor/rules/` and
`.claude/rules/` and load when you touch a matching file. Deep FastAPI/Pydantic guidance lives in skills
under `.cursor/skills/` / `.claude/skills/`. Harness layout: `.cursor/rules/core/harness.mdc`.

## Repo map

`app/` is layered by technical type, not by feature. Read the tree rather than a copy of it; the parts
that are not self-evident:

- `app/main.py` - `create_app()` factory; middleware + exception-handler wiring; lifespan
- `app/middlewares/` - `configure_middleware()`; order is load-bearing (see the middleware rule)
- `app/exceptions/` - `CoreError` subclasses + `handlers.py` (`register_exception_handlers`)
- `app/dtos/`, `app/enums/` - the only wire contracts; `ErrorCodes` + `Environment` live in `enums/`
- `hooks/` - shared Cursor + Claude agent hooks, **not** human git hooks (has its own `AGENTS.md`)

## Setup

```sh
make sync                          # uv sync --frozen - installs uv.lock as-is; dev group included (matches CI)
cp .env.template .env              # fill API_KEY, API_CLIENT, …
make dev                           # http://localhost:8000 - ping: /api/v1/ping
```

Env (see `app/core/config.py`): field names map to env vars case-insensitively, so **no aliases** - only
`name` has one (`APP_NAME`).

**`ENVIRONMENT=production` fails closed**: startup raises unless `ALLOWED_ORIGINS` and `ALLOWED_HOSTS`
are explicit (not `*`) and `API_KEY` is set; docs/OpenAPI default to off.

## Essential commands

`make help` lists every target. The ones whose behaviour you cannot guess:

| Command | Purpose |
|---------|---------|
| `make ci` | Ruff format + ty. **No tests** - run `make test` separately |
| `make lock` / `make update` | The only way `uv.lock` may change |
| `make dev` / `make prod` | Dev server on 8000 / prod on 8001 |

## Critical gotchas

- **CORS** defaults to allow-all origins for local template use - **restrict in production**.
- **aiocache alias config takes no `maxsize`** - `SimpleMemoryCache` rejects it, and `set_config()` only
  stores the dict, so a bad key raises `TypeError` lazily on the first `caches.get("default")` (i.e. as a
  500 inside a route). TTL is the only eviction this backend has.
- **Outbound HTTP** uses a shared lifespan-scoped `httpx2.AsyncClient` on `app.state.http_client`
  (`app/core/http_client.py`); inject via `Depends(get_http_client)`. Never create per-request clients.
- **Logfire** send/plugin flags stay off via Makefile / Docker / CI unless explicitly enabled.
- **`# type: ignore` suppresses nothing** - ty only honours `# ty: ignore[rule-name]`, and a bare
  `# ty: ignore` is an error.
- **Worktrees carry no `.env`.** `.worktreeinclude` deliberately omits it: a subagent worktree that made
  any change persists until a sweep older than `cleanupPeriodDays` (20), so a listed secret would sit in
  plaintext under `.claude/worktrees/` for weeks. Tests do not need it (`tests/conftest.py` uses
  `model_validate`); only `make dev` / `make prod` do - copy it in by hand for those. Worktrees branch
  from local `HEAD` (`worktree.baseRef: "head"`) and share the main `.venv` by symlink, so never run
  `uv sync` / `make sync` inside one.

## API surface (template)

Every error returns one `ErrorResponse` envelope; `details` is withheld on 5xx - see
`contracts/pydantic-dtos`. Route, probe and auth detail lives in `backend/fastapi-routes`.

## Finish gate

`make ci` for Ruff + ty, plus the narrowest relevant tests when behaviour changes. Do not silence a
failure - see `core/guardrails`.

## Contribution

Update this file only for always-relevant facts; domain detail belongs in a rule or a skill.

**Rules are a dual tree.** Every `.claude/rules/**/*.md` has a `.cursor/rules/**/*.mdc` twin with the same
basename and the same intent. Change both in one edit; the frontmatter dialects differ and do not transfer
(Claude Code: `paths:` only. Cursor: `description:` + `globs:` + `alwaysApply:`).
