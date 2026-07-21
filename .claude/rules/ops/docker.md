---
paths:
  - "Dockerfile*"
  - ".dockerignore"
  - "compose*.yaml"
  - "compose*.yml"
  - "docker-compose*.yml"
  - "make/docker.mk"
---

# Docker

Container build + Compose conventions for this template, validated against Docker's
[build best practices](https://docs.docker.com/build/building/best-practices/), the
[uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/), and the
[Compose file reference](https://docs.docker.com/reference/compose-file/). Keep the
Cursor twin [`.cursor/rules/ops/docker.mdc`](../../../.cursor/rules/ops/docker.mdc)
in sync when you change this file.

## Build context (allowlist `.dockerignore`)

[`.dockerignore`](../../../.dockerignore) excludes everything (`*`), then re-includes
only what the Dockerfile `COPY`s (`pyproject.toml`, `uv.lock`, `app/`).

- Add a `COPY <path>` to the Dockerfile → add the matching `!<path>` in the **same** change.
- Re-exclude caches even inside allowlisted trees (`app/**/__pycache__`, `*.pyc`).

## Image build (multi-stage + uv)

- **Multi-stage.** `uv` lives only in the `builder` stage; `runtime` copies the finished
  `/app/.venv` and contains no `uv` or build tooling — smaller image and attack surface.
  Copy the venv with `COPY --link` for better cross-build cache reuse.
- **Install.** `RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev`.
  Use `--locked` (fails on lock drift; matches CI) — not `--frozen` (bootstrap only).
- **uv env.** `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy` (cache mount is a different fs),
  `UV_PYTHON_DOWNLOADS=0` (use the base image's Python). `[tool.uv] package = false`
  here, so `uv sync` installs dependencies only — copy `app/` separately as source.
- **Pin bases.** Pin the Python base and the `ghcr.io/astral-sh/uv` tag by version;
  digest-pin (`@sha256:…`) for full reproducibility in production. Never `:latest`.
- **Non-root.** Fixed-UID user (`useradd -r -u 10001 … -s /sbin/nologin -M`); set `USER`
  before `CMD`. Keep `PYTHONDONTWRITEBYTECODE=1` so a read-only rootfs never writes `.pyc`.
- **Signals.** Exec-form (JSON-array) `CMD` so the server is PID 1 and receives SIGTERM.
- **Labels.** Add OCI labels (`org.opencontainers.image.*`) for provenance.

## Healthchecks

- Each servable stage's `HEALTHCHECK` must target the port that stage serves. `runtime`
  serves 8001, `reload` serves 8000 — `reload` **overrides** the inherited check (a stage
  that changes the port but keeps an 8001 check reports unhealthy). `--start-interval`
  speeds up start-period detection.

## Secrets

- Never put secrets in `ENV`/`ARG` — they persist in image layers and `docker history`.
  Use `RUN --mount=type=secret,id=…` at build time, and Compose `secrets:` / `env_file`
  (`.env`, git-ignored) at runtime.

## Compose

- No top-level `version:` (obsolete); set a `name:` for stable project naming.
- **Harden every service:** `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`,
  `pids_limit`, `deploy.resources.limits` (cpus/memory), `logging` size caps, `init: true`,
  and `read_only: true` + `tmpfs` where the workload allows. Publish ports to loopback
  (`127.0.0.1:…`).
- **Hot reload:** `develop.watch` — `sync` app source, `rebuild` on `pyproject.toml`/`uv.lock`.
  Run via `docker compose up --watch` (`make docker-run-dev`). `read_only` is relaxed on the
  watch-sync dev service (sync writes into the container); the production image stays read-only.
- **Startup order:** `depends_on: { <svc>: { condition: service_healthy } }`.

## Workflow

- Prefer `make docker-*` targets over ad-hoc `docker` commands in docs/agents; keep the
  `.PHONY` list in [`make/docker.mk`](../../../make/docker.mk) in sync with real targets.
- Keep Logfire/telemetry disable flags consistent with Makefile defaults unless explicitly enabling them.
