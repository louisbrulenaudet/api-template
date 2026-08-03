from app.enums.error_codes import ErrorCodes
from app.exceptions.core_exception import CoreError

__all__ = [
    "AuthenticationError",
]


class AuthenticationError(CoreError):
    """Raised when a request carries a missing or invalid credential."""

    http_status_code: int = 401

    def __init__(self, details: str | None = None) -> None:
        """Create an error indicating the caller could not be authenticated.

        Args:
            details: Client-safe context. Never include the expected or supplied secret.
        """
        super().__init__(
            "Authentication failed.",
            ErrorCodes.AUTHENTICATION_ERROR,
            details=details,
        )
