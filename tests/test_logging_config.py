import json
import logging
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging_config import JsonFormatter, RequestIDFilter, configure_logging
from app.main import create_app
from tests.conftest import build_settings


def test_configure_logging_installs_a_root_handler() -> None:
    configure_logging(build_settings(log_level="INFO"))

    root = logging.getLogger()

    assert root.handlers, "root logger must have a handler, not fall back to lastResort"
    assert root.level == logging.INFO


def test_configure_logging_honours_the_level() -> None:
    configure_logging(build_settings(log_level="WARNING"))

    assert logging.getLogger().level == logging.WARNING

    # Restore a sane level for the rest of the suite.
    configure_logging(build_settings(log_level="INFO"))


def test_request_id_filter_adds_the_attribute() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "msg", None, None)

    assert RequestIDFilter().filter(record) is True
    # Empty outside a request, but present - so a formatter referencing it never blows up.
    assert record.__dict__["request_id"] == ""


def test_request_id_filter_picks_up_the_active_request(app: FastAPI) -> None:
    """Inside a request the filter must see the middleware's ContextVar value."""
    seen: list[str] = []

    @app.get("/log-a-line")
    async def log_a_line() -> dict[str, bool]:
        record = logging.LogRecord("t", logging.INFO, __file__, 1, "msg", None, None)
        RequestIDFilter().filter(record)
        seen.append(record.__dict__["request_id"])
        return {"ok": True}

    with TestClient(app) as client:
        client.get("/log-a-line", headers={"X-Request-ID": "trace-log-1"})

    assert seen == ["trace-log-1"]


def test_json_formatter_emits_parseable_records() -> None:
    record = logging.LogRecord("svc", logging.WARNING, __file__, 10, "hello %s", ("world",), None)
    RequestIDFilter().filter(record)

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "WARNING"
    assert payload["logger"] == "svc"
    assert payload["message"] == "hello world"
    assert "timestamp" in payload
    assert "request_id" in payload


def test_json_formatter_includes_exception_text() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            "svc", logging.ERROR, __file__, 10, "failed", None, sys.exc_info()
        )

    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: boom" in payload["exception"]


def test_json_logging_is_selectable() -> None:
    app = create_app(build_settings(log_json=True))
    handler = logging.getLogger().handlers[0]

    assert isinstance(handler.formatter, JsonFormatter)
    assert app is not None

    # Reset to the plain formatter so later tests read normal output.
    configure_logging(build_settings(log_json=False))


def test_json_formatter_includes_stack_info() -> None:
    """A record carrying `stack_info` must surface it, not drop it silently."""
    record = logging.LogRecord(
        "svc", logging.INFO, __file__, 1, "msg", None, None, None, "fake stack frame"
    )
    RequestIDFilter().filter(record)

    payload = json.loads(JsonFormatter().format(record))

    assert "fake stack frame" in payload["stack"]
