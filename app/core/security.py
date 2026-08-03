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

# `auto_error=False`: on a missing header FastAPI would otherwise raise its own 403 with a
# `{"detail": ...}` body, bypassing the uniform `ErrorResponse` envelope. Returning `None`
# instead lets `require_api_key` raise `AuthenticationError` so every failure - missing or
# wrong - looks the same on the wire. The scheme is still published to OpenAPI, so Swagger UI
# renders the padlock and an "Authorize" box.
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

    Apply it where it belongs rather than globally - the health/ping probes must stay unauthenticated for Docker and Kubernetes:

        router = APIRouter(dependencies=[Depends(require_api_key)])

    Args:
        settings: Supplies the expected key.
        provided: The `X-API-Key` header value, or `None` when absent.

    Raises:
        AuthenticationError: If the server has no key configured, or the supplied key is
            missing or does not match.
    """
    expected = settings.api_key.get_secret_value()
    if not expected:
        # Fail closed: an unset API_KEY must never mean "allow everyone".
        raise AuthenticationError("Server API key is not configured.")

    # `compare_digest` keeps the comparison constant-time, so response latency does not leak
    # how many leading characters of the key were correct. It requires bytes for non-ASCII
    # safety, hence the explicit encode.
    if provided is None or not secrets.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        raise AuthenticationError("Missing or invalid API key.")
