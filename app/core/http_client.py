import httpx2
from fastapi import FastAPI, Request

from app.exceptions.client_initialization_error import ClientInitializationError

__all__ = [
    "create_http_client",
    "get_http_client",
    "set_http_client",
]

# The two functions below are the ONLY place `app.state` is touched for this key; the read
# re-establishes the type at runtime because the state bag is untyped (backend/middleware).
_STATE_ATTR = "http_client"


def create_http_client() -> httpx2.AsyncClient:
    """Create a shared outbound HTTP client with pooling, HTTP/2, and timeouts."""
    try:
        return httpx2.AsyncClient(
            http2=True,
            timeout=httpx2.Timeout(10.0, connect=5.0),
            limits=httpx2.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=5.0,
            ),
        )
    except Exception as exc:
        raise ClientInitializationError(exc) from exc


def set_http_client(app: FastAPI, client: httpx2.AsyncClient) -> None:
    """Publish the lifespan-scoped client on ``app.state``."""
    setattr(app.state, _STATE_ATTR, client)


def get_http_client(request: Request) -> httpx2.AsyncClient:
    """Return the lifespan-scoped `httpx2.AsyncClient` from app state.

    Raises:
        ClientInitializationError: If no client is on `app.state`, so a missing lifespan is a typed 500 rather than an `AttributeError` escaping the untyped state bag.
    """
    client = getattr(request.app.state, _STATE_ATTR, None)
    if not isinstance(client, httpx2.AsyncClient):
        raise ClientInitializationError(
            f"`app.state.{_STATE_ATTR}` is missing or not an `httpx2.AsyncClient`; "
            "the application lifespan did not run."
        )
    return client
