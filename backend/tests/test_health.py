"""Tests for the /health endpoint response contract."""

from unittest.mock import patch

from app.config import settings


class _HealthyConnection:
    """Connection double that succeeds for SELECT 1 health probes."""

    async def execute(self, _statement) -> None:  # type: ignore[no-untyped-def]
        return None


class _HealthyConnectionContext:
    """Async context manager that yields a healthy connection."""

    async def __aenter__(self) -> _HealthyConnection:
        return _HealthyConnection()

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # type: ignore[no-untyped-def]
        return False


class _FailingConnectionContext:
    """Async context manager that raises when connecting to the DB."""

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        raise RuntimeError("database unavailable")

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # type: ignore[no-untyped-def]
        return False


class _HealthyEngine:
    """Engine double that returns a healthy DB connection context."""

    def connect(self) -> _HealthyConnectionContext:
        return _HealthyConnectionContext()


class _FailingEngine:
    """Engine double that raises on DB connect."""

    def connect(self) -> _FailingConnectionContext:
        return _FailingConnectionContext()


class TestHealthCheck:
    """GET /health"""

    async def test_health_success_redacts_upload_directory(self, client) -> None:
        with patch("app.main.async_engine", new=_HealthyEngine()):
            response = await client.get("/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "healthy"
        assert payload["database"] == "connected"
        assert payload["max_file_size_mb"] == settings.max_file_size / 1024 / 1024
        assert "upload_dir" not in payload

    async def test_health_failure_redacts_upload_directory(self, client) -> None:
        with patch("app.main.async_engine", new=_FailingEngine()):
            response = await client.get("/health")

        assert response.status_code == 503
        payload = response.json()
        assert payload["status"] == "unhealthy"
        assert payload["database"] == "error"
        assert payload["max_file_size_mb"] == settings.max_file_size / 1024 / 1024
        assert "upload_dir" not in payload
