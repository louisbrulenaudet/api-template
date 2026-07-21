---
paths:
  - "app/**/*.py"
  - "tests/**/*.py"
---

# Code Style

Ruff is the source of truth for format and lint. Do not fight the formatter.

## Finish gate

After a batch of Python edits, run `make check` (and `make format` if you changed style). Prefer fixing causes over `# noqa`.

## Style

- Double quotes, spaces, line length 100 (`[tool.ruff]` in `pyproject.toml`).
- Strict type hints on all function parameters and return types.
- Prefer explicit over clever; keep functions focused and under ~50 lines when practical.
- No floating work: always `await` async calls or return the coroutine to the caller.
- Thin route handlers - business logic lives in `app/core/` or dedicated service modules, not in endpoint files.

## Imports

- Absolute imports from `app.*`.
- Group: stdlib → third party → local (`app`), separated by blank lines (Ruff `I`).
