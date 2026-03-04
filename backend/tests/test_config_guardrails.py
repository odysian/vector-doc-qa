"""Runtime config guardrail tests for strict and non-strict environments."""

import pytest
from pydantic import ValidationError

from app.constants import MAX_CHUNK_OVERLAP, MAX_CHUNK_SIZE
from app.config import Settings

SAFE_SECRET_KEY = "0123456789abcdef0123456789abcdef"
SAFE_DATABASE_URL = (
    "postgresql://app_user:super-strong-password@10.10.10.10:5432/quaero"
    "?options=-c%20search_path=quaero,public"
)


def _make_settings(**overrides: object) -> Settings:
    """Build Settings from explicit values without reading env files."""
    return Settings.model_validate(overrides)


def test_production_rejects_default_secret_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make_settings(
            app_env="production",
            secret_key="dev-secret-key-change-in-production",
            database_url=SAFE_DATABASE_URL,
        )

    assert "SECRET_KEY uses a forbidden dev/default value" in str(exc_info.value)


def test_production_rejects_default_database_url_patterns() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make_settings(
            app_env="production",
            secret_key=SAFE_SECRET_KEY,
            database_url="postgresql://postgres:postgres@localhost:5434/document_intelligence",
        )

    error = str(exc_info.value)
    assert "DATABASE_URL must not use localhost/loopback" in error
    assert "DATABASE_URL must not use default dev credentials" in error
    assert "DATABASE_URL must not use the default dev database name" in error


def test_production_accepts_safe_runtime_values() -> None:
    settings = _make_settings(
        app_env="production",
        secret_key=SAFE_SECRET_KEY,
        database_url=SAFE_DATABASE_URL,
    )

    assert settings.is_strict_environment is True


def test_development_allows_local_defaults() -> None:
    settings = _make_settings(
        app_env="development",
        secret_key="dev-secret-key-change-in-production",
        database_url="postgresql://postgres:postgres@localhost:5434/document_intelligence",
    )

    assert settings.is_strict_environment is False
    assert settings.secret_key == "dev-secret-key-change-in-production"
    assert "localhost" in settings.database_url


def test_app_env_is_case_insensitive_for_strict_mode() -> None:
    with pytest.raises(ValidationError):
        _make_settings(
            app_env="Production",
            secret_key="dev-secret-key-change-in-production",
            database_url=SAFE_DATABASE_URL,
        )


def test_rejects_non_positive_chunk_size() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make_settings(chunk_size=0)

    assert "CHUNK_SIZE must be greater than 0" in str(exc_info.value)


def test_rejects_negative_chunk_overlap() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make_settings(chunk_overlap=-1)

    assert "CHUNK_OVERLAP must be greater than or equal to 0" in str(exc_info.value)


def test_rejects_chunk_overlap_gte_chunk_size() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make_settings(chunk_size=100, chunk_overlap=100)

    assert "CHUNK_OVERLAP must be smaller than CHUNK_SIZE" in str(exc_info.value)


def test_accepts_valid_chunk_config_bounds() -> None:
    settings = _make_settings(chunk_size=1, chunk_overlap=0)
    assert settings.chunk_size == 1
    assert settings.chunk_overlap == 0


def test_rejects_chunk_size_above_max() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make_settings(
            chunk_size=MAX_CHUNK_SIZE + 1,
            chunk_overlap=MAX_CHUNK_OVERLAP,
        )

    assert f"CHUNK_SIZE must be less than or equal to {MAX_CHUNK_SIZE}" in str(
        exc_info.value
    )


def test_rejects_chunk_overlap_above_max() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make_settings(
            chunk_size=MAX_CHUNK_SIZE,
            chunk_overlap=MAX_CHUNK_OVERLAP + 1,
        )

    assert (
        f"CHUNK_OVERLAP must be less than or equal to {MAX_CHUNK_OVERLAP}"
        in str(exc_info.value)
    )


def test_accepts_chunk_config_at_upper_bounds() -> None:
    settings = _make_settings(
        chunk_size=MAX_CHUNK_SIZE,
        chunk_overlap=MAX_CHUNK_OVERLAP,
    )

    assert settings.chunk_size == MAX_CHUNK_SIZE
    assert settings.chunk_overlap == MAX_CHUNK_OVERLAP
