import httpx2
from fastapi import FastAPI, Request

from app.exceptions.client_initialization_error import ClientInitializationError

__all__ = [
    "create_http_client",
    "get_http_client",
    "set_http_client",
]

# Starlette's `State` is an untyped attribute bag - `__getattr__` returns `Any` - so
# neither the key nor the value's type can be verified at a call site: a plain
# `return request.app.state.http_client` type checks against *any* annotation.
# `set_http_client` / `get_http_client` are the only place that boundary is crossed,
# and the read re-establishes the type with a runtime `isinstance` check instead of
# asserting it in an annotation ty cannot confirm.
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
    """Publish the lifespan-scoped client on ``app.state``.

    Args:
        app: The application whose state holds the shared client.
        client: The client created for this lifespan.
    """
    setattr(app.state, _STATE_ATTR, client)


def get_http_client(request: Request) -> httpx2.AsyncClient:
    """Return the lifespan-scoped `httpx2.AsyncClient` from app state.

    Args:
        request: The incoming request, used to reach the application state.

    Returns:
        httpx2.AsyncClient: The shared outbound client published by the lifespan.

    Raises:
        ClientInitializationError: If no client is on `app.state` - typically an app built without running its lifespan. Fails as a typed 500 rather than leaking an `AttributeError` from the untyped state bag into a handler.
    """
    client = getattr(request.app.state, _STATE_ATTR, None)
    if not isinstance(client, httpx2.AsyncClient):
        raise ClientInitializationError(
            f"`app.state.{_STATE_ATTR}` is missing or not an `httpx2.AsyncClient`; "
            "the application lifespan did not run."
        )
    return client
