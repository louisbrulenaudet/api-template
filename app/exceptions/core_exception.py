from __future__ import annotations

from typing import Any, override

from app.enums.error_codes import ErrorCodes

__all__ = [
    "CoreError",
]


class CoreError(Exception):
    """A custom exception class for handling application-specific errors.

    This exception includes an error message, an error code, and optional details.

    Attributes:
        message (str): A descriptive error message.
        code (ErrorCodes): An enumerated error code representing the specific error type.
        details (dict[str, Any] | str | None): Additional details about the error.
        http_status_code (int): HTTP status code returned by the global exception handler. Override this class attribute in subclasses to change the response status.
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
        """Initialize a CoreError instance with an error message, code, and optional details.

        Args:
            message (str): The error message.
            code (ErrorCodes): A predefined error code representing the error type.
            details (dict[str, Any] | str | None, optional): Additional information about the error.
                Can be a dictionary, a string, or None. Defaults to None.
        """
        self.message = message
        self.code = code
        self.details = details

    @override
    def __str__(self) -> str:
        """Return a string representation of the error, including the message, code, and optional details.

        Returns:
            str: A formatted string describing the error.

        Example:
            >>> error = CoreError(
            ...     "Validation failed",
            ...     ErrorCodes.VALIDATION_ERROR,
            ...     {"field": "email"},
            ... )
            >>> print(str(error))
            "CoreError: Validation failed [Code: VALIDATION_ERROR] Details: {'field': 'email'}"
        """
        detail_part = f" Details: {self.details}" if self.details else ""
        return f"{self.__class__.__name__}: {self.message} [Code: {self.code}]{detail_part}"

    # No `to_dict()`: the client-facing shape has exactly one owner,
    # `app.dtos.error_response.ErrorResponse`, built by the handlers in
    # `app/exceptions/handlers.py`. A second serializer here drifted from it silently - it had no
    # `request_id`, and it echoed `details` on 5xx responses, which the handler now withholds.
