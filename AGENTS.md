# api-template Agent Instructions

Lean always-on map for Cursor and Claude Code. Path-specific conventions live in `.cursor/rules/` and `.claude/rules/` and load when you touch a matching file. Deep FastAPI/Pydantic guidance lives in skills under `.cursor/skills/` / `.claude/skills/`. Harness layout: `core/harness`.

## Repo map

`app/` is layered by technical type, not by feature. Read the tree rather than a copy of it; the parts that are not self-evident:

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

Env (see `app/core/config.py`): field names map to env vars case-insensitively, so **no aliases** - only `name` has one (`APP_NAME`).

**`ENVIRONMENT=production` fails closed**: startup raises unless `ALLOWED_ORIGINS` and `ALLOWED_HOSTS` are explicit (not `*`) and `API_KEY` is set; docs/OpenAPI default to off.

## Essential commands

`make help` lists every target. The ones whose behaviour you cannot guess:

| Command | Purpose |
|---------|---------|
| `make ci` | Ruff format + ty. **Mutates** (`ruff format .`, `ruff check --fix`) and runs **no tests** - run `make test` separately |
| `make ci-check` | The non-mutating mirror of CI's `test` job: format check + lint + ty + pytest + the requirements gate. Use this to predict CI; `make ci` cannot fail on formatting drift |
| `make lock` / `make update` | The only way `uv.lock` may change |
| `make check-requirements` | Fails if `requirements.txt` has drifted from `uv.lock`. A CI gate, because that export - not `uv.lock` - is what GitHub's dependency graph reads |
| `make dev` / `make prod` | Dev server on 8000 (`fastapi dev`) / prod on 8001 (`uvicorn`, as the container runs it but bound to loopback, not `0.0.0.0`) |
| `make docker-run-dev` | Dev stack with Compose watch (8000). Compose is dev-only; prod is k8s |
| `make docker-check-build` / `make docker-config` | The Docker gates CI runs locally too - build checks, Compose validation. CI adds one more that is deliberately not a `make` target: `.github/actions/verify-base-digests` (hits a registry, so it stays out of the inner loop) |

## Critical gotchas

- **CORS** defaults to allow-all origins for local template use - **restrict in production**.
- **aiocache alias config takes no `maxsize`** - `SimpleMemoryCache` rejects it, and `set_config()` only stores the dict, so a bad key raises `TypeError` lazily on the first `caches.get("default")` (i.e. as a 500 inside a route). TTL is the only eviction this backend has.
- **Outbound HTTP** uses a shared lifespan-scoped `httpx2.AsyncClient` on `app.state.http_client` (`app/core/http_client.py`); inject via `Depends(get_http_client)`. Never create per-request clients.
- **Logfire** send/plugin flags stay off via Makefile / Docker / CI unless explicitly enabled.
- **Compose is local dev only** - one `compose.yaml`, `reload` target, port 8000. Production runs on Kubernetes, so nothing here is a deployment descriptor: the hardened `runtime` image is proven by CI's smoke step (`.github/actions/smoke-test-image`) and the production posture belongs in the k8s manifests. Do not add a second Compose file or an override to model production. See `ops/compose`.
- **`# type: ignore` suppresses nothing** - ty only honours `# ty: ignore[rule-name]`, and a bare `# ty: ignore` is an error.
- **Worktrees carry no `.env`**, share the main `.venv` by symlink (so never run `uv sync` / `make sync` inside one), and see only `worktree.sparsePaths` - which excludes `.cursor` and `.github`, so a worktree-isolated agent cannot complete a dual-tree or CI-touching change. Reasons and the full list: `core/harness`.

## API surface (template)

Every error returns one `ErrorResponse` envelope; `details` is withheld on 5xx - see `contracts/pydantic-dtos`. Route, probe and auth detail lives in `backend/fastapi-routes`.

## Finish gate

`make ci` for Ruff + ty, plus the narrowest relevant tests when behaviour changes. Before opening a PR, `make ci-check` instead - it is the same command list as CI's `test` job and, unlike `make ci`, it cannot pass on formatting drift. Do not silence a failure - see `core/guardrails`.

## Contribution

Update this file only for always-relevant facts; domain detail belongs in a rule or a skill.

**Rules are a dual tree.** Every `.claude/rules/**/*.md` has a `.cursor/rules/**/*.mdc` twin at the same relative path with the same intent. Change both in one edit; the frontmatter dialects differ and do not transfer (Claude Code: `paths:` only. Cursor: `description:` + `globs:` + `alwaysApply:`). The mechanics that decide whether a harness change does what it looks like it does - subagent privilege, the load model, worktree sparse paths - are in `core/harness`.

**Markdown is soft-wrapped.** One line per paragraph or list item - never break a paragraph across lines to hit a column. `.vscode/settings.json` turns on `editor.wordWrap` for Markdown; let the editor wrap. Badge rows and other standalone link lines stay one per line.
