"""Tests for the /health endpoint response contract."""

import asyncio
from unittest.mock import AsyncMock, patch


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


class _HealthyPool:
    """Redis pool double that returns a healthy connection."""

    async def ping(self):
        return None

    async def close(self):
        return None


class _FailingPool:
    """Redis pool double that fails ping."""

    async def ping(self):
        raise RuntimeError("redis unavailable")

    async def close(self):
        return None


class _TimeoutPool:
    """Redis pool double that raises TimeoutError, simulating asyncio.wait_for firing."""

    async def ping(self):
        raise asyncio.TimeoutError("redis probe timed out")

    async def close(self):
        return None


class _TimeoutConnectionContext:
    """Async context manager that raises TimeoutError on enter, simulating a hung DB connect."""

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        raise asyncio.TimeoutError("db probe timed out")

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # type: ignore[no-untyped-def]
        return False


class _TimeoutEngine:
    """Engine double that times out on DB connect."""

    def connect(self) -> _TimeoutConnectionContext:
        return _TimeoutConnectionContext()


class TestHealthCheck:
    """GET /health"""

    async def test_health_success_redacts_upload_directory(self, client) -> None:
        with patch("app.main.async_engine", new=_HealthyEngine()), patch(
            "app.main.create_pool", new=AsyncMock(return_value=_HealthyPool())
        ):
            response = await client.get("/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "healthy"
        assert payload["database"] == "connected"
        assert payload["redis"] == "connected"
        assert "upload_dir" not in payload

    async def test_health_failure_redacts_upload_directory(self, client) -> None:
        with patch("app.main.async_engine", new=_FailingEngine()), patch(
            "app.main.create_pool", new=AsyncMock(return_value=_HealthyPool())
        ):
            response = await client.get("/health")

        assert response.status_code == 503
        payload = response.json()
        assert payload["status"] == "unhealthy"
        assert payload["database"] == "disconnected"
        assert payload["redis"] == "connected"
        assert "upload_dir" not in payload

    async def test_health_returns_degraded_when_redis_is_down(self, client) -> None:
        with patch("app.main.async_engine", new=_HealthyEngine()), patch(
            "app.main.create_pool", new=AsyncMock(return_value=_FailingPool())
        ):
            response = await client.get("/health")

        assert response.status_code == 503
        payload = response.json()
        assert payload["status"] == "degraded"
        assert payload["database"] == "connected"
        assert payload["redis"] == "disconnected"

    async def test_health_returns_degraded_when_redis_times_out(self, client) -> None:
        """asyncio.TimeoutError from Redis probe is caught and returns 503 degraded."""
        with patch("app.main.async_engine", new=_HealthyEngine()), patch(
            "app.main.create_pool", new=AsyncMock(return_value=_TimeoutPool())
        ):
            response = await client.get("/health")

        assert response.status_code == 503
        payload = response.json()
        assert payload["status"] == "degraded"
        assert payload["database"] == "connected"
        assert payload["redis"] == "disconnected"

    async def test_health_returns_unhealthy_when_db_times_out(self, client) -> None:
        """asyncio.TimeoutError from DB probe is caught and returns 503 unhealthy."""
        with patch("app.main.async_engine", new=_TimeoutEngine()), patch(
            "app.main.create_pool", new=AsyncMock(return_value=_HealthyPool())
        ):
            response = await client.get("/health")

        assert response.status_code == 503
        payload = response.json()
        assert payload["status"] == "unhealthy"
        assert payload["database"] == "disconnected"
        assert payload["redis"] == "connected"
