import contextvars
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

__all__ = [
    "RequestIDMiddleware",
    "get_request_id",
]

_REQUEST_ID_HEADER = "x-request-id"

_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="",
)


def get_request_id() -> str:
    """Return the current request's correlation ID (empty string outside a request)."""
    return _request_id_ctx.get()


class RequestIDMiddleware:
    """Pure-ASGI middleware that assigns an ``X-Request-ID`` correlation header.

    Reads an inbound ``X-Request-ID`` (e.g. set by an upstream proxy / load balancer) or generates a UUID4, exposes it via :func:`get_request_id` for structured logging, and echoes it on the response so clients can quote it when reporting problems.

    Implemented as pure ASGI rather than ``BaseHTTPMiddleware`` so the ``ContextVar`` propagates to downstream handlers and loggers - Starlette documents that ``BaseHTTPMiddleware`` prevents ``contextvars`` changes from propagating upwards.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Store the wrapped ASGI application."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Attach a correlation ID to the request context and response headers."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = Headers(scope=scope).get(_REQUEST_ID_HEADER) or uuid4().hex
        token = _request_id_ctx.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[_REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            _request_id_ctx.reset(token)
