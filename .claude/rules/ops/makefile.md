---
paths:
  - "Makefile"
  - "make/**"
---

# Makefile

The root [`Makefile`](../../../Makefile) is a thin aggregator that includes `make/*.mk`. Put a new target in the right fragment (`dev.mk`, `docker.mk`, `help.mk`, `variables.mk`), never as one-off shell in docs. `make help` lists them; `AGENTS.md` covers the few whose behaviour is not obvious.

Every target carries a `## description` comment - that is what `help` parses, so a target without one is invisible.

## Parity with CI

**`make` targets and GitHub Actions steps run the same commands.** Divergence between them is how "green locally, red in CI" happens, so change both in one edit. The mirror of CI's `test` job is **`make ci-check`**, which never mutates the tree. `make ci` is deliberately *not* that mirror: it runs `ruff format .` and `ruff check . --fix`, so formatting drift can never fail it the way CI's `ruff format --check .` fails. See [`ops/ci.md`](ci.md).

A check a developer should be able to reproduce locally goes here, never inline in a workflow step - which is why `docker-lint` runs `make docker-check-build` + `make docker-config` rather than raw `docker` commands. The one deliberate exception is a **registry-bound** gate: `verify-base-digests` is a composite action and not a `make` target precisely so a developer's inner loop gains no network dependency ([`ops/composite-actions.md`](composite-actions.md)).

## Load-bearing details

- **`ASGI_APP` has three homes:** the `make/variables.mk` variable, the Dockerfile `runtime` stage's `CMD`, and `[tool.fastapi] entrypoint`. **Nothing enforces this:** nothing checks that the three agree, so a partial rename leaves a Makefile that starts the wrong module and a container that still starts the right one. Keep them in step by hand. (`uvicorn` takes a module path, which is why the variable is not just `APP`.)
- **`make prod` runs the same server and entrypoint as the `runtime` stage's `CMD`**, so it exercises the real production command rather than a lookalike - `uvicorn` directly, never `fastapi run`, because the fastapi CLI is `devserver`-only and absent from that image ([`quality/uv-dependencies.md`](../quality/uv-dependencies.md)). **Two deliberate differences.** No `--host 0.0.0.0`, so it binds uvicorn's default `127.0.0.1` and stays off the LAN: inside a container `0.0.0.0` is required and safe, because the network namespace is the boundary; on a laptop it is neither. Pass `--host 0.0.0.0` yourself if you need to reach it from another machine. And `FORWARDED_ALLOW_IPS` is left unset - the container sets it because a sidecar proxy connects from another container, which does not apply here ([`ops/compose.md`](compose.md)).
- **`check-requirements` writes only to a temp file.** A check must never "fix" the tree it is checking. Two details in that recipe are load-bearing and look like noise: `mktemp` gets an explicit template because BSD/macOS `mktemp` with no argument **ignores `TMPDIR`**, and stdout is dropped because `uv export -o FILE` also echoes the whole file there - stderr is left alone so a genuine export failure stays visible. Its `diff -I '^#  *uv export '` filter is equally load-bearing: `uv export` writes its own argv into a header comment, so without it the gate fails on every run forever. `-I` ignores a hunk only when *every* changed line in it matches, so a real dependency change next to the header still fails - the failure mode is a false alarm, never a miss.
- **`make lock` / `make update` are the only way `uv.lock` may change**, and `make export-requirements` must follow every one of them ([`quality/uv-dependencies.md`](../quality/uv-dependencies.md)).
- **Logfire send/plugin flags stay off** via the exported `LOGFIRE_SEND_TO_LOGFIRE` / `LOGFIRE_PYDANTIC_PLUGIN_RECORD` in `make/variables.mk`, matching Docker and CI. Do not drop them to "test telemetry" without saying so.

## Docker targets

Prefer `make docker-*` over ad-hoc `docker` commands, and keep the `.PHONY` list in [`make/docker.mk`](../../../make/docker.mk) matching the real targets. Never inline `docker compose` in a recipe - use `$(COMPOSE)`, so the `--profile` handling in `make/variables.mk` stays in one place. **`--profile` is needed by every command that names a profiled service**, not just `up`: without it Compose treats the service as unknown, which is why `$(COMPOSE_TUNNEL)` exists for the `cloudflared` sidecar ([`ops/compose.md`](compose.md)).
