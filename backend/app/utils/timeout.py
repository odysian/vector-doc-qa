import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, TypeVar

T = TypeVar("T")

# Module-level singleton executor — avoids creating a new pool per call.
# Uses "spawn" start method implicitly (default on Linux 3.12+ with asyncio).
_executor: ProcessPoolExecutor | None = None


def _get_executor() -> ProcessPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ProcessPoolExecutor(max_workers=2)
    return _executor


async def run_with_timeout_async(
    func: Callable[..., T], args: tuple, timeout_seconds: int
) -> T:
    """
    Run a CPU-bound function in a process pool without blocking the event loop.

    Args:
        func: Function to run (must be picklable)
        args: Tuple of arguments to pass to func
        timeout_seconds: Max seconds to wait

    Returns:
        Result of the function

    Raises:
        TimeoutError: If func exceeds timeout
        Exception: Any exception raised by func
    """
    loop = asyncio.get_running_loop()
    executor = _get_executor()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(executor, func, *args),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        raise TimeoutError(f"Operation timed out after {timeout_seconds} seconds")
