---
paths:
  - ".github/workflows/**"
---

# Continuous Integration

The workflow is [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml). Read it for the step
list; a prose copy here would only drift out of date.

## What must stay true

- **`make` targets and GHA steps run the same commands.** Divergence between them is how "green locally,
  red in CI" happens. Change both in one edit.
- **Installs use `--frozen`, never `--locked`** - see `quality/python-tooling.md` for why the relative
  `exclude-newer` window makes `--locked` drift. The uv version is pinned in the workflow; bump it
  deliberately.
- **The Docker `runtime` build is an independent job** (deliberately no `needs: test`) with a Buildx GHA
  layer cache. Do not drop it without replacing the coverage it gives.
- **Production secrets never live in workflow files.** Use GitHub Actions secrets / environments, and keep
  Logfire send flags off unless the run is explicitly testing telemetry.

Weakening a CI gate to force green is covered by [guardrails.md](../core/guardrails.md) and is never the
answer here either.
