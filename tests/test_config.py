import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings

_ENV_KEYS = ("ALLOWED_ORIGINS", "ALLOW_CREDENTIALS", "API_KEY", "DOCS_ENABLED")


def _settings(monkeypatch, tmp_path, **env):
    # chdir to an empty dir so a developer's local .env can't affect the result,
    # then drive the values purely through environment variables.
    monkeypatch.chdir(tmp_path)
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_allowed_origins_default_is_wildcard(monkeypatch, tmp_path):
    settings = _settings(monkeypatch, tmp_path)
    assert settings.allowed_origins == ["*"]
    assert settings.allow_credentials is False
    assert settings.docs_enabled is True


def test_allowed_origins_parsed_from_comma_separated_env(monkeypatch, tmp_path):
    settings = _settings(
        monkeypatch,
        tmp_path,
        ALLOWED_ORIGINS="https://a.example, https://b.example",
    )
    assert settings.allowed_origins == ["https://a.example", "https://b.example"]


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
