import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from aiocache import caches
from aiocache.backends.memory import SimpleMemoryCache
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as api_router
from app.core.config import get_settings
from app.core.http_client import create_http_client
from app.core.middleware import RequestIDMiddleware, get_request_id
from app.exceptions.core_exception import CoreError

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Configure application lifespan (cache + shared HTTP client)."""
    caches.set_config({"default": {"cache": SimpleMemoryCache, "ttl": 60, "maxsize": 1000}})
    app.state.http_client = create_http_client()
    try:
        yield
    finally:
        await app.state.http_client.aclose()


app = FastAPI(
    title=settings.name,
    summary="Minimal, production-ready FastAPI backend with strict Pydantic validation.",
    description="A minimal, production-ready template for building APIs with FastAPI, featuring strict data validation and Docker-based containerization, tailored for express deployment via a secure Cloudflare Tunnel.",
    version=settings.version,
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.include_router(api_router, prefix="/api/v1")

# Middleware is applied in LIFO order: the LAST added is the OUTERMOST (first to see the
# request, last to touch the response). Adding GZip → [HTTPSRedirect] → RequestID → CORS
# gives this request-processing order:
#   CORS → RequestID → (optional HTTPS redirect) → GZip → routes
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


@app.exception_handler(CoreError)
async def error_handler(_: Request, exc: CoreError) -> JSONResponse:
    """Custom exception handler for `CoreError`.

    Converts the error into a structured JSON response tagged with the request's correlation ID (X-Request-ID) for log/support correlation.
    """
    request_id = get_request_id()

    logger.error(
        "CoreError: %s [Code: %s] [RequestID: %s] Details: %s",
        exc.message,
        exc.code,
        request_id,
        exc.details,
    )

    payload: dict[str, Any] = {
        "error": exc.__class__.__name__,
        "message": exc.message,
        "code": exc.code,
        "details": exc.details or {},
        "request_id": request_id,
    }

    return JSONResponse(
        status_code=exc.http_status_code,
        content=payload,
    )
