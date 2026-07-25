from enum import StrEnum

__all__ = [
    "Environment",
]


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_production(self) -> bool:
        """Return True when running in the production environment."""
        return self is Environment.PRODUCTION
