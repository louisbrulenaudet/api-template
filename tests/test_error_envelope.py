from typing import Annotated

import pytest
from fastapi import HTTPException, Query
from fastapi.testclient import TestClient

from app.enums.error_codes import ErrorCodes
from app.exceptions.client_initialization_error import ClientInitializationError
from app.exceptions.core_exception import CoreError
from app.main import create_app
from tests.conftest import build_settings

_ENVELOPE_KEYS = {"error", "message", "code", "details", "request_id"}


@pytest.fixture(scope="module")
def failing_client() -> TestClient:
    """A client whose app exposes one route per failure mode."""
    app = create_app(build_settings())

    @app.get("/raise-http-exception")
    async def raise_http_exception() -> None:
        raise HTTPException(status_code=403, detail="nope")

    @app.get("/raise-unexpected")
    async def raise_unexpected() -> None:
        raise RuntimeError("internal detail /srv/secret should not leak")

    @app.get("/needs-int")
    async def needs_int(value: Annotated[int, Query()]) -> dict[str, int]:
        return {"value": value}

    @app.get("/raise-server-core-error")
    async def raise_server_core_error() -> None:
        raise ClientInitializationError("leaky internal reason")

    @app.get("/raise-client-core-error")
    async def raise_client_core_error() -> None:
        raise CoreError("bad field", ErrorCodes.VALIDATION_ERROR, {"field": "email"})

    # `raise_server_exceptions=False` lets the registered catch-all produce a real 500 response
    # instead of TestClient re-raising the exception into the test.
    return TestClient(app, raise_server_exceptions=False)


def test_validation_error_uses_the_envelope(failing_client: TestClient) -> None:
    response = failing_client.get("/needs-int?value=abc")

    assert response.status_code == 422
    body = response.json()
    assert set(body) == _ENVELOPE_KEYS
    assert body["code"] == ErrorCodes.VALIDATION_ERROR
    assert body["error"] == "RequestValidationError"
    # The per-field detail is what makes a 422 actionable, so it must survive re-shaping.
    assert body["details"][0]["loc"] == ["query", "value"]
    assert body["request_id"]


def test_http_exception_uses_the_envelope(failing_client: TestClient) -> None:
    response = failing_client.get("/raise-http-exception")

    assert response.status_code == 403
    body = response.json()
    assert set(body) == _ENVELOPE_KEYS
    assert body["code"] == ErrorCodes.HTTP_ERROR
    assert body["message"] == "nope"


def test_not_found_uses_the_envelope(failing_client: TestClient) -> None:
    response = failing_client.get("/definitely-not-a-route")

    assert response.status_code == 404
    body = response.json()
    assert set(body) == _ENVELOPE_KEYS
    assert body["message"] == "Not Found"


def test_unhandled_exception_is_opaque(failing_client: TestClient) -> None:
    response = failing_client.get("/raise-unexpected")

    assert response.status_code == 500
    body = response.json()
    assert set(body) == _ENVELOPE_KEYS
    assert body["code"] == ErrorCodes.INTERNAL_ERROR
    assert body["details"] is None
    # The whole point: no internal path, no exception text, no traceback on the wire.
    assert "/srv/secret" not in response.text
    assert "RuntimeError" not in response.text


def test_unhandled_exception_still_carries_a_correlation_id(
    failing_client: TestClient,
) -> None:
    """The catch-all runs outside `RequestIDMiddleware`, so it must supply the ID itself."""
    response = failing_client.get("/raise-unexpected", headers={"X-Request-ID": "trace-500"})

    assert response.json()["request_id"] == "trace-500"
    assert response.headers["x-request-id"] == "trace-500"


def test_server_error_core_error_withholds_details(failing_client: TestClient) -> None:
    """A 5xx `CoreError`'s details are internal; they belong in the log, not the response."""
    response = failing_client.get("/raise-server-core-error")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == ErrorCodes.CLIENT_INITIALIZATION_ERROR
    # `ClientInitializationError` stores the underlying exception text in `details`; echoing it
    # would hand an internal failure string to the caller.
    assert body["details"] is None
    assert "leaky internal reason" not in response.text


def test_client_error_core_error_keeps_details(failing_client: TestClient) -> None:
    """A 4xx `CoreError`'s details are client-actionable and must be preserved."""
    response = failing_client.get("/raise-client-core-error")

    assert response.status_code == 400
    assert response.json()["details"] == {"field": "email"}
