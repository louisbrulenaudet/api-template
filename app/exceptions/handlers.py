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

    Sets the correlation header itself rather than leaving it to `RequestIDMiddleware`, which never
    sees the catch-all handler's response (backend/exceptions).
    """
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers={REQUEST_ID_HEADER: payload.request_id, **(headers or {})},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the application's global exception handlers on ``app``.

    All four are load-bearing: dropping any one lets a second error shape onto the wire
    (backend/exceptions).
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
            # 5xx only - a 4xx traceback is expected noise.
            exc_info=exc if is_server_error else None,
        )

        return _render(
            ErrorResponse(
                error=exc.__class__.__name__,
                message=exc.message,
                code=exc.code,
                # Withheld on 5xx and logged above instead (backend/exceptions).
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
        # `exc_info=exc`, not `logger.exception(...)`: a registered handler is not an `except`
        # block, so there is no ambient `sys.exc_info()` (and `.exception()` trips Ruff LOG004).
        # This traceback is logged twice, deliberately (backend/exceptions).
        logger.error(
            "Unhandled %s escaped the application",
            exc.__class__.__name__,
            exc_info=exc,
        )

        return _render(
            ErrorResponse(
                error="InternalServerError",
                # Generic on purpose - exception text may name internal paths or hosts.
                message="An internal server error occurred.",
                code=ErrorCodes.INTERNAL_ERROR,
                details=None,
                request_id=request_id_from(request),
            ),
            _SERVER_ERROR,
        )
