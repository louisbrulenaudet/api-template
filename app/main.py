from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from aiocache import caches
from aiocache.backends.memory import SimpleMemoryCache
from fastapi import FastAPI

from app.api.v1.router import router as api_router
from app.core.config import Settings, get_settings
from app.core.http_client import create_http_client
from app.exceptions.handlers import register_exception_handlers
from app.middlewares import configure_middleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Configure application lifespan (cache + shared HTTP client)."""
    caches.set_config({"default": {"cache": SimpleMemoryCache, "ttl": 60, "maxsize": 1000}})
    app.state.http_client = create_http_client()
    try:
        yield
    finally:
        await app.state.http_client.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure a FastAPI application instance.

    A factory (rather than a module-level app assembled at import time) keeps construction side-effect free until called and lets tests build a fresh, isolated app. The module-level ``app = create_app()`` below remains the ASGI entrypoint served as ``app.main:app``.

    Args:
        settings: Optional settings override; falls back to the cached ``get_settings()``.

    Returns:
        FastAPI: The configured application, with middleware, exception handlers, and the
            versioned API router wired in.
    """
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.name,
        summary="Minimal, production-ready FastAPI backend with strict Pydantic validation.",
        description="A minimal, production-ready template for building APIs with FastAPI, featuring strict data validation and Docker-based containerization, tailored for express deployment via a secure Cloudflare Tunnel.",
        version=settings.version,
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    configure_middleware(app, settings)
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
