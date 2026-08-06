from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from aiocache import caches
from aiocache.backends.memory import SimpleMemoryCache
from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.api.v1.router import API_V1_PREFIX
from app.api.v1.router import router as api_router
from app.core.config import Settings, get_settings
from app.core.http_client import create_http_client, set_http_client
from app.core.logging_config import configure_logging
from app.dtos.error_response import ErrorResponse
from app.exceptions.handlers import register_exception_handlers
from app.middlewares import configure_middleware

# Documented on every operation so the uniform error envelope is discoverable from the schema
# alone. Route-level `responses=` entries merge over these.
_DEFAULT_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Request validation failed."},
    500: {"model": ErrorResponse, "description": "Unexpected internal error."},
}


def _generate_operation_id(route: APIRoute) -> str:
    """Build a stable, path-free `operationId` for a route."""
    parts = [str(route.tags[0])] if route.tags else []
    parts.append(route.name)
    # `pragma: no branch`: an `APIRoute` always carries at least one method, so the false path is
    # unreachable defensive code - the guard exists only because the attribute is typed as a set.
    if route.methods:  # pragma: no branch
        # `min` keeps the result deterministic when a route declares several methods.
        parts.append(min(route.methods).lower())
    return "_".join(parts)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Configure application lifespan (cache + shared HTTP client)."""
    caches.set_config({"default": {"cache": SimpleMemoryCache, "ttl": 60}})

    # Held in a local, never re-read from `app.state`, for teardown.
    http_client = create_http_client()
    set_http_client(app, http_client)
    try:
        yield
    finally:
        await http_client.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure a FastAPI application instance.

    The module-level ``app = create_app()`` below is the ASGI entrypoint served as ``app.main:app``.
    """
    settings = settings if settings is not None else get_settings()

    configure_logging(settings)

    app = FastAPI(
        title=settings.name,
        summary="Minimal, production-ready FastAPI backend with strict Pydantic validation.",
        description="A minimal, production-ready template for building APIs with FastAPI, featuring strict data validation and Docker-based containerization, tailored for express deployment via a secure Cloudflare Tunnel.",
        version=settings.version,
        lifespan=lifespan,
        # Set when a proxy serves the app under a sub-path it strips before forwarding; makes
        # the docs, `openapi.json` and generated URLs reflect the externally visible prefix.
        root_path=settings.root_path,
        docs_url="/docs" if settings.docs_are_enabled else None,
        openapi_url="/openapi.json" if settings.docs_are_enabled else None,
        redoc_url="/redoc" if settings.docs_are_enabled else None,
        generate_unique_id_function=_generate_operation_id,
        responses=_DEFAULT_ERROR_RESPONSES,
    )

    # Required, not a test affordance: without it the factory is split-brain (backend/middleware).
    app.dependency_overrides[get_settings] = lambda: settings

    configure_middleware(app, settings)
    register_exception_handlers(app)
    app.include_router(api_router, prefix=API_V1_PREFIX)

    return app


app = create_app()
