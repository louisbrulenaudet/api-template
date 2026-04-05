# syntax=docker/dockerfile:1.7

# uv is only present here. The runtime stage copies the finished venv and never
# sees uv, reducing the attack surface and image size.
FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock /app/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.14-slim AS runtime

# PYTHONDONTWRITEBYTECODE: suppress runtime .pyc writes (uv pre-compiled at build).
# PYTHONUNBUFFERED: flush stdout/stderr immediately (visible in `docker logs`).
# PYTHONHASHSEED: unpredictable seed — mitigates hash-flooding attacks.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    LOGFIRE_SEND_TO_LOGFIRE=false \
    LOGFIRE_PYDANTIC_PLUGIN_RECORD=off

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY --from=builder /app/.venv /app/.venv

# Fixed UID/GID (10001) avoids accidental collision with system UIDs and is
# predictable across rebuilds. -M: no home directory. -s /sbin/nologin: no shell.
RUN groupadd -r -g 10001 appuser \
    && useradd -r -u 10001 -g appuser -s /sbin/nologin -M appuser

COPY --chown=appuser:appuser pyproject.toml /app/pyproject.toml
COPY --chown=appuser:appuser ./app /app/app

USER 10001:10001

HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys,urllib.request; url='http://127.0.0.1:8001/api/v1/health'; r=urllib.request.urlopen(url,timeout=3); sys.exit(0 if r.status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

# Inherits the hardened runtime image; fastapi/uvicorn come from the venv,
# so uv is not needed here either.
FROM runtime AS reload
CMD ["fastapi", "dev", "app/main.py", "--host", "0.0.0.0", "--port", "8000", "--reload"]
