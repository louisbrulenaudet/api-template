import secrets
from typing import Annotated

from fastapi import Depends
from fastapi.security import APIKeyHeader

from app.core.config import Settings, get_settings
from app.exceptions.authentication_error import AuthenticationError

__all__ = [
    "API_KEY_HEADER_NAME",
    "require_api_key",
]

API_KEY_HEADER_NAME = "X-API-Key"

# `auto_error=False` is required to keep failures inside the `ErrorResponse` envelope
# (backend/fastapi-routes).
_api_key_header = APIKeyHeader(
    name=API_KEY_HEADER_NAME,
    auto_error=False,
    description="Shared secret issued to API clients.",
)


async def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    provided: Annotated[str | None, Depends(_api_key_header)] = None,
) -> None:
    """Reject the request unless it carries the configured API key.

    Apply per-router, never globally - the probes must stay unauthenticated (backend/fastapi-routes).

    Raises:
        AuthenticationError: If the server has no key configured, or the supplied key is missing or
            does not match.
    """
    expected = settings.api_key.get_secret_value()
    if not expected:
        # Fail closed: an unset API_KEY must never mean "allow everyone".
        raise AuthenticationError("Server API key is not configured.")

    # `compare_digest`, never `==`: constant-time, so latency cannot leak a prefix match. It needs
    # bytes for non-ASCII safety, hence the encode.
    if provided is None or not secrets.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        raise AuthenticationError("Missing or invalid API key.")
