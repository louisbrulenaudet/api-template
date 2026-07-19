from unittest.mock import MagicMock, patch

import httpx2
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.http_client import create_http_client, get_http_client
from app.enums.error_codes import ErrorCodes
from app.exceptions.client_initialization_error import ClientInitializationError


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
