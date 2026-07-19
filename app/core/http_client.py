import httpx2
from fastapi import Request

from app.exceptions.client_initialization_error import ClientInitializationError

__all__ = [
    "create_http_client",
    "get_http_client",
]


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


def get_http_client(request: Request) -> httpx2.AsyncClient:
    """Return the lifespan-scoped `httpx2.AsyncClient` from app state."""
    return request.app.state.http_client
