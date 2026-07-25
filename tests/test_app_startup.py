from fastapi import FastAPI
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.enums.error_codes import ErrorCodes
from app.main import create_app
from tests.conftest import build_settings


def test_force_https_registers_https_redirect_middleware() -> None:
    """`FORCE_HTTPS` should add the HTTPS redirect middleware.

    Built through `create_app` with explicit settings. The previous version mutated the environment and called `importlib.reload(app.main)`, which rebound the module-level `app` other tests had already captured.
    """
    app = create_app(build_settings(force_https=True))

    assert any(m.cls is HTTPSRedirectMiddleware for m in app.user_middleware)


def test_https_redirect_absent_by_default() -> None:
    """The redirect middleware must not be registered unless asked for."""
    app = create_app(build_settings())

    assert not any(m.cls is HTTPSRedirectMiddleware for m in app.user_middleware)


def test_factory_settings_reach_route_dependencies() -> None:
    """`create_app(settings)` must bind those settings to `Depends(get_settings)`.

    Regression test: the factory used to set `app.title` from the passed settings while every handler kept reading the process-wide `lru_cache`d `get_settings()`, so a test could configure an app and silently exercise different settings.
    """
    settings = build_settings(name="Factory Bound")
    app = create_app(settings)

    resolved = app.dependency_overrides[get_settings]()

    assert app.title == "Factory Bound"
    assert resolved is settings
    assert resolved is not get_settings()


def test_core_error_handler(client: TestClient) -> None:
    response = client.get("/raise-core-error")

    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "CoreError"
    assert data["message"] == "fail"
    assert data["code"] == ErrorCodes.CLIENT_INITIALIZATION_ERROR
    assert data["details"] == {"foo": "bar"}


def test_docs_enabled_by_default(app: FastAPI, client: TestClient) -> None:
    """A non-production app publishes its schema and both doc UIs."""
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200


def test_docs_disabled_in_production() -> None:
    """Production must not publish the schema unless explicitly told to."""
    app = create_app(
        build_settings(
            environment="production",
            allowed_origins=["https://app.example"],
            allowed_hosts=["app.example"],
        )
    )

    # `base_url` must match `allowed_hosts`, or TrustedHostMiddleware answers 400 before the
    # router is ever consulted.
    with TestClient(app, base_url="http://app.example") as production_client:
        assert production_client.get("/openapi.json").status_code == 404
        assert production_client.get("/docs").status_code == 404
        # `redoc_url` is gated too - FastAPI already hides redoc when `openapi_url` is None,
        # but pinning it here keeps that coupling from silently changing.
        assert production_client.get("/redoc").status_code == 404


def test_operation_ids_are_path_independent(app: FastAPI) -> None:
    """`operationId`s must not embed the URL, so generated clients survive path edits."""
    schema = app.openapi()
    operation_ids = {
        operation["operationId"] for path in schema["paths"].values() for operation in path.values()
    }

    assert "Health_ping_get" in operation_ids
    assert "Health_health_get" in operation_ids
    assert not any("api_v1" in operation_id for operation_id in operation_ids)


def test_error_response_is_documented_in_openapi(app: FastAPI) -> None:
    """The error envelope must be discoverable from the schema alone."""
    schema = app.openapi()

    assert "ErrorResponse" in schema["components"]["schemas"]
    ping_responses = schema["paths"]["/api/v1/ping"]["get"]["responses"]
    assert "500" in ping_responses


def test_settings_are_not_the_global_cache(settings: Settings) -> None:
    """The suite must run on its own settings, never the env-derived singleton."""
    assert settings is not get_settings()
    assert settings.name == "Test Backend"
