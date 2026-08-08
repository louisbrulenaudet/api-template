# syntax=docker/dockerfile:1
# check=error=true

# Base and uv pins are literal `FROM` refs so Dependabot can see them (ops/dockerfile).
FROM python:3.14-slim-trixie@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144 AS base

FROM ghcr.io/astral-sh/uv:0.12.1@sha256:cf4eedcaa81655197f625739489effcbe71b61ceb1506f332c3facae5deceded AS uvbin

FROM base AS builder

COPY --from=uvbin /uv /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock /app/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Supplies `fastapi dev` to the `reload` stage, and nothing else. `--no-dev --group devserver`, never
# a bare `uv sync` (ops/dockerfile, quality/uv-dependencies).
FROM builder AS builder-dev

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --group devserver

FROM base AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    LOGFIRE_SEND_TO_LOGFIRE=false \
    LOGFIRE_PYDANTIC_PLUGIN_RECORD=off

# Which peers may set X-Forwarded-For / X-Forwarded-Proto. Not "*", and not a uvicorn flag, both
# deliberately - see ops/dockerfile before changing either.
ENV FORWARDED_ALLOW_IPS="10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.1"

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY --link --from=builder /app/.venv /app/.venv

# Non-root at a fixed UID, and the same layer strips pip from the SYSTEM site-packages - all three
# paths, via `rm -rf` rather than `pip uninstall` (ops/dockerfile).
RUN groupadd -r -g 10001 appuser \
    && useradd -r -u 10001 -g appuser -s /sbin/nologin -M appuser \
    && rm -rf /usr/local/lib/python3.14/site-packages/pip \
              /usr/local/lib/python3.14/site-packages/pip-*.dist-info \
              /usr/local/lib/python3.14/ensurepip/_bundled \
              /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.14

COPY --chown=appuser:appuser pyproject.toml /app/pyproject.toml
COPY --chown=appuser:appuser ./app /app/app

# `app/` arrives as plain source, so precompile it here. Must stay before USER, and keep the default
# `timestamp` invalidation mode - `reload` depends on it (ops/dockerfile).
RUN python -m compileall -q /app/app

USER 10001:10001

# Placed late so a label change does not bust the layers above (ops/dockerfile).
ARG APP_VERSION=0.1.0
LABEL org.opencontainers.image.title="backend" \
      org.opencontainers.image.description="Minimal, production-ready FastAPI template with strict Pydantic validation." \
      org.opencontainers.image.source="https://github.com/louisbrulenaudet/api-template" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.version="${APP_VERSION}"

EXPOSE 8001

HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --start-interval=5s --retries=3 \
    CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/api/v1/health',timeout=3).status==200 else 1)"]

# --timeout-graceful-shutdown has NO default in uvicorn, and 25s must stay strictly inside whatever
# stop window the orchestrator applies (ops/dockerfile).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-server-header", "--timeout-graceful-shutdown", "25"]

FROM runtime AS reload

# Overlays the dev-group venv, which supplies `fastapi dev` below. A plain COPY, deliberately not
# `--link`: an overlay must build on the inherited state (ops/dockerfile).
COPY --from=builder-dev /app/.venv /app/.venv

# The dev server listens on 8000, so this MUST override the inherited 8001 check (ops/dockerfile).
# compose.yaml relies on this one rather than declaring its own.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --start-interval=5s --retries=3 \
    CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health',timeout=3).status==200 else 1)"]

EXPOSE 8000

CMD ["fastapi", "dev", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
