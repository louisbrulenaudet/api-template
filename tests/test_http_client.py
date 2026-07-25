from unittest.mock import MagicMock, patch

import httpx2
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.http_client import create_http_client, get_http_client, set_http_client
from app.enums.error_codes import ErrorCodes
from app.exceptions.client_initialization_error import ClientInitializationError


def _request_for(app: FastAPI) -> Request:
    """Build a request stub backed by a real app, so `app.state` behaves like Starlette's."""
    request = MagicMock(spec=Request)
    request.app = app
    return request


def test_lifespan_exposes_shared_http_client(client: TestClient) -> None:
    """Lifespan should create a live httpx2.AsyncClient on app.state."""
    app = client.app
    assert isinstance(app, FastAPI)
    http_client = app.state.http_client
    assert isinstance(http_client, httpx2.AsyncClient)
    assert not http_client.is_closed


def test_get_http_client_returns_app_state_client() -> None:
    """Dependency should return the lifespan-scoped client from request.app.state."""
    expected = MagicMock(spec=httpx2.AsyncClient)
    request = MagicMock(spec=Request)
    request.app.state.http_client = expected

    assert get_http_client(request) is expected


def test_set_http_client_round_trips_through_app_state() -> None:
    """set_http_client should publish the exact client get_http_client hands back."""
    app = FastAPI()
    expected = MagicMock(spec=httpx2.AsyncClient)

    set_http_client(app, expected)

    assert get_http_client(_request_for(app)) is expected


def test_get_http_client_without_lifespan_raises() -> None:
    """A missing client is a typed 500, not an AttributeError from the state bag."""
    with pytest.raises(ClientInitializationError) as exc_info:
        get_http_client(_request_for(FastAPI()))

    assert exc_info.value.code == ErrorCodes.CLIENT_INITIALIZATION_ERROR


def test_get_http_client_rejects_wrong_state_type() -> None:
    """State holding a non-client must not be handed out as an httpx2.AsyncClient."""
    app = FastAPI()
    app.state.http_client = "not a client"

    with pytest.raises(ClientInitializationError):
        get_http_client(_request_for(app))


def test_create_http_client_raises_client_initialization_error() -> None:
    """Construction failures should surface as ClientInitializationError."""
    with (
        patch(
            "app.core.http_client.httpx2.AsyncClient",
            side_effect=RuntimeError("boom"),
        ),
        pytest.raises(ClientInitializationError) as exc_info,
    ):
        create_http_client()

    err = exc_info.value
    assert err.code == ErrorCodes.CLIENT_INITIALIZATION_ERROR
    assert "boom" in str(err.details)
    assert isinstance(err.__cause__, RuntimeError)
