---
paths:
  - "app/main.py"
  - "app/middlewares/**"
---

# Middleware and App Entry

`app/main.py`'s `create_app()` factory assembles the app - middleware, exception handlers, the versioned router, and lifespan - and exposes the module-level `app = create_app()` served as `app.main:app`.

## Middleware order

Starlette applies middleware in **LIFO** order (last added = outermost). Keep CORS outermost so `OPTIONS` preflight is answered before redirects/compression.

Documented request flow: **CORS → RequestID → (optional HTTPS redirect) → GZip → routes**.

The stack is registered by `configure_middleware(app, settings)` (`app/middlewares/setup.py`), not inline in `main.py`. `RequestIDMiddleware` (`app/middlewares/request_id.py`, pure ASGI) assigns/propagates an `X-Request-ID` per request and exposes it via `get_request_id()` for logging. Pure ASGI (not `BaseHTTPMiddleware`) so the `ContextVar` propagates downstream.

## Security

- CORS origins/credentials are settings-driven (`ALLOWED_ORIGINS`, `ALLOW_CREDENTIALS` in `app/core/config.py`): default allow-all for local dev - **restrict in production**. Wildcard origins combined with credentials is rejected at startup.
- Do not log secrets, raw API keys, or full auth headers.

## Lifespan

- Configure aiocache (or other process-wide async resources) in lifespan setup/teardown.
- Avoid mutable global per-request state; use FastAPI dependencies / request context.

## Exception handler

The `CoreError` handler lives in `app/exceptions/handlers.py` and is registered via `register_exception_handlers(app)` (called by `create_app()`). Keep it returning structured JSON, tagged with the request's `X-Request-ID` for correlation. When adding error types that need special status codes, update the handler or class-level `http_status_code` in the same change.
