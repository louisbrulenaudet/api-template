---
paths:
  - "app/main.py"
  - "app/middlewares/**"
---

# Middleware and App Entry

`create_app()` in `app/main.py` assembles everything - middleware, exception handlers, the versioned
router, lifespan - and the module-level `app = create_app()` is what `app.main:app` serves. The stack is
registered by `configure_middleware(app, settings)` in `app/middlewares/setup.py`, never inline in
`main.py`.

## Middleware order

Starlette applies middleware **LIFO** (last added = outermost). Read `setup.py` for the current order.
Three orderings are load-bearing and must not be "tidied":

- **CORS outermost** - preflight answered before any redirect or compression.
- **TrustedHost before HTTPSRedirect** - the redirect builds `Location` from `Host`; validating first is
  what prevents an open redirect.
- **SecurityHeaders outside both** - so their short-circuit 400/307 responses still carry the headers.

## Probe exemption

`ProbeBypassMiddleware` (`app/middlewares/probe_bypass.py`) owns TrustedHost + HTTPSRedirect as one unit
and serves `PROBE_PATHS` (`app/api/v1/router.py`) without either. Neither guard is satisfiable by a probe:
the Dockerfile `HEALTHCHECK` and a kubelet probe both connect by IP, so they send a `Host` production's
explicit-hostname `ALLOWED_HOSTS` cannot name, and a 307 to HTTPS is one they cannot follow. Without it
the container is permanently unhealthy - the failure mode that produced a wall of 400s in CI's image
smoke test.

**Both guards, not just the host check.** Exempting TrustedHost alone drops the request into
HTTPSRedirect, which then builds `Location` from an unvalidated `Host` - an open redirect on
`/api/v1/health`. That is why the two are composed inside one middleware instead of registered
separately, and why `HTTPSRedirectMiddleware` no longer appears in `app.user_middleware` (assert on
behaviour, not on that list).

The exemption is safe only because these routes take no input and return a static payload. **Do not add a
path to `PROBE_PATHS`** that reads request state, echoes anything, or builds a URL.

`RequestIDMiddleware` and `SecurityHeadersMiddleware` are **pure ASGI, not `BaseHTTPMiddleware`** - the
former deliberately so, because its `ContextVar` has to propagate downstream, which `BaseHTTPMiddleware`
breaks.

## Security

- CORS origins and credentials are settings-driven and **default to allow-all for local dev**. Wildcard +
  credentials is rejected at startup, and `ENVIRONMENT=production` rejects wildcard outright - the guard is
  in code, not a comment.
- `SecurityHeadersMiddleware` uses `setdefault`, so an individual route may override a header.
- **Inbound `X-Request-ID` is untrusted input.** `_coerce_request_id` accepts only
  `[A-Za-z0-9._:@/+=-]{1,128}` and otherwise substitutes a fresh UUID. The value reaches log lines and a
  response header, so an unvalidated one is a log-forging vector.
- Never log secrets, raw API keys, or full auth headers.

## Lifespan

- Configure aiocache and other process-wide async resources in lifespan setup/teardown. Avoid mutable global
  per-request state - use dependencies or request context.
- **`app.state` is an untyped `Any` bag** (Starlette's `State.__getattr__`), so a plain `app.state.foo` read
  satisfies *any* annotation and no ty setting can catch a wrong one. Give each entry a typed setter/getter
  pair - see `set_http_client` / `get_http_client` in `app/core/http_client.py`: the setter keeps writes
  checked, the getter re-establishes the type with `isinstance` and raises a `CoreError` when the lifespan
  never ran.
- **Hold the resource in a local for teardown** (`await http_client.aclose()`). Never
  `await app.state.x.aclose()` - that is an unchecked call on `Any`.

Exception handlers are registered by `register_exception_handlers(app)`; the envelope and status mapping live
in [exceptions.md](exceptions.md).
