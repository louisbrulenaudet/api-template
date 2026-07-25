from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.enums.error_codes import ErrorCodes

__all__ = [
    "ErrorResponse",
]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    error: str = Field(
        description="Exception class name, for coarse client-side branching and log grepping.",
    )
    message: str = Field(
        description="Human-readable, client-safe summary. Never contains secrets or stack traces.",
    )
    code: ErrorCodes = Field(
        description="Stable symbolic code. Prefer branching on this over `error` or `message`.",
    )
    details: dict[str, Any] | list[Any] | str | None = Field(
        default=None,
        description="Structured context: a validation-error list, a mapping, or a string. "
        "Omitted for 5xx responses, whose details are internal and only logged.",
    )
    request_id: str = Field(
        default="",
        description="Correlation ID, matching the `X-Request-ID` response header.",
    )
