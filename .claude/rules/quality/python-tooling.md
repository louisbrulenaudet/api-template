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

- Canonical lockfile: `uv.lock`. Use `make sync`, `make lock`, `make update` - never hand-edit the lock.
- **Installs use `--frozen`** (`make sync`, CI, Docker): install `uv.lock` exactly, no re-resolution. Deliberate - `exclude-newer = "7 days"` is a *relative* window, so `--locked` would re-resolve against a sliding cutoff and drift. Locking (and the freshness gate) happens only in `uv lock` / `make lock` / `make update`. Trade-off: installs don't auto-detect an un-relocked `pyproject.toml` edit - run `make lock` after changing dependencies.
- Dev tooling (pytest, Ruff, ty, pre-commit) is the PEP 735 `[dependency-groups] dev` group, synced **by default** (no `--extra`/`--group` flag; there are no `[project.optional-dependencies]`).
- `[tool.uv] required-version` pins the uv floor (matches the CI/Docker pin); `.python-version` pins the dev/CI interpreter within `requires-python`.
- `requirements.txt` is an optional export only (`make export-requirements`); `uv.lock` wins.

## Quality commands

| Command | Purpose |
|---------|---------|
| `make check` | `ruff check .` |
| `make format` | `ruff format` + `ruff check --fix` |
| `make type-check` | `ty check` |
| `make test` | pytest |
| `make ci` | `format` + `type-check` (Ruff + ty; no tests) |
| `make pre-commit` | pre-commit on all files (Ruff lint → Ruff format → ty) |

## Type safety (ty)

ty is the **sole** type checker and LSP (no mypy/pyright config - do not add one). Config: `[tool.ty.*]` in `pyproject.toml`.

- **Suppressions must be `# ty: ignore[rule-name]`.** `analysis.respect-type-ignore-comments = false`, so a mypy-style `# type: ignore` no longer suppresses anything - it is just a comment. A bare `# ty: ignore` is an error (`blanket-ignore-comment`), and stale or misspelled ones fail too (`unused-ignore-comment`, `ignore-comment-unknown-rule`). A suppression is a last resort, never a way to clear a check - see [guardrails.md](../core/guardrails.md).
- **Strictness budget:** of ty's 122 rules, 92 default to `error` and 22 to `warn`; `terminal.error-on-warning = true` makes both levels fail the gate. That leaves only the 8 off-by-default rules as a lever, and 7 are enabled in `[tool.ty.rules]`. `possibly-unresolved-reference` stays off (ty disables it for false positives). Curated-strict is deliberate over `all = "error"`: a ty upgrade must not silently promote a new rule into a hard failure.
- **`src.include` is an allowlist** (`["app", "tests"]`). A new top-level Python package - a `scripts/`, a root `conftest.py` - is silently **unchecked** until added there.
- **`src.exclude` extends** ty's built-in defaults (`.venv/`, `.git/`, `dist/`, `node_modules/`, …) rather than replacing them; a `!pattern` entry re-includes a default. `__pycache__` is *not* a ty default, hence the explicit entry.
- **`environment.python-platform = "linux"`** keeps local diagnostics identical to CI and the container; without it ty assumes the host platform. `python-version` is intentionally left to ty's inference from `project.requires-python`.
- **Do not add `analysis.strict-literal-narrowing`.** It is valid on the pinned ty (0.0.59) but was renamed `strict-equality-semantics` upstream, and an unknown key is a hard TOML parse error - it would break `ty check` the moment the pin moves. Revisit when bumping ty.
- **Relax per-path with `[[tool.ty.overrides]]`**, never by loosening the global rules. Later overrides win; `exclude` beats `include`.
- `ty check` takes **no path argument** anywhere (Makefile, pre-commit, CI): CLI paths bypass `[tool.ty.src]` include/exclude.
- New method overrides need `@override` (`missing-override-decorator = "error"`, PEP 698).

## Makefile layout

- Root `Makefile` includes `make/*.mk`. Put new targets in the right fragment (`dev.mk`, `docker.mk`, …), not as one-off shell in docs.
