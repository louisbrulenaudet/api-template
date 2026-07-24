import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions.core_exception import CoreError
from app.middlewares.request_id import get_request_id

__all__ = [
    "register_exception_handlers",
]

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register the application's global exception handlers on ``app``.

    Centralizes the mapping from domain exceptions to structured JSON responses so the :func:`app.main.create_app` factory stays thin and the handlers live next to the ``CoreError`` hierarchy they serve.

    Args:
        app: The FastAPI application to register handlers on.
    """

    @app.exception_handler(CoreError)
    async def _handle_core_error(_: Request, exc: CoreError) -> JSONResponse:
        """Convert a `CoreError` into a structured JSON response tagged with the request's correlation ID (X-Request-ID) for log/support correlation."""
        request_id = get_request_id()

        logger.error(
            "CoreError: %s [Code: %s] [RequestID: %s] Details: %s",
            exc.message,
            exc.code,
            request_id,
            exc.details,
        )

        payload: dict[str, Any] = {
            "error": exc.__class__.__name__,
            "message": exc.message,
            "code": exc.code,
            "details": exc.details or {},
            "request_id": request_id,
        }

        return JSONResponse(
            status_code=exc.http_status_code,
            content=payload,
        )
