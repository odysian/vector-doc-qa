# tests/test_timeout.py
"""Tests for async timeout utility."""

import time

import pytest

from app.utils.timeout import run_with_timeout_async


def _add(a: int, b: int) -> int:
    return a + b


def _slow_func(seconds: float) -> str:
    time.sleep(seconds)
    return "done"


def _raise_value_error() -> None:
    raise ValueError("boom")


class TestRunWithTimeoutAsync:
    """Verify CPU-bound work runs off the event loop with timeout."""

    @pytest.mark.asyncio
    async def test_returns_result_on_success(self) -> None:
        result = await run_with_timeout_async(_add, (2, 3), timeout_seconds=5)
        assert result == 5

    @pytest.mark.asyncio
    async def test_raises_timeout_error_when_exceeded(self) -> None:
        with pytest.raises(TimeoutError, match="timed out after 1 seconds"):
            await run_with_timeout_async(
                _slow_func, (10.0,), timeout_seconds=1
            )

    @pytest.mark.asyncio
    async def test_propagates_function_exception(self) -> None:
        with pytest.raises(ValueError, match="boom"):
            await run_with_timeout_async(
                _raise_value_error, (), timeout_seconds=5
            )
