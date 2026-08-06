---
paths:
  - "compose*.y*ml"
  - "docker-compose*.y*ml"
---

# Compose

**Compose is local development only.** Production runs on Kubernetes, so there is exactly one file - [`compose.yaml`](../../../compose.yaml), building the `reload` target on port 8000 - and nothing in it is a deployment descriptor. Image-build decisions live in [`ops/dockerfile.md`](dockerfile.md).

Two consequences. The proof that the `runtime` image is actually deployable lives in CI's smoke step, which runs it under `--read-only --cap-drop ALL --security-opt no-new-privileges` on a raw `docker run` ([`ops/composite-actions.md`](composite-actions.md)). And the production posture - `securityContext` with `runAsUser: 10001`, `readOnlyRootFilesystem`, `capabilities.drop: [ALL]`, `allowPrivilegeEscalation: false`, resource limits, the `ENVIRONMENT=production` pin - belongs in the k8s manifests. **Do not reintroduce a second Compose file or an override to model production.**

- No top-level `version:` (obsolete); set a `name:` for stable project naming.
- **`ENVIRONMENT: development` is pinned in the file, not left to `.env`**, because a Compose-file `environment` value outranks `env_file` and this file *is* the dev stack. Know the consequence: `make docker-run-dev-tunnel` puts a development-configured app on a public Cloudflare hostname, where `_enforce_production_hardening` is inert - `/docs` and the full OpenAPI schema are served, `ALLOWED_ORIGINS` / `ALLOWED_HOSTS` may still be `*`, and an empty `API_KEY` does not raise. Demo link, never a deployment.
- **`pids_limit` and `deploy.resources.limits.pids` must be equal**, and an *absent* `pids` counts as 0 - so `pids_limit` next to any `limits` block is a hard `invalid compose project` error. Set both.
- **A Compose `healthcheck` replaces the image's `HEALTHCHECK` wholesale, flags included**, so the Dockerfile's `--start-interval` does not carry over. Restate `start_interval` or the container sits "starting" for a full `interval`.
- **No `image:` on the `app` service** - Compose auto-names the built image from the project and service name, and a hand-written local tag only invites tooling to mistake it for a pullable ref.
- **Harden every service anyway:** `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, `pids_limit`, `deploy.resources.limits`, `logging` size caps, `init: true`. Publish ports to loopback (`127.0.0.1:…`). Use `limits` only - `reservations` is silently ignored outside Swarm, so relying on it is a false sense of safety. `read_only: true` + `tmpfs` where the workload allows: `cloudflared` takes it, the `app` service cannot because `develop.watch` sync writes into `/app/app`.
- **`develop.watch` `ignore` patterns need an explicit `**/`.** They are relative to the entry's `path` and use Docker's context-pattern syntax, where a bare `*.pyc` matches only files *directly* under `./app` - not `app/core/__pycache__/config.cpython-314.pyc`. Written without it, the list silently covers almost nothing and only the recursive `app/**/__pycache__` entries in `.dockerignore` (which Compose also applies) keep host bytecode out of the container. Use `**/__pycache__/` and `**/*.pyc`.
- Startup order via `depends_on: { <svc>: { condition: service_healthy } }`.
- **`--profile` is needed by every command that names a profiled service**, not just `up`: without it Compose treats the service as unknown. The `cloudflared` sidecar sits behind `profiles: ["tunnel"]`, which is why `make/variables.mk` keeps a separate `$(COMPOSE_TUNNEL)` ([`ops/makefile.md`](makefile.md)).

## The cloudflared sidecar

**It probes itself with its own binary** - `cloudflared tunnel --metrics <addr> ready`, which exits 0 only once the connector holds a live edge connection, so it is a genuine readiness check rather than a liveness proxy. The image is distroless (no shell, no curl), so the subcommand is the only option available. Two argument-order facts go with it: `--metrics` must precede the `run` subcommand or it is parsed as a `run` flag, and the image `ENTRYPOINT` already supplies `cloudflared --no-autoupdate`, so the Compose `command:` must not repeat either.

## Graceful shutdown

`stop_grace_period: 10s` on the `app` service is **not** related to the `runtime` stage's 25s `--timeout-graceful-shutdown`. Compose builds the `reload` stage, which runs `fastapi dev` and has no in-flight-request budget to protect; 10s is also Compose's own default. **Do not "align" the two numbers** - they govern different stages ([`ops/dockerfile.md`](dockerfile.md)).

## Secrets

Duplicated from [`ops/dockerfile.md`](dockerfile.md) on purpose rather than cross-referenced: a path rule is not re-injected after `/compact`, so a reader who opened only `compose.yaml` would otherwise be wiring credentials with these invariants absent.

**Nothing enforces this:** never put secrets in `ENV` / `ARG` - they persist in image layers and in `docker history`, so the leak outlives the build. **Never `COPY .env`.** Use `RUN --mount=type=secret,id=…` at build time and Compose `secrets:` / `env_file` (git-ignored `.env`) at runtime. Note the two Compose mechanisms are different: `.env` feeds Compose *interpolation*, `env_file:` injects into the container.

The tunnel token is the worked example. It goes through the top-level `secrets:` element (sourced from `environment: TUNNEL_TOKEN`) and reaches cloudflared as `TUNNEL_TOKEN_FILE=/run/secrets/tunnel_token`, so it is a tmpfs file rather than a container env var - out of `docker inspect`, out of `/proc/<pid>/environ`, out of the host process list. Passing `TUNNEL_TOKEN` or `--token` to the service directly undoes all of that. The invariant: **the token is never inline in a Compose file and never baked into an image.**

**`.env` being read twice is the trap.** Compose reads it for interpolation (which is how that secret is sourced) *and* `env_file:` injects it into the app container - so a token in `.env` reaches the internet-facing process too, `secrets:` notwithstanding. `compose.yaml` therefore sets `TUNNEL_TOKEN: ""` in the app service's `environment:`, which outranks `env_file` and scrubs it.

**Nothing enforces this:** deleting that line is a silent credential leak. `docker compose config` is happy either way, no test covers it, and `env_file` has no exclusion mechanism - so **any credential that only a sidecar needs has to be scrubbed the same way**. It is the one line in `compose.yaml` to leave alone.
