---
paths:
  - ".github/workflows/**"
---

# Continuous Integration

CI lives in [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml).

## Expectations

- Install with `uv sync --locked` (dev dependency-group is included by default; pinned uv version in the workflow — bump deliberately).
- Prefer `make ci` for local Ruff + ty; use `make test` for pytest. Keep those aligned with the matching GHA steps.
- In GHA, run ruff / ty / pytest concurrently via the `parallel:` step group after install (shared `.venv`).
- Docker `runtime` image build is an independent job (no `needs: test`) with Buildx GHA layer cache — do not remove without replacing coverage.
- Never weaken CI (skip steps, ignore failures, broaden `continue-on-error`) to force green. Fix the cause. See [guardrails.md](../core/guardrails.md).

## Secrets

- Do not put production secrets in workflow files. Use GitHub Actions secrets / environments.
- Keep Logfire send flags off in CI unless explicitly testing telemetry.
