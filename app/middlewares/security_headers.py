from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

__all__ = [
    "SecurityHeadersMiddleware",
]

# Starlette ships no security-headers middleware, so this is a deliberate local one.
# Values chosen to be safe for a JSON API: no framing, no MIME sniffing, no referrer leakage.
_BASE_HEADERS: tuple[tuple[str, str], ...] = (
    ("x-content-type-options", "nosniff"),
    ("referrer-policy", "no-referrer"),
    ("x-frame-options", "DENY"),
    ("cross-origin-opener-policy", "same-origin"),
)

# Two years, the floor browsers require for HSTS preload eligibility. Only sent when the
# deployment terminates TLS, since HSTS on a plain-HTTP origin is both ignored and misleading.
_HSTS_HEADER = ("strict-transport-security", "max-age=63072000; includeSubDomains")


class SecurityHeadersMiddleware:
    """Pure-ASGI middleware adding conservative security response headers.

    Pure ASGI rather than `BaseHTTPMiddleware`, matching `RequestIDMiddleware` and current Starlette guidance: it avoids the `contextvars` propagation limits of the base class and adds no per-request task overhead.
    """

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        """Store the wrapped app and precompute the header tuple.

        Args:
            app: The ASGI application to wrap.
            hsts: Whether to also send `Strict-Transport-Security`. Enable only behind TLS.
        """
        self.app = app
        self.headers = (*_BASE_HEADERS, _HSTS_HEADER) if hsts else _BASE_HEADERS

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Add the security headers to every HTTP response that lacks them."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in self.headers:
                    # `setdefault`, not assignment: a route that deliberately sets its own
                    # policy (e.g. a permissive CSP for the docs page) must win.
                    headers.setdefault(key, value)
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
