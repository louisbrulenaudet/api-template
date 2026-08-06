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

    Added LIFO, so the last added is outermost. That yields this request-processing order:

        CORS -> RequestID -> SecurityHeaders -> ProbeBypass{TrustedHost -> [HTTPSRedirect]} -> GZip -> routes

    Three of those orderings are load-bearing and must not be "tidied" - see
    `.claude/rules/backend/middleware.md` before reordering anything here.
    """
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1500,
        compresslevel=5,
    )

    # Host validation plus optional HTTPS redirection, as one unit.
    app.add_middleware(
        ProbeBypassMiddleware,
        allowed_hosts=settings.allowed_hosts,
        force_https=settings.force_https,
        probe_paths=PROBE_PATHS,
    )

    # HSTS only where TLS is actually terminated, which `force_https` is the signal for.
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.force_https)

    app.add_middleware(RequestIDMiddleware)

    # Must stay outermost.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=settings.allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        # Dropping X-Request-ID or X-API-Key here fails preflight for browser clients.
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
