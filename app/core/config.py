import time
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

__all__ = [
    "Settings",
    "get_settings",
]


def _get_package_version() -> str:
    """Return the version from pyproject.toml."""
    pyproject = Path(__file__).parent.parent.parent / "pyproject.toml"
    with pyproject.open("rb") as f:
        return tomllib.load(f)["project"]["version"]


class Settings(BaseSettings):
    """Configuration settings for the application, validated by Pydantic."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    name: str = Field(default="Backend", alias="APP_NAME")
    version: str = Field(default_factory=_get_package_version)
    service_start_time: float = Field(default_factory=time.time, exclude=True)
    # Secret: masked in logs/repr; read the raw value via `api_key.get_secret_value()`.
    api_key: SecretStr = Field(default=SecretStr(""), alias="API_KEY")
    api_client: str = Field(default="", alias="API_CLIENT")
    force_https: bool = Field(default=False, alias="FORCE_HTTPS")
    docs_enabled: bool = Field(default=True, alias="DOCS_ENABLED")

    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["*"],
        alias="ALLOWED_ORIGINS",
    )
    allow_credentials: bool = Field(default=False, alias="ALLOW_CREDENTIALS")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Parse a comma-separated ALLOWED_ORIGINS env string into a list of origins."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _reject_wildcard_with_credentials(self) -> Self:
        """Fail closed: credentialed CORS must not be combined with wildcard origins.

        Starlette silently reflects the request origin when `allow_origins=["*"]` and `allow_credentials=True`, effectively allowing any site to send credentialed requests. Reject that combination at startup instead.
        """
        if self.allow_credentials and "*" in self.allowed_origins:
            raise ValueError(
                "ALLOW_CREDENTIALS cannot be enabled with wildcard ALLOWED_ORIGINS "
                "['*']; specify explicit origins when credentials are allowed."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings for `Depends(get_settings)`."""
    return Settings()
