from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "PingResponse",
]


class PingResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    status: Literal["ok"] = Field(
        default="ok",
        description="The status of the health check.",
    )

    uptime: int = Field(
        default=0,
        description="The uptime of the service in seconds.",
    )

    timestamp: int = Field(
        default=0,
        description="The current timestamp when the health check was performed.",
    )
