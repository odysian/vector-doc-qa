from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Callable, TypeVar

T = TypeVar("T")


def run_with_timeout(func: Callable[..., T], args: tuple, timeout_seconds: int) -> T:
    """
    Run a function with a timeout.

    Args:
        func: Function to run
        args: Tuple of arguments to pass to func
        timeout_seconds: Max seconds to wait

    Returns:
        Result of the function

    Raises:
        TimeoutError: If func exceeds timeout
        Exception: Any exception raised by func
    """
    with ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            future.cancel()
            raise TimeoutError(f"Operation timed out after {timeout_seconds} seconds")
        finally:
            executor.shutdown(wait=False)
