---
paths:
  - "pyproject.toml"
  - "uv.lock"
  - "Makefile"
  - "make/**"
  - ".pre-commit-config.yaml"
---

# Python Tooling

Single source of truth for tool config: [`pyproject.toml`](../../../pyproject.toml). Do not fork Ruff / ty / pytest settings into ad-hoc local copies.

## Package management

- Canonical lockfile: `uv.lock`. Use `make sync`, `make lock`, `make update` — never hand-edit the lock.
- Dev tools come from the `dev` extra (`uv sync --locked --extra dev`), matching CI.
- `requirements.txt` is an optional export only (`make export-requirements` if present); `uv.lock` wins.

## Quality commands

| Command | Purpose |
|---------|---------|
| `make check` | `ruff check .` |
| `make format` | `ruff format` + `ruff check --fix` |
| `make type-check` | `ty check .` |
| `make test` | pytest |
| `make ci` | `format` + `type-check` (Ruff + ty; no tests) |
| `make pre-commit` | pre-commit on all files |

## Makefile layout

- Root `Makefile` includes `make/*.mk`. Put new targets in the right fragment (`dev.mk`, `docker.mk`, …), not as one-off shell in docs.
