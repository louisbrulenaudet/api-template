---
name: review-checklist
description: Enumerated review checklist for this api-template - the diff-level checks that map to .cursor/rules/. Use when reviewing a diff or auditing files for rule conformance; the criteria for the code-reviewer and security-reviewer agents.
---

# Review checklist (project skill)

The rule files under `.cursor/rules/` are the authority. This is the **traversal order** for reviewing a diff against them, plus the diff-level signals that indicate a violation. It does not restate the rules - open the cited file when a call is close.

The Claude twin lives at `.claude/skills/review-checklist/SKILL.md` - keep the two in sync.

## How to report

Cite the governing rule file for every finding. **If no rule governs it, it is not a finding** - say nothing rather than padding. Silence on an area is a valid result.

**Rank a `**Nothing enforces this:**` violation above everything else.** That marker in a rule means the invariant is fail-open: breaking it leaves every gate green, so a review is the only thing standing between the change and production. `grep -rn 'Nothing enforces this' .cursor/rules/` is the whole set. Anything CI already fails on is a lower-value finding - the build will say so without you.

---

## 1. Guardrails - `core/guardrails.mdc` (always-on, highest severity)

- A suppression added to clear a failure: `# noqa`, `# ty: ignore[...]`, `Any`, a skipped or deleted test, a relaxed assertion, a disabled Ruff rule, a loosened CI step. A suppression needs a stated reason in a comment; one that appears in the same diff as the error it silences is a **Critical** finding.
- `# type: ignore` suppresses nothing here - ty only honours `# ty: ignore[rule-name]`, and a bare `# ty: ignore` is an error. Either form is a finding.
- A hand-edit to `uv.lock`, or to any generated artifact, instead of regenerating it (`make lock`).
- Scope drift: a diff described as config/docs/rules that also touches `app/`, Docker, or CI.
- A duplicated DTO or `ErrorCodes` member instead of an import.
- Any new surface that creates, rotates, or deletes a long-lived credential on a caller's behalf.

## 2. Layering - `backend/services.mdc`

- Logic that belongs in `app/services/`: a branch beyond input validation, a write or side effect, orchestration of more than one dependency or I/O call, or logic worth testing without HTTP.
- Business logic placed in `app/core/`. `core/` is cross-cutting infrastructure only (settings, the shared HTTP client).
- A service touching `Request` / `Response` - services are transport-agnostic.
- A service raising `HTTPException` instead of a `CoreError` subclass.
- An anemic pass-through service that only forwards its arguments.
- A relative import, or importing a module rather than the specific callable.

## 3. Routes and DTOs - `backend/fastapi-routes.mdc`, `contracts/pydantic-dtos.mdc`

- A handler doing more than validate, resolve dependencies, and shape one value into a DTO.
- An unvalidated boundary: a raw `dict`, a bare `str`, or an untyped body/query where a DTO belongs.
- A wire shape defined inline in a handler instead of in `app/dtos/`.
- A per-request `httpx2.AsyncClient` instead of `Depends(get_http_client)`.
- A DTO field whose type or optionality changed without the asserting test changing in the same diff.

## 4. Errors - `backend/exceptions.mdc`

- A new failure mode raising something other than a `CoreError` subclass.
- A new error without a corresponding `ErrorCodes` member, or a duplicated member.
- A handler or DTO that could put internals into the client-facing envelope: stack traces, SQL, file paths, upstream response bodies. `details` must stay withheld on 5xx.

## 5. Style and naming - `quality/python-style.mdc`

Ruff owns format, line length, quotes, import grouping and PEP 8 naming - **do not report what Ruff already enforces.** Report only the rules a linter cannot see:

- A dropped coroutine: an async call neither awaited nor returned to the caller.
- A relative import (`from .x import y`) - `app.*` absolute only.
- Contract naming: `{Name}Response` / `{Name}Request` in `app/dtos/`; `{Name}Error` subclassing `CoreError` in `app/exceptions/`; enum members `UPPER_SNAKE_CASE` on a `PascalCase` class; settings fields matching the env var they read.
- A new markdown, rule, or hook filename that is not `kebab-case`.

## 6. Tests - `quality/testing.mdc`

- A DTO, enum, or route contract change with no test update **in the same diff**.
- An app built without `create_app(settings)`, a mutated module-level `app`, or `importlib.reload(app.main)`.
- Settings built with `Settings(...)` instead of `build_settings(**overrides)` - the constructor consults the environment and a local `.env`.
- A test that mutates settings or env without `get_settings.cache_clear()`.
- `addopts` gaining `-q`, coverage, or `--disable-warnings`; `filterwarnings = ["error"]` relaxed; `testpaths` removed.
- A `# pragma: no cover` / `no branch` without a comment saying why, or used on reachable code. Coverage is 100 % statements **and** branches.
- Order-dependent or non-deterministic tests.

## 7. Config and settings - `backend/settings-config.mdc`

- A new setting that is not on the frozen `Settings` model, or a secret not typed `SecretStr`.
- An alias added where case-insensitive env mapping already works (only `name` has one, `APP_NAME`).
- A production check weakened: wildcard `ALLOWED_ORIGINS` / `ALLOWED_HOSTS` or an empty `API_KEY` must still raise under `ENVIRONMENT=production`; docs/OpenAPI must default off.
- `.env.template` not updated when a new required variable landed.

## 8. Ops - `ops/dockerfile.mdc`, `ops/compose.mdc`, `ops/ci.mdc`, `ops/composite-actions.mdc`

- A new `COPY` path in the Dockerfile without a matching `!` entry in `.dockerignore` - the build context is an allowlist. Remember `.dockerignore` does not read `.gitignore`, so gitignored editor/OS metadata under `app/` still needs its own re-exclusion.
- Dev (8000) / container (8001) port or healthcheck parity broken.
- A secret baked into an image layer or a build arg.
- CI losing `uv sync --frozen`, or the pinned uv version drifting between its three homes: the `ghcr.io/astral-sh/uv:` `FROM` line, `setup-uv`'s `version:` input in `ci.yml`, and `[tool.uv] required-version`. Dependabot moves only the first; the other two are manual.
- A base image ref that has lost its Debian codename (`3.14-slim` instead of `3.14-slim-trixie`, where the suite-less tag is an alias that carries an OS major upgrade silently) or its `@sha256:` digest.
- A dev-group package reaching the `runtime` venv - `fastapi-cli` back in `[project] dependencies`, or `fastapi[standard]` pulling it in transitively. The smoke test asserts the CLI's absence. `fastapi[standard]` also re-adds `jinja2`, dropped deliberately. Do not prune `python-multipart` the same way, though: it looks unused but `starlette.requests` imports it unconditionally, so `import fastapi` fails without it. Prove a dependency is dead by blocking it on `sys.meta_path` and serving a request, not by grepping `app/`.
- `builder-dev` widened from `--no-dev --group devserver` to a bare `uv sync`: the full `dev` group pulls `pre-commit-uv`, which depends on the `uv` PyPI package, so that puts an installer into the dev image.
- `requirements.txt` not regenerated after `make lock` - it is an export of the **runtime** closure (`make export-requirements` passes `--no-dev`), and a stale one is a second, contradictory manifest.

---

## Out of scope for this checklist

Semantic bug-hunting (logic errors, race conditions, edge cases) and end-to-end behaviour verification are separate passes. Do not duplicate them here - a reviewer prompted to find problems will invent them, and over-reporting trains the reader to ignore the report.
