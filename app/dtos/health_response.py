from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "HealthResponse",
]


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    status: Literal["ok"] = Field(
        default="ok",
        description="The health status of the service.",
    )
