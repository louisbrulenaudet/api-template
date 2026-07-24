from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

from app.core.config import Settings
from app.middlewares.request_id import RequestIDMiddleware

__all__ = [
    "configure_middleware",
]


def configure_middleware(app: FastAPI, settings: Settings) -> None:
    """Register the application middleware stack on ``app``.

    Middleware is applied in LIFO order: the LAST added is the OUTERMOST (first to see the request, last to touch the response). Adding GZip -> [HTTPSRedirect] -> RequestID -> CORS gives this request-processing order: CORS -> RequestID -> (optional HTTPS redirect) -> GZip -> routes

    Args:
        app: The FastAPI application to configure.
        settings: The application settings driving CORS and HTTPS behavior.
    """
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1500,
        compresslevel=5,
    )

    if settings.force_https:
        app.add_middleware(HTTPSRedirectMiddleware)

    # Correlation ID: assign/propagate X-Request-ID (exposed to browsers via CORS below).
    app.add_middleware(RequestIDMiddleware)

    # CORS must be outermost so an OPTIONS preflight is answered before any redirect or
    # compression. Origins/credentials come from Settings - restrict ALLOWED_ORIGINS in
    # production (default ["*"] for local dev; wildcard + credentials is rejected at startup).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=settings.allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "Origin"],
        expose_headers=["X-Request-ID"],
    )
