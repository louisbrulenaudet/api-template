import time
import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings.main import SettingsConfigDict

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

    name: str = Field(default="Backend", alias="APP_NAME")
    version: str = Field(default_factory=_get_package_version)
    service_start_time: float = Field(default_factory=time.time, exclude=True)
    api_key: str = Field(default="", alias="API_KEY")
    api_client: str = Field(default="", alias="API_CLIENT")
    force_https: bool = Field(default=False, alias="FORCE_HTTPS")

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings for `Depends(get_settings)`."""
    return Settings()
