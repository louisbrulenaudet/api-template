from __future__ import annotations

from typing import Any, override

from app.enums.error_codes import ErrorCodes

__all__ = [
    "CoreError",
]


class CoreError(Exception):
    """Base class for application-specific errors: message, `ErrorCodes` code, optional details.

    Subclasses override `http_status_code` to change the status the global handler returns.
    """

    http_status_code: int = 400
    message: str
    code: ErrorCodes
    details: dict[str, Any] | str | None

    def __init__(
        self,
        message: str,
        code: ErrorCodes,
        details: dict[str, Any] | str | None = None,
    ) -> None:
        """Initialize a CoreError with an error message, code, and optional details."""
        self.message = message
        self.code = code
        self.details = details

    @override
    def __str__(self) -> str:
        """Return the error as `Class: message [Code: CODE] Details: ...`."""
        detail_part = f" Details: {self.details}" if self.details else ""
        return f"{self.__class__.__name__}: {self.message} [Code: {self.code}]{detail_part}"

    # No `to_dict()` - `ErrorResponse` is the only owner of the wire shape (backend/exceptions).
