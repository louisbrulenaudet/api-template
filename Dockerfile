# syntax=docker/dockerfile:1
# check=error=true

# An alias stage adds no layer and costs nothing; both children resolve the same base image.
FROM python:3.14-slim AS base

# uv ships as a standalone binary in its own image. Resolved through a named stage so the `COPY
# --from` below refers to a stage rather than an image reference - and so Dependabot sees this ref
# on a FROM line too.
FROM ghcr.io/astral-sh/uv:0.11.29 AS uvbin

# uv is only present here. The runtime stage copies the finished venv and never
# sees uv, reducing the attack surface and image size.
FROM base AS builder

COPY --from=uvbin /uv /bin/

# UV_COMPILE_BYTECODE: ship precompiled .pyc for faster cold start.
# UV_LINK_MODE=copy: the cache mount is a different filesystem than the venv, so
#   copy instead of hardlink (avoids cross-device link warnings).
# UV_PYTHON_DOWNLOADS=0: use the base image's Python; never fetch a second one.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock /app/

# --frozen installs uv.lock exactly, without re-resolving - deterministic and
# immune to the relative `exclude-newer` window (which would make --locked drift
# as the window slides). Locking happens only via `uv lock` / `make lock`. The
# cache mount persists uv's downloads across builds.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM base AS runtime

# PYTHONDONTWRITEBYTECODE: suppress runtime .pyc writes (uv pre-compiled at build).
# PYTHONUNBUFFERED: flush stdout/stderr immediately (visible in `docker logs`).
# PYTHONHASHSEED: unpredictable seed - mitigates hash-flooding attacks.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    LOGFIRE_SEND_TO_LOGFIRE=false \
    LOGFIRE_PYDANTIC_PLUGIN_RECORD=off

# Which peers may set X-Forwarded-For / X-Forwarded-Proto. uvicorn enables --proxy-headers by
# default but trusts only 127.0.0.1, and a sidecar proxy (the cloudflared service in
# compose.yaml) connects from another container on the bridge network - so the forwarded headers
# were silently discarded: request.client.host became the proxy's IP, and FORCE_HTTPS produced an
# infinite redirect loop because scope["scheme"] stayed "http" (which also kept the HEALTHCHECK
# failing, so the tunnel's `depends_on: service_healthy` never released).
# RFC1918 CIDRs rather than "*": still correct behind a container-network proxy, but a directly
# published port cannot be spoofed from the internet. uvicorn reads this env var when the
# --forwarded-allow-ips flag is absent, so it stays overridable per deployment.
ENV FORWARDED_ALLOW_IPS="10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.1"

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

# --link isolates the venv on its own layer for better cross-build cache reuse.
COPY --link --from=builder /app/.venv /app/.venv

# Fixed UID/GID (10001) avoids accidental collision with system UIDs and is
# predictable across rebuilds. -M: no home directory. -s /sbin/nologin: no shell.
RUN groupadd -r -g 10001 appuser \
    && useradd -r -u 10001 -g appuser -s /sbin/nologin -M appuser

COPY --chown=appuser:appuser pyproject.toml /app/pyproject.toml
COPY --chown=appuser:appuser ./app /app/app

USER 10001:10001

# OCI image metadata for provenance. CI can inject dynamic fields, e.g.
# --build-arg APP_VERSION=$(git describe --tags). Placed late so label changes
# do not bust the venv/source layers above.
ARG APP_VERSION=0.1.0
LABEL org.opencontainers.image.title="backend" \
      org.opencontainers.image.description="Minimal, production-ready FastAPI template with strict Pydantic validation." \
      org.opencontainers.image.source="https://github.com/louisbrulenaudet/api-template" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.version="${APP_VERSION}"

EXPOSE 8001

# --start-interval probes more frequently during the start period (needs Engine >= 25.0).
# Exec form (JSON array): no /bin/sh is spawned per probe, and it survives a shell-less base if
# the runtime is ever swapped for distroless. `python` resolves via PATH to the venv interpreter,
# so the probe needs nothing installed that the app does not already need. Deliberately hits only
# /api/v1/health - a probe that reached a downstream dependency would report this container
# unhealthy for someone else's outage.
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --start-interval=5s --retries=3 \
    CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/api/v1/health',timeout=3).status==200 else 1)"]

# --no-server-header drops the `server: uvicorn` banner, which only tells a scanner what to
# target. Proxy-header trust comes from FORWARDED_ALLOW_IPS above rather than a flag, so it stays
# overridable at run time without rebuilding.
# --timeout-graceful-shutdown has NO default in uvicorn: without it the server waits on in-flight
# requests indefinitely, whatever stop window the orchestrator applies expires, and SIGKILL truncates
# them. 25s has to stay strictly inside that window - in production that is Kubernetes'
# terminationGracePeriodSeconds (default 30s), and in CI it is `docker stop --timeout 30` in the smoke
# test. Compose never runs this stage; it builds `reload` below.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-server-header", "--timeout-graceful-shutdown", "25"]

# Inherits the hardened runtime image; fastapi/uvicorn come from the venv,
# so uv is not needed here either.
FROM runtime AS reload

# The dev server listens on 8000; override the inherited 8001 healthcheck so the
# reload image is also correct when run directly (Compose overrides it too).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --start-interval=5s --retries=3 \
    CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health',timeout=3).status==200 else 1)"]

EXPOSE 8000

# `fastapi dev` already enables --reload.
CMD ["fastapi", "dev", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
