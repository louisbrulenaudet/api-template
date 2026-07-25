import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings, _get_package_version
from app.enums.environment import Environment

_ENV_KEYS = (
    "ALLOWED_ORIGINS",
    "ALLOWED_HOSTS",
    "ALLOW_CREDENTIALS",
    "API_KEY",
    "DOCS_ENABLED",
    "ENVIRONMENT",
    "LOG_LEVEL",
)


def _settings(monkeypatch, tmp_path, **env):
    # chdir to an empty dir so a developer's local .env can't affect the result,
    # then drive the values purely through environment variables.
    monkeypatch.chdir(tmp_path)
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_defaults_are_development(monkeypatch, tmp_path):
    settings = _settings(monkeypatch, tmp_path)

    assert settings.environment is Environment.DEVELOPMENT
    assert settings.allowed_origins == ["*"]
    assert settings.allowed_hosts == ["*"]
    assert settings.allow_credentials is False
    assert settings.docs_are_enabled is True


def test_env_vars_map_to_fields_without_aliases(monkeypatch, tmp_path):
    """Field names match env vars case-insensitively, so no `alias=` is needed."""
    settings = _settings(monkeypatch, tmp_path, API_KEY="k", LOG_LEVEL="debug")

    assert settings.api_key.get_secret_value() == "k"
    assert settings.log_level == "DEBUG"


def test_app_name_alias_still_applies(monkeypatch, tmp_path):
    """`name` is the one field whose env var (`APP_NAME`) differs from the field name."""
    monkeypatch.setenv("APP_NAME", "Aliased")
    settings = _settings(monkeypatch, tmp_path)

    assert settings.name == "Aliased"
    monkeypatch.delenv("APP_NAME", raising=False)


def test_construction_by_field_name_is_honoured(monkeypatch, tmp_path):
    """Regression: `alias=` without `populate_by_name` silently ignored the kwarg.

    It returned the default instead of raising, so a test could configure a value and quietly exercise a different one. Init kwargs outrank env vars, so this asserts the constructor path specifically rather than going through `model_validate`.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("APP_NAME", raising=False)

    settings = Settings(name="ByFieldName")

    assert settings.name == "ByFieldName"


def test_allowed_origins_parsed_from_comma_separated_env(monkeypatch, tmp_path):
    settings = _settings(
        monkeypatch,
        tmp_path,
        ALLOWED_ORIGINS="https://a.example, https://b.example",
    )

    assert settings.allowed_origins == ["https://a.example", "https://b.example"]


def test_allowed_hosts_parsed_from_comma_separated_env(monkeypatch, tmp_path):
    settings = _settings(monkeypatch, tmp_path, ALLOWED_HOSTS="a.example, b.example")

    assert settings.allowed_hosts == ["a.example", "b.example"]


def test_wildcard_origins_with_credentials_is_rejected(monkeypatch, tmp_path):
    with pytest.raises(ValidationError, match="ALLOW_CREDENTIALS"):
        _settings(monkeypatch, tmp_path, ALLOWED_ORIGINS="*", ALLOW_CREDENTIALS="true")


def test_explicit_origins_with_credentials_allowed(monkeypatch, tmp_path):
    settings = _settings(
        monkeypatch,
        tmp_path,
        ALLOWED_ORIGINS="https://app.example",
        ALLOW_CREDENTIALS="true",
    )

    assert settings.allow_credentials is True
    assert settings.allowed_origins == ["https://app.example"]


def test_api_key_is_secret_and_not_leaked_in_repr(monkeypatch, tmp_path):
    settings = _settings(monkeypatch, tmp_path, API_KEY="super-secret-value")

    assert isinstance(settings.api_key, SecretStr)
    assert settings.api_key.get_secret_value() == "super-secret-value"
    assert "super-secret-value" not in repr(settings)


def test_invalid_log_level_is_rejected(monkeypatch, tmp_path):
    with pytest.raises(ValidationError, match="LOG_LEVEL"):
        _settings(monkeypatch, tmp_path, LOG_LEVEL="chatty")


def test_empty_api_key_env_is_treated_as_unset(monkeypatch, tmp_path):
    """`env_ignore_empty` makes a blank `API_KEY=` in a copied .env read as missing."""
    settings = _settings(monkeypatch, tmp_path, API_KEY="")

    assert settings.api_key.get_secret_value() == ""


class TestProductionFailsClosed:
    """Production must refuse to boot while holding permissive template defaults."""

    def test_wildcard_origins_rejected(self, monkeypatch, tmp_path):
        with pytest.raises(ValidationError, match="ALLOWED_ORIGINS"):
            _settings(monkeypatch, tmp_path, ENVIRONMENT="production", API_KEY="k")

    def test_wildcard_hosts_rejected(self, monkeypatch, tmp_path):
        with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
            _settings(
                monkeypatch,
                tmp_path,
                ENVIRONMENT="production",
                API_KEY="k",
                ALLOWED_ORIGINS="https://a.example",
            )

    def test_missing_api_key_rejected(self, monkeypatch, tmp_path):
        with pytest.raises(ValidationError, match="API_KEY"):
            _settings(
                monkeypatch,
                tmp_path,
                ENVIRONMENT="production",
                ALLOWED_ORIGINS="https://a.example",
                ALLOWED_HOSTS="a.example",
            )

    def test_fully_configured_production_boots(self, monkeypatch, tmp_path):
        settings = _settings(
            monkeypatch,
            tmp_path,
            ENVIRONMENT="production",
            ALLOWED_ORIGINS="https://a.example",
            ALLOWED_HOSTS="a.example",
            API_KEY="k",
        )

        assert settings.environment.is_production is True
        # Docs default to off in production...
        assert settings.docs_are_enabled is False

    def test_docs_can_be_published_deliberately(self, monkeypatch, tmp_path):
        settings = _settings(
            monkeypatch,
            tmp_path,
            ENVIRONMENT="production",
            ALLOWED_ORIGINS="https://a.example",
            ALLOWED_HOSTS="a.example",
            API_KEY="k",
            DOCS_ENABLED="true",
        )

        # ...but an explicit opt-in still wins, in either direction.
        assert settings.docs_are_enabled is True


def test_non_string_pyproject_version_is_rejected(monkeypatch):
    """`tomllib.load` is typed as returning `Any`, so the value must be checked at runtime.

    Without the guard, `Settings.version` would silently become an unvalidated `Any` - Pydantic does not validate `default_factory` output.
    """
    monkeypatch.setattr(
        "app.core.config.tomllib.load",
        lambda _: {"project": {"version": 1}},
    )

    with pytest.raises(TypeError, match="must be a string"):
        _get_package_version()
