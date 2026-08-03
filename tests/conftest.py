from collections.abc import AsyncGenerator, Generator

import httpx2
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.enums.error_codes import ErrorCodes
from app.exceptions.core_exception import CoreError
from app.main import create_app

TEST_API_KEY = "test-api-key"


def build_settings(**overrides: object) -> Settings:
    """Build isolated `Settings` for a test.

    Uses `model_validate` rather than `Settings(...)` deliberately: the constructor consults the environment and `.env`, so a developer's untracked local file could decide whether the suite passes. `model_validate` validates only the mapping given here - every field not listed falls back to its declared default - while still running the field and model validators, including the fail-closed production guards.

    Args:
        **overrides: Field-name overrides (e.g. `force_https=True`).

    Returns:
        Settings: A fresh, environment-independent settings object.
    """
    data: dict[str, object] = {
        "name": "Test Backend",
        "api_key": TEST_API_KEY,
        **overrides,
    }
    return Settings.model_validate(data)


def _diagnostics_router() -> APIRouter:
    """Return a router with routes that deliberately fail, for exercising the handlers.

    Registered on the app the fixtures build rather than on the imported `app` singleton. The previous approach mutated that module-level object from an autouse fixture, which meant the test suite's app was not the app `create_app()` produces.
    """
    router = APIRouter(tags=["Diagnostics"])

    @router.get("/raise-core-error")
    async def raise_core_error() -> None:
        raise CoreError(
            "fail",
            ErrorCodes.CLIENT_INITIALIZATION_ERROR,
            {"foo": "bar"},
        )

    return router


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Session-wide settings used to build the test application."""
    return build_settings()


@pytest.fixture(scope="session")
def app(settings: Settings) -> FastAPI:
    """The application under test, built through the real factory."""
    application = create_app(settings)
    application.include_router(_diagnostics_router())
    return application


@pytest.fixture(scope="module")
def client(app: FastAPI) -> Generator[TestClient]:
    """Reusable TestClient that triggers the app lifespan (startup/shutdown)."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[httpx2.AsyncClient]:
    """An async ASGI client, for exercising routes from `async def` tests.

    `ASGITransport` speaks to the app in-process without a socket, but it does not run the lifespan - hence the explicit `lifespan_context`, without which `app.state.http_client` would be missing and `get_http_client` would raise.
    """
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
