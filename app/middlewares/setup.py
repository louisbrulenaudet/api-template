from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1.router import PROBE_PATHS
from app.core.config import Settings
from app.core.security import API_KEY_HEADER_NAME
from app.middlewares.probe_bypass import ProbeBypassMiddleware
from app.middlewares.request_id import REQUEST_ID_HEADER, RequestIDMiddleware
from app.middlewares.security_headers import SecurityHeadersMiddleware

__all__ = [
    "configure_middleware",
]


def configure_middleware(app: FastAPI, settings: Settings) -> None:
    """Register the application middleware stack on ``app``.

    Middleware is applied in LIFO order: the LAST added is the OUTERMOST (first to see the request, last to touch the response). The add order below therefore yields this request-processing order:

        CORS -> RequestID -> SecurityHeaders -> ProbeBypass{TrustedHost -> [HTTPSRedirect]} -> GZip -> routes

    `ProbeBypassMiddleware` owns host validation and HTTPS redirection as one unit rather than registering them separately, because the probe paths have to skip both together - see its docstring.

    Three orderings are load-bearing:

    * **CORS outermost** so an `OPTIONS` preflight is answered before any redirect or compression touches it.
    * **TrustedHost before HTTPSRedirect** (inside `ProbeBypassMiddleware`). `HTTPSRedirectMiddleware` builds its `Location` from the request's `Host` header. Validating the host first is what stops a spoofed `Host` from turning that redirect into an open redirect to an attacker's domain.
    * **SecurityHeaders outside the bypass** so the short-circuit responses (a 400 invalid-host, a 307 redirect) carry the headers too.

    Args:
        app: The FastAPI application to configure.
        settings: The application settings driving CORS, host and HTTPS behavior.
    """
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1500,
        compresslevel=5,
    )

    # Host-header validation plus optional HTTPS redirection. `["*"]` (the local default) makes
    # the host check a no-op; production rejects that wildcard at startup, so a prod app always
    # has an explicit host list - which is exactly why the probes need an exemption from it.
    app.add_middleware(
        ProbeBypassMiddleware,
        allowed_hosts=settings.allowed_hosts,
        force_https=settings.force_https,
        probe_paths=PROBE_PATHS,
    )

    # HSTS only where TLS is actually terminated, which `force_https` is the signal for.
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.force_https)

    # Correlation ID: assign/propagate X-Request-ID (exposed to browsers via CORS below).
    app.add_middleware(RequestIDMiddleware)

    # CORS must be outermost. Origins/credentials come from Settings - the local default is
    # allow-all; production rejects a wildcard, and wildcard + credentials is rejected in
    # every environment.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=settings.allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        # `X-Request-ID` is accepted inbound (callers may supply their own trace ID) as well as
        # exposed outbound; omitting it here would make the documented correlation flow fail
        # preflight for browser clients. `X-API-Key` is the auth header from `app.core.security`.
        allow_headers=[
            "Accept",
            "Authorization",
            "Content-Type",
            "Origin",
            API_KEY_HEADER_NAME,
            REQUEST_ID_HEADER,
        ],
        expose_headers=[REQUEST_ID_HEADER],
    )
