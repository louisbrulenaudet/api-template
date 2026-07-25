import logging
from collections.abc import Mapping
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.dtos.error_response import ErrorResponse
from app.enums.error_codes import ErrorCodes
from app.exceptions.core_exception import CoreError
from app.middlewares.request_id import REQUEST_ID_HEADER, request_id_from

__all__ = [
    "register_exception_handlers",
]

logger = logging.getLogger(__name__)

_SERVER_ERROR = HTTPStatus.INTERNAL_SERVER_ERROR


def _render(
    payload: ErrorResponse,
    status_code: int,
    # `Mapping`, not `dict`: `StarletteHTTPException.headers` is a read-only mapping.
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Serialize an `ErrorResponse` through Pydantic so the DTO stays the only wire shape.

    The correlation header is set here rather than left to `RequestIDMiddleware`, because the catch-all handler's response is emitted by ServerErrorMiddleware - outside that middleware - and would otherwise ship without an `X-Request-ID` for the client to quote.
    """
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers={REQUEST_ID_HEADER: payload.request_id, **(headers or {})},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the application's global exception handlers on ``app``.

    Every handler answers with the same `ErrorResponse` envelope, tagged with the request's correlation ID. Without the validation / HTTP / catch-all handlers, FastAPI's defaults would return two other shapes (`{"detail": ...}` and a plain-text `Internal Server Error`), leaving clients to parse three different error formats from one API.

    Args:
        app: The FastAPI application to register handlers on.
    """

    @app.exception_handler(CoreError)
    async def _handle_core_error(request: Request, exc: CoreError) -> JSONResponse:
        """Convert a `CoreError` into the standard envelope."""
        request_id = request_id_from(request)
        is_server_error = exc.http_status_code >= _SERVER_ERROR

        logger.log(
            logging.ERROR if is_server_error else logging.WARNING,
            "%s: %s [code=%s] details=%s",
            exc.__class__.__name__,
            exc.message,
            exc.code,
            exc.details,
            # Server-side faults need the traceback; client faults (4xx) are expected and
            # would only add noise.
            exc_info=exc if is_server_error else None,
        )

        return _render(
            ErrorResponse(
                error=exc.__class__.__name__,
                message=exc.message,
                code=exc.code,
                # A 5xx `details` describes an internal failure (an upstream exception string,
                # a config problem) and is logged above rather than returned to the caller.
                details=None if is_server_error else exc.details,
                request_id=request_id,
            ),
            exc.http_status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Return Pydantic's per-field errors inside the standard envelope."""
        # `jsonable_encoder` is required: `exc.errors()` can carry non-serializable values in
        # `ctx` (the original `ValueError`) and raw `bytes` inputs.
        return _render(
            ErrorResponse(
                error="RequestValidationError",
                message="Request validation failed.",
                code=ErrorCodes.VALIDATION_ERROR,
                details=jsonable_encoder(exc.errors()),
                request_id=request_id_from(request),
            ),
            HTTPStatus.UNPROCESSABLE_CONTENT,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        """Re-shape framework `HTTPException`s (404s, 405s, `raise HTTPException(...)`)."""
        # Registered against the Starlette base class so `fastapi.HTTPException` - a subclass -
        # is covered by the same handler.
        return _render(
            ErrorResponse(
                error="HTTPException",
                message=exc.detail or HTTPStatus(exc.status_code).phrase,
                code=ErrorCodes.HTTP_ERROR,
                details=None,
                request_id=request_id_from(request),
            ),
            exc.status_code,
            # Preserve headers the framework attached, e.g. `WWW-Authenticate` on a 401 or
            # `Allow` on a 405; dropping them would break the HTTP contract.
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """Last resort: log the traceback and return an opaque 500."""
        # `exc_info=exc` rather than `logger.exception(...)`: this is a registered handler, not
        # an `except` block, so it must not depend on an ambient `sys.exc_info()` to find the
        # traceback (and `.exception()` here trips Ruff LOG004 for that reason).
        #
        # Note: Starlette's ServerErrorMiddleware re-raises after calling this handler, so the
        # server logger records the traceback a second time. That duplication is the price of
        # having one copy carry the correlation ID - which is the copy an operator can actually
        # tie back to a client report.
        logger.error(
            "Unhandled %s escaped the application",
            exc.__class__.__name__,
            exc_info=exc,
        )

        return _render(
            ErrorResponse(
                error="InternalServerError",
                # Deliberately generic: the exception text may name internal paths, hosts or
                # query fragments. The traceback goes to the log, not to the client.
                message="An internal server error occurred.",
                code=ErrorCodes.INTERNAL_ERROR,
                details=None,
                request_id=request_id_from(request),
            ),
            _SERVER_ERROR,
        )
