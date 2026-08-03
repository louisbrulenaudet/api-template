---
paths:
  - "Dockerfile*"
  - ".dockerignore"
  - "compose*.yaml"
  - "compose*.yml"
  - "docker-compose*.yml"
  - "make/docker.mk"
  - ".github/dependabot.yml"
---

# Docker

Validated against Docker's [build best practices](https://docs.docker.com/build/building/best-practices/), [build checks](https://docs.docker.com/build/checks/) and the  [uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/). Read the `Dockerfile`,
`.dockerignore` and `compose.yaml` for what they currently do; this rule covers the decisions behind them and the traps that are not visible in the files.

## Build context

`.dockerignore` is an **allowlist**: it excludes everything (`*`), then re-includes only what the
Dockerfile copies. So **adding a `COPY <path>` means adding the matching `!<path>` in the same change**, or
the build fails on a missing file. Re-exclude caches even inside allowlisted trees (`app/**/__pycache__`,
`*.pyc`).

**The blanket guarantee stops at `!app/**`.** That pattern re-includes *everything* under `app/`, so a
stray `app/.env` or `app/service.key` would land in the image. The explicit re-exclusions for `.env*`,
`*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.keystore` under `app/` put it back. Do not narrow `!app/**` to
`*.py` instead - `jinja2` is a dependency, so non-Python assets have to keep working.

## Image build

- **`# check=error=true`** turns Docker's build-check warnings into build failures, so `docker build`
  cannot succeed with a lint-level defect. `# syntax=docker/dockerfile:1` is deliberately unpinned at the
  minor level because the `check` directive needs frontend ≥ 1.8. `make docker-check-build`
  (`docker build --check`) runs the rules *without* executing build steps; CI runs it as a fast pre-gate.
- **Multi-stage, and `uv` never reaches `runtime`.** It lives in `builder`; `runtime` copies the finished
  `/app/.venv` only, which is both smaller and less attack surface. `COPY --link` improves cross-build
  cache reuse.
- **The base ref is written once, as a literal, in an alias stage** (`FROM python:3.14-slim AS base`;
  `builder` and `runtime` both do `FROM base`). An alias stage costs nothing and keeps the two stages from
  drifting. It is deliberately **not** `ARG PYTHON_IMAGE` + `FROM ${PYTHON_IMAGE}`: Dependabot's Docker
  parser matches only a literal reference on a `FROM` line and has no `ARG` resolution
  (dependabot-core `docker/lib/dependabot/docker/file_parser.rb`, `FROM_LINE`), so the indirection would
  make every base image invisible to it. Change the version by editing the `FROM`.
- **Pin bases by version, never `:latest`**; digest-pin (`@sha256:…`) where immutability matters more than
  legibility. Resolve one with `docker buildx imagetools inspect <ref> --format '{{.Manifest.Digest}}'`. A
  digest is immutable *by design*, which is exactly why the `docker` and `docker-compose` Dependabot
  ecosystems in `.github/dependabot.yml` are load-bearing: nothing else will ever move a pinned base off a
  CVE.
- **`--frozen`, not `--locked`** - see `quality/python-tooling.md` for the `exclude-newer` reason.
- **`UV_LINK_MODE=copy` is required**, not a preference: the cache mount is a different filesystem, so
  hardlinking fails. `UV_PYTHON_DOWNLOADS=0` uses the base image's Python. `[tool.uv] package = false`
  means `uv sync` installs dependencies only, so `app/` is copied separately as source.
- **Non-root with a fixed UID**, `USER` set before `CMD`. Keep `PYTHONDONTWRITEBYTECODE=1` so a read-only
  rootfs never tries to write `.pyc`.
- **Exec-form (JSON-array) `CMD`** so the server is PID 1 and actually receives SIGTERM. Shell form
  silently breaks graceful shutdown.
- Keep the OCI labels (`org.opencontainers.image.*`) for provenance.

## Healthchecks

Each servable stage's `HEALTHCHECK` must target the port **that stage** serves. `runtime` serves 8001 and
`reload` serves 8000, so `reload` has to **override** the inherited check - a stage that changes the port
but keeps the parent's check reports unhealthy forever. `--start-interval` speeds up start-period detection.

**Exec form here too**, and a Python probe rather than `curl`/`wget`: no `/bin/sh` is spawned per probe, and
it survives a shell-less base if `runtime` is ever swapped for distroless. A probe must never reach a
downstream dependency, or this container reports unhealthy for someone else's outage.

## Graceful shutdown

`--timeout-graceful-shutdown` has **no default in uvicorn**: without it the server waits on in-flight
requests indefinitely, whatever stop window the orchestrator applies expires, and SIGKILL truncates them.
**Keep the uvicorn timeout strictly below that window.** It is 25s in the `runtime` stage's `CMD`, which
fits inside Kubernetes' `terminationGracePeriodSeconds` (default 30s) and CI's `docker stop --timeout 30`.
Raising one without the other silently reintroduces the truncation.

This pairing does **not** involve `compose.yaml`: Compose builds the `reload` stage, which runs
`fastapi dev` and has no in-flight-request budget to protect, hence its `stop_grace_period: 10s` (Compose's
own default is also 10s). Do not "align" that number with the uvicorn timeout - they govern different
stages.

## Secrets

Never put secrets in `ENV` / `ARG`: they persist in image layers and in `docker history`, so the leak
outlives the build. Use `RUN --mount=type=secret,id=…` at build time and Compose `secrets:` / `env_file`
(git-ignored `.env`) at runtime. **Never `COPY .env`** - and note the two are different mechanisms: `.env`
feeds Compose *interpolation*, `env_file:` injects into the container.

The tunnel token is the worked example. It goes through the top-level `secrets:` element (sourced from
`environment: TUNNEL_TOKEN`) and reaches cloudflared as `TUNNEL_TOKEN_FILE=/run/secrets/tunnel_token`, so
it is a tmpfs file rather than a container env var - out of `docker inspect`, out of `/proc/<pid>/environ`,
out of the host process list. Passing `TUNNEL_TOKEN` or `--token` to the service directly undoes all of
that. The invariant: **the token is never inline in a Compose file and never baked into an image.**

**`.env` being read twice is the trap.** Compose reads it for interpolation (which is how that secret is
sourced) *and* `env_file:` injects it into the app container - so a token in `.env` reaches the
internet-facing process too, `secrets:` notwithstanding. `compose.yaml` therefore sets `TUNNEL_TOKEN: ""`
in the app service's `environment:`, which outranks `env_file` and scrubs it. **Any credential that only a
sidecar needs has to be scrubbed the same way**, because `env_file` has no exclusion mechanism. Nothing
enforces this - `docker compose config` is happy either way - so deleting that line is a silent
credential leak. It is the one line in `compose.yaml` to leave alone.

## Compose

**Compose is local development only.** Production runs on Kubernetes, so there is exactly one file -
`compose.yaml`, building the `reload` target on port 8000 - and nothing in it is a deployment descriptor.
Two consequences. The proof that the `runtime` image is actually deployable lives in CI's smoke step
(`.github/actions/smoke-test-image`), which runs it under `--read-only --cap-drop ALL
--security-opt no-new-privileges` on a raw `docker run`. And the production posture - `securityContext`
with `runAsUser: 10001`, `readOnlyRootFilesystem`, `capabilities.drop: [ALL]`,
`allowPrivilegeEscalation: false`, resource limits, the `ENVIRONMENT=production` pin - belongs in the k8s
manifests. Do not reintroduce a second Compose file or an override to model production.

- No top-level `version:` (obsolete); set a `name:` for stable project naming.
- **`ENVIRONMENT: development` is pinned in the file, not left to `.env`**, because a Compose-file
  `environment` value outranks `env_file` and this file *is* the dev stack. Know the consequence:
  `make docker-run-dev-tunnel` puts a development-configured app on a public Cloudflare hostname, where
  `_enforce_production_hardening` is inert - `/docs` and the full OpenAPI schema are served,
  `ALLOWED_ORIGINS` / `ALLOWED_HOSTS` may still be `*`, and an empty `API_KEY` does not raise. Demo link,
  never a deployment.
- **`pids_limit` and `deploy.resources.limits.pids` must be equal**, and an *absent* `pids` counts as 0 -
  so `pids_limit` next to any `limits` block is a hard `invalid compose project` error. Set both.
- **A Compose `healthcheck` replaces the image's `HEALTHCHECK` wholesale, flags included**, so the
  Dockerfile's `--start-interval` does not carry over. Restate `start_interval` or the container sits
  "starting" for a full `interval`.
- **No `image:` on the `app` service** - Compose auto-names the built image from the project and service
  name, and a hand-written local tag only invites tooling to mistake it for a pullable ref.
- **Harden every service anyway:** `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`,
  `pids_limit`, `deploy.resources.limits`, `logging` size caps, `init: true`. Publish ports to loopback
  (`127.0.0.1:…`). Use `limits` only - `reservations` is silently ignored outside Swarm, so relying on it
  is a false sense of safety. `read_only: true` + `tmpfs` where the workload allows: `cloudflared` takes
  it, the `app` service cannot because `develop.watch` sync writes into `/app/app`.
- Startup order via `depends_on: { <svc>: { condition: service_healthy } }`.
- **`--profile` is needed by every command that names a profiled service**, not just `up`: without it
  Compose treats the service as unknown. The `cloudflared` sidecar sits behind `profiles: ["tunnel"]`.

## Workflow

Prefer `make docker-*` over ad-hoc `docker` commands, and keep the `.PHONY` list in
[`make/docker.mk`](../../../make/docker.mk) matching the real targets. Never inline `docker compose` in a
recipe - use `$(COMPOSE)`. `docker-check-build` and `docker-config` are also what CI's `docker-lint` job
runs; see `ops/ci.md`.
