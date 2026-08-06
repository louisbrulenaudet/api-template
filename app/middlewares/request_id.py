import contextvars
import re
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

__all__ = [
    "REQUEST_ID_HEADER",
    "RequestIDMiddleware",
    "get_request_id",
    "request_id_from",
]

REQUEST_ID_HEADER = "X-Request-ID"

# Published to the scope as well as the ContextVar, because the ContextVar is already reset by the
# time the catch-all handler runs (backend/exceptions).
_SCOPE_KEY = "request_id"

# An inbound ID is attacker-controlled and reaches log lines and a response header, so the charset is
# a log-forging guard (backend/middleware). The length cap also stops a megabyte-long "ID"; a
# non-matching value degrades to a fresh UUID rather than failing the request.
_MAX_LENGTH = 128
_SAFE_REQUEST_ID = re.compile(r"\A[A-Za-z0-9._:@/+=-]+\Z")

_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="",
)


def get_request_id() -> str:
    """Return the current request's correlation ID (empty string outside a request)."""
    return _request_id_ctx.get()


def request_id_from(request: Request) -> str:
    """Return the correlation ID for ``request``, even outside the middleware's context.

    Reads the scope copy first and falls back to the `ContextVar`. The `isinstance` re-checks are the
    `app.state` boundary discipline, not redundancy (backend/middleware).
    """
    state = request.scope.get("state")
    if isinstance(state, dict):
        value = state.get(_SCOPE_KEY)
        if isinstance(value, str):
            return value
    return get_request_id()


def _coerce_request_id(inbound: str | None) -> str:
    """Return a safe correlation ID, generating one when the inbound value is unusable."""
    if inbound and len(inbound) <= _MAX_LENGTH and _SAFE_REQUEST_ID.match(inbound):
        return inbound
    return uuid4().hex


class RequestIDMiddleware:
    """Pure-ASGI middleware that assigns an ``X-Request-ID`` correlation header.

    Reads an inbound ``X-Request-ID`` or generates a UUID4, exposes it via :func:`get_request_id`, and
    echoes it on the response. Pure ASGI rather than ``BaseHTTPMiddleware`` so the ``ContextVar``
    propagates downstream (backend/middleware).
    """

    def __init__(self, app: ASGIApp) -> None:
        """Store the wrapped ASGI application."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Attach a correlation ID to the request context and response headers."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _coerce_request_id(Headers(scope=scope).get(REQUEST_ID_HEADER))
        token = _request_id_ctx.set(request_id)
        scope.setdefault("state", {})[_SCOPE_KEY] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            _request_id_ctx.reset(token)
