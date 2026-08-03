import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.utils.decorators import async_retry, retry


class CustomError(Exception):
    pass


class NonRetryError(Exception):
    pass


def test_retry_success():
    @retry()
    def func():
        return 42

    assert func() == 42


def test_retry_retries_then_success(monkeypatch):
    calls = {"count": 0}

    @retry(max_retries=3)
    def func():
        calls["count"] += 1
        if calls["count"] < 2:
            raise CustomError()
        return "ok"

    assert func() == "ok"
    assert calls["count"] == 2


def test_retry_max_retries_raises():
    @retry(max_retries=2)
    def func():
        raise CustomError()

    with pytest.raises(CustomError):
        func()


def test_retry_sleep(monkeypatch):
    called = {"sleep": 0}

    def fake_sleep(t):
        called["sleep"] += 1

    monkeypatch.setattr("app.utils.decorators.sleep", fake_sleep)
    calls = {"count": 0}

    @retry(max_retries=3, sleep_time=0.1)
    def func():
        calls["count"] += 1
        raise CustomError()

    with pytest.raises(CustomError):
        func()
    assert called["sleep"] == 2


def test_retry_raises_on_exception_false():
    @retry(max_retries=2, raises_on_exception=False)
    def func():
        raise CustomError()

    assert func() is None


def test_retry_non_retry_exceptions():
    @retry(max_retries=3, non_retry_exceptions=(NonRetryError,))
    def func():
        raise NonRetryError()

    with pytest.raises(NonRetryError):
        func()


@pytest.mark.asyncio
async def test_async_retry_success():
    @async_retry()
    async def func():
        return 99

    assert await func() == 99


@pytest.mark.asyncio
async def test_async_retry_retries_then_success():
    calls = {"count": 0}

    @async_retry(max_retries=3)
    async def func():
        calls["count"] += 1
        if calls["count"] < 2:
            raise CustomError()
        return "ok"

    assert await func() == "ok"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_async_retry_max_retries_raises():
    @async_retry(max_retries=2)
    async def func():
        raise CustomError()

    with pytest.raises(CustomError):
        await func()


@pytest.mark.asyncio
async def test_async_retry_sleep(monkeypatch):
    called = {"sleep": 0}

    async def fake_asyncio_sleep(t):
        called["sleep"] += 1

    monkeypatch.setattr("asyncio.sleep", fake_asyncio_sleep)
    calls = {"count": 0}

    @async_retry(max_retries=3, sleep_time=0.1)
    async def func():
        calls["count"] += 1
        raise CustomError()

    with pytest.raises(CustomError):
        await func()
    assert called["sleep"] == 2


@pytest.mark.asyncio
async def test_async_retry_raises_on_exception_false():
    @async_retry(max_retries=2, raises_on_exception=False)
    async def func():
        raise CustomError()

    assert await func() is None


@pytest.mark.asyncio
async def test_async_retry_non_retry_exceptions():
    @async_retry(max_retries=3, non_retry_exceptions=(NonRetryError,))
    async def func():
        raise NonRetryError()

    with pytest.raises(NonRetryError):
        await func()


@pytest.mark.asyncio
async def test_retry_guard_raises_when_event_loop_running(monkeypatch):
    called = {"sleep": 0}

    def fake_sleep(_: float) -> None:
        called["sleep"] += 1

    monkeypatch.setattr("app.utils.decorators.sleep", fake_sleep)

    @retry(max_retries=3, sleep_time=0.1)
    def func():
        raise CustomError()

    with pytest.raises(RuntimeError, match="Use async_retry\\(\\) instead"):
        func()

    assert called["sleep"] == 0


def test_retry_preserves_function_metadata():
    """`functools.wraps` must survive, or FastAPI cannot introspect a decorated handler."""

    @retry()
    def original_name() -> str:
        """Original docstring."""
        return "ok"

    assert original_name.__name__ == "original_name"
    assert original_name.__doc__ == "Original docstring."


def test_async_retry_preserves_function_metadata():
    @async_retry()
    async def original_async_name() -> str:
        """Original async docstring."""
        return "ok"

    assert original_async_name.__name__ == "original_async_name"
    assert original_async_name.__doc__ == "Original async docstring."


def test_decorated_route_can_be_registered_on_fastapi():
    """Regression: without `functools.wraps` the wrapper exposed `(*args: P.args, ...)`.

    FastAPI then tried to build a response field from `P.args` and raised `FastAPIError: Invalid args for response field!` at import time, so retry/async_retry could never be applied to a path operation.
    """
    app = FastAPI()

    @app.get("/decorated")
    @async_retry(max_retries=2)
    async def decorated() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        assert client.get("/decorated").json() == {"ok": True}


def test_non_retry_exception_stops_retrying_when_not_raising():
    """`raises_on_exception=False` must still honour `non_retry_exceptions`.

    Previously `_should_raise` short-circuited on `raises_on_exception=False` and never consulted `non_retry_exceptions`, so an error explicitly marked as not worth retrying was retried anyway.
    """
    calls = {"count": 0}

    @retry(max_retries=5, raises_on_exception=False, non_retry_exceptions=(NonRetryError,))
    def func():
        calls["count"] += 1
        raise NonRetryError()

    assert func() is None
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_async_non_retry_exception_stops_retrying_when_not_raising():
    calls = {"count": 0}

    @async_retry(max_retries=5, raises_on_exception=False, non_retry_exceptions=(NonRetryError,))
    async def func():
        calls["count"] += 1
        raise NonRetryError()

    assert await func() is None
    assert calls["count"] == 1


def test_retry_with_zero_attempts_returns_none():
    """`max_retries=0` never runs the body, so the post-loop `return None` is the only exit."""
    calls = {"count": 0}

    @retry(max_retries=0)
    def func():
        calls["count"] += 1
        return "unreachable"

    assert func() is None
    assert calls["count"] == 0


@pytest.mark.asyncio
async def test_async_retry_with_zero_attempts_returns_none():
    calls = {"count": 0}

    @async_retry(max_retries=0)
    async def func():
        calls["count"] += 1
        return "unreachable"

    assert await func() is None
    assert calls["count"] == 0
