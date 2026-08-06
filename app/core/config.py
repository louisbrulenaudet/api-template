import time
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.enums.environment import Environment

__all__ = [
    "Settings",
    "get_settings",
]

_WILDCARD = "*"


def _get_package_version() -> str:
    """Return the version from pyproject.toml.

    Raises:
        TypeError: If `[project].version` is not a string. `tomllib.load` is typed as returning `dict[str, Any]`, so without this check `Settings.version` would silently become an unvalidated `Any` (Pydantic does not validate `default_factory` output).
    """
    pyproject = Path(__file__).parent.parent.parent / "pyproject.toml"
    with pyproject.open("rb") as handle:
        version = tomllib.load(handle)["project"]["version"]

    if not isinstance(version, str):
        raise TypeError(
            f"pyproject.toml [project].version must be a string, got {type(version).__name__}."
        )
    return version


def _split_csv(value: object) -> object:
    """Parse a comma-separated env string into a list, leaving other inputs untouched."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    """Configuration settings for the application, validated by Pydantic.

    Field names map to env vars case-insensitively, so no field needs an `alias=`
    (backend/settings-config).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        populate_by_name=True,
        env_ignore_empty=True,
    )

    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Deployment environment; PRODUCTION enforces the fail-closed guards below.",
    )

    name: str = Field(default="Backend", validation_alias="APP_NAME")
    version: str = Field(default_factory=_get_package_version)
    service_start_time: float = Field(default_factory=time.monotonic, exclude=True)

    api_key: SecretStr = Field(default=SecretStr(""))
    api_client: str = Field(default="")

    force_https: bool = Field(default=False)
    root_path: str = Field(
        default="",
        description="ASGI root_path when mounted under a sub-path by a proxy (see FastAPI docs).",
    )

    # `None` derives from the environment; read via `docs_are_enabled` (backend/settings-config).
    docs_enabled: bool | None = Field(default=None)

    allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: [_WILDCARD])
    allow_credentials: bool = Field(default=False)
    allowed_hosts: Annotated[list[str], NoDecode] = Field(default_factory=lambda: [_WILDCARD])

    log_level: str = Field(default="INFO")
    log_json: bool = Field(
        default=False,
        description="Emit one JSON object per log record; recommended when shipping to a collector.",
    )

    @field_validator("allowed_origins", "allowed_hosts", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Parse comma-separated origin/host env strings into lists."""
        return _split_csv(value)

    @field_validator("log_level", mode="after")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        """Uppercase and validate the log level against the stdlib names."""
        level = value.strip().upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if level not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}, got {value!r}.")
        return level

    @property
    def docs_are_enabled(self) -> bool:
        """Return whether OpenAPI/docs routes should be mounted."""
        if self.docs_enabled is not None:
            return self.docs_enabled
        return not self.environment.is_production

    @model_validator(mode="after")
    def _reject_wildcard_with_credentials(self) -> Self:
        """Fail closed: credentialed CORS must not be combined with wildcard origins.

        Starlette would silently reflect the request's own origin instead (backend/middleware).
        """
        if self.allow_credentials and _WILDCARD in self.allowed_origins:
            raise ValueError(
                "ALLOW_CREDENTIALS cannot be enabled with wildcard ALLOWED_ORIGINS "
                "['*']; specify explicit origins when credentials are allowed."
            )
        return self

    @model_validator(mode="after")
    def _enforce_production_hardening(self) -> Self:
        """Fail closed: refuse to boot a production app that still holds template defaults.

        New "safe locally, unsafe in prod" defaults belong here, not in a comment
        (backend/settings-config).
        """
        if not self.environment.is_production:
            return self

        problems: list[str] = []
        if _WILDCARD in self.allowed_origins:
            problems.append("ALLOWED_ORIGINS must list explicit origins (not '*')")
        if _WILDCARD in self.allowed_hosts:
            problems.append("ALLOWED_HOSTS must list explicit hostnames (not '*')")
        if not self.api_key.get_secret_value():
            problems.append("API_KEY must be set")

        if problems:
            raise ValueError(
                f"Invalid configuration for ENVIRONMENT={self.environment.value}: "
                + "; ".join(problems)
                + ". Set these explicitly, or use a non-production ENVIRONMENT locally."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings for `Depends(get_settings)`."""
    return Settings()
