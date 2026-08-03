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

# The ID is published twice, deliberately:
#   * a ContextVar, so any logger can pick it up with no plumbing (see `RequestIDFilter`);
#   * the ASGI scope, so it survives past this middleware's `finally: reset(token)`.
# The second one matters for the catch-all `Exception` handler: that runs inside Starlette's
# ServerErrorMiddleware, which sits OUTSIDE all user middleware, so by then the ContextVar has
# already been reset and would read as "". `request_id_from()` is the accessor that works in
# both places.
_SCOPE_KEY = "request_id"

# An inbound correlation ID is attacker-controlled input that ends up in log lines and in a
# response header. Constraining it to a conservative token charset (and a sane length) is what
# stops a caller from forging log records with embedded newlines, smuggling ANSI escapes into
# an operator's terminal, or bloating every log line with a megabyte-long "ID". Anything that
# does not match is replaced by a fresh UUID rather than rejected, so a badly-behaved proxy
# degrades to "no correlation" instead of failing the request.
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

    Reads the scope copy first and falls back to the `ContextVar`. `request.state` is an untyped `Any` bag, so the value is re-checked with `isinstance` rather than trusted from an annotation - the same boundary discipline as `app.core.http_client.get_http_client`.

    Args:
        request: The request whose correlation ID is wanted.

    Returns:
        str: The correlation ID, or an empty string if none was assigned.
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
