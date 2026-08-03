---
paths:
  - "tests/**"
  - "**/conftest.py"
  - "**/pyproject.toml"
---

# Testing

pytest (+ pytest-asyncio / pytest-cov). Prefer the narrowest run that covers the change:
`uv run pytest tests/test_base.py` or `uv run pytest path::test_name` over the full suite.

## Building the app under test

- **Always go through `create_app(settings)`**; it binds those settings to `Depends(get_settings)`. Never
  mutate the module-level `app` singleton, and never `importlib.reload(app.main)` - that rebinds the
  object other fixtures already captured, and the failure surfaces somewhere unrelated.
- **Build settings with `build_settings(**overrides)`** (`tests/conftest.py`). It uses `model_validate`, so
  neither the environment nor a local `.env` can influence a result.
- **Clear `get_settings.cache_clear()`** in any test that mutates settings or env - `get_settings()` is
  `@lru_cache(maxsize=1)`, so a stale entry leaks into every later test.
- `conftest.py` provides `settings`, `app`, `client` and `async_client`. The async one has to enter
  `app.router.lifespan_context` itself, because `ASGITransport` does not run the lifespan. Note the client
  is `httpx2`, not `httpx`.

## What to test

Trust boundaries - DTO validation, `CoreError` → HTTP mapping (see `backend/exceptions.md`), route status
codes and payloads. Prefer observable behaviour (status, JSON body) over private internals. Keep tests
deterministic, with no order dependence.

## Config that must not be undone

These `[tool.pytest.ini_options]` settings each exist because of a specific failure:

- **`testpaths = ["tests"]`** - without it a bare `pytest` walks the repo root and dies collecting
  unreadable directories such as `hooks/logs`.
- **`filterwarnings = ["error"]`** - a new DeprecationWarning fails the suite by design. Fix the cause; do
  not re-add `--disable-warnings`.
- **No `-q` in `addopts`.** pytest verbosity is additive, so `-q` (-1) cancels an explicit `-v` (+1) and
  leaves `-vv` as the only route to verbose output. Default verbosity plus `-ra` already gives per-file
  progress and a summary of everything that did not pass.
- **No coverage in `addopts`** - it slows the inner loop and hard-fails wherever `.coverage` / `htmlcov/`
  are not writable, such as a sandboxed agent. Use `make test-cov` when you want it.

Coverage is **100 % statements and branches**. Genuinely unreachable defensive code gets
`# pragma: no branch` / `# pragma: no cover` *with a comment saying why* - never to hide untested
reachable code.

## Discipline

When you change a DTO, enum, or route contract, update the asserting tests in the **same** change.
Weakening source or skipping a test to reach green is covered by [guardrails.md](../core/guardrails.md).
