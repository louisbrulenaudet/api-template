import json
import logging
import logging.config
from datetime import UTC, datetime
from typing import Any, override

from app.core.config import Settings
from app.middlewares.request_id import get_request_id

__all__ = [
    "RECORD_REQUEST_ID_KEY",
    "JsonFormatter",
    "RequestIDFilter",
    "configure_logging",
]

# The `LogRecord` attribute the filter injects and the formatters read.
RECORD_REQUEST_ID_KEY = "request_id"

# Named `logging_config` rather than `logging` so the module does not shadow the stdlib one
# (Ruff A005) for anything importing `app.core.*`.


class RequestIDFilter(logging.Filter):
    """Attach the current request's correlation ID to every log record.

    `RequestIDMiddleware` stores the ID in a `ContextVar`; reading it here means handlers and services get correlated logs for free, instead of each call site having to interpolate `get_request_id()` by hand.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Set `record.request_id` and always keep the record."""
        # Written through `__dict__` because that is how `logging` itself injects `extra=` fields:
        # `request_id` is not a declared `LogRecord` attribute, so assigning it directly is an
        # unchecked attribute write that ty rightly rejects.
        record.__dict__[RECORD_REQUEST_ID_KEY] = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    """Render one JSON object per record, for ingestion by a log collector."""

    @override
    def format(self, record: logging.LogRecord) -> str:
        """Serialize the record, including any exception and stack info."""
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            RECORD_REQUEST_ID_KEY: record.__dict__.get(RECORD_REQUEST_ID_KEY, ""),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    """Install the application-wide logging configuration.

    Without this, nothing ever calls `dictConfig`/`basicConfig`: app `INFO`/`DEBUG` records are discarded and `WARNING`+ escapes through `logging.lastResort` with no timestamp, logger name or correlation ID. Uvicorn's own loggers are re-pointed at the same handler so application and server output share one format and one stream.

    Args:
        settings: Supplies the level and whether to emit JSON.
    """
    formatter = "json" if settings.log_json else "plain"
    uvicorn_logger = {
        "handlers": ["default"],
        "level": settings.log_level,
        "propagate": False,
    }

    logging.config.dictConfig(
        {
            "version": 1,
            # Never disable loggers created at import time (module-level `getLogger(__name__)`).
            "disable_existing_loggers": False,
            "filters": {"request_id": {"()": RequestIDFilter}},
            "formatters": {
                # `%(request_id)s` resolves because every handler below carries the filter.
                "plain": {
                    "format": "%(asctime)s %(levelname)-8s %(name)s [%(request_id)s] %(message)s",
                },
                "json": {"()": JsonFormatter},
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": formatter,
                    "filters": ["request_id"],
                },
            },
            "root": {"handlers": ["default"], "level": settings.log_level},
            "loggers": {
                "uvicorn": uvicorn_logger,
                "uvicorn.error": uvicorn_logger,
                "uvicorn.access": uvicorn_logger,
            },
        }
    )
