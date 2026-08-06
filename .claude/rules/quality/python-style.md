---
paths:
  - "app/**/*.py"
  - "tests/**/*.py"
---

# Python Style and Naming

Ruff owns format and lint via `[tool.ruff]` in `pyproject.toml` - do not fight the formatter. Line length, quote style, import grouping, function-size limits and PEP 8 naming are all configured there and enforced by the `N`, `I`, `ANN` and `PL` rulesets. Read the config when you need a value; a copy of it here would only go stale. The `PostToolUse` hook runs `ruff format` + `ruff check` after every edit, so you do not need to be told to run it.

## Not enforced by a linter - which is why these are written down

- **No floating work.** Always `await` an async call, or return the coroutine to the caller. A dropped coroutine fails silently at runtime, not at lint time.
- **Nothing enforces this:** **a type suppression must be `# ty: ignore[rule-name]`.** ty is the sole type checker and runs with `analysis.respect-type-ignore-comments = false`, so a mypy-style `# type: ignore` is just a comment - it silences nothing and no gate tells you. A bare `# ty: ignore` *is* an error (`blanket-ignore-comment`), as are stale or misspelled ones. Whether a suppression is justified at all is [guardrails.md](../core/guardrails.md); the config reasoning is [lint-and-types.md](lint-and-types.md).
- **Absolute imports from `app.*` only** (`ban-relative-imports = "all"`).
- **Prefer explicit over clever.** `max-statements`/`max-complexity` catch the extremes; taste covers the rest.
- **Names carry contract meaning**, so they are not free choices:
  - Response/request models: `{Name}Response` / `{Name}Request` (e.g. `PingResponse`) in `app/dtos/`.
  - Exception classes: `{Name}Error` subclassing `CoreError` in `app/exceptions/`.
  - Enum members: `UPPER_SNAKE_CASE` on a `PascalCase` class (e.g. `ErrorCodes.CLIENT_INITIALIZATION_ERROR`).
  - Settings fields must match the env var they read - see `backend/settings-config.md`.
  - **A module must not shadow a stdlib name** (Ruff `A005`), which is why `app/core/logging_config.py` is not `logging.py`. The rule fires for anything importing `app.core.*`, so the suffix is not cosmetic.
- **Markdown, rule and hook script filenames are `kebab-case`.**
- **`@wraps` on a decorator wrapper is required, not cosmetic.** Without it the wrapper exposes `(*args: P.args, **kwargs: P.kwargs)`, and FastAPI rejects any decorated path operation with `FastAPIError: Invalid args for response field! ... check that P.args is a valid Pydantic field type`. It also restores `__name__` / `__doc__` / `__wrapped__` for introspection. Both decorators in `app/utils/decorators.py` carry it; a new one must too.
- **Two retry-policy decisions in `app/utils/decorators.py` that a reader would otherwise "simplify":** the backoff is **full jitter** - uniform in `[0, min(base_delay, max_delay)]` - which is what reduces thundering-herd impact when many callers retry after the same downstream failure; and `_should_stop` is **deliberately independent of `raises_on_exception`**, because whether to keep trying and whether to re-raise are separate questions. Conflating them made `raises_on_exception=False` silently ignore `non_retry_exceptions` and keep retrying an error explicitly marked as not worth retrying.
