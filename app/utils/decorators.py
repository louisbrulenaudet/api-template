import asyncio
import secrets
from collections.abc import Awaitable, Callable
from functools import wraps
from time import sleep
from typing import ParamSpec, TypeVar

__all__ = [
    "async_retry",
    "retry",
]


P = ParamSpec("P")
R = TypeVar("R")
_SECURE_RANDOM = secrets.SystemRandom()


def _compute_retry_delay(sleep_time: int | float, attempt: int, max_delay: float = 30.0) -> float:
    """Compute an attempt-based backoff delay with full jitter (quality/python-style)."""
    base_delay = min(float(sleep_time) * (2**attempt), max_delay)
    return _SECURE_RANDOM.uniform(0, base_delay)


def _is_event_loop_running() -> bool:
    """Return True when called from within an active asyncio event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def _should_stop(
    exc: Exception,
    attempt: int,
    max_retries: int,
    non_retry_exceptions: tuple[type[Exception], ...],
) -> bool:
    """Return True when no further attempt should be made.

    Deliberately independent of `raises_on_exception` (quality/python-style).
    """
    if non_retry_exceptions and isinstance(exc, non_retry_exceptions):
        return True
    return attempt >= max_retries - 1


def retry(
    max_retries: int = 3,
    sleep_time: int | float = 0,
    raises_on_exception: bool = True,
    non_retry_exceptions: tuple[type[Exception], ...] = (),
) -> Callable[[Callable[P, R]], Callable[P, R | None]]:
    """Retry a sync function call on exception, with full-jitter backoff."""

    def decorator(func: Callable[P, R]) -> Callable[P, R | None]:
        # Required, not cosmetic - FastAPI rejects a decorated path operation without it
        # (quality/python-style).
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | None:
            if _is_event_loop_running():
                raise RuntimeError(
                    "retry() must not be used inside an async context. Use async_retry() instead."
                )
            for i in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    if _should_stop(e, i, max_retries, non_retry_exceptions):
                        if raises_on_exception:
                            raise
                        return None
                    if sleep_time:
                        sleep(_compute_retry_delay(sleep_time, i))
                else:
                    return result

            # Only reachable when max_retries < 1, i.e. the body never ran.
            return None

        return wrapper

    return decorator


def async_retry(
    max_retries: int = 3,
    sleep_time: int | float = 0,
    raises_on_exception: bool = True,
    non_retry_exceptions: tuple[type[Exception], ...] = (),
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R | None]]]:
    """Retry a coroutine function call on exception, with full-jitter backoff."""

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R | None]]:
        # Required, not cosmetic - see `retry` above (quality/python-style).
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | None:
            for i in range(max_retries):
                try:
                    result = await func(*args, **kwargs)
                except Exception as e:
                    if _should_stop(e, i, max_retries, non_retry_exceptions):
                        if raises_on_exception:
                            raise
                        return None
                    if sleep_time:
                        await asyncio.sleep(_compute_retry_delay(sleep_time, i))
                else:
                    return result

            # Only reachable when max_retries < 1, i.e. the body never ran.
            return None

        return wrapper

    return decorator
