from collections.abc import Iterable, Sequence

from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

__all__ = [
    "ProbeBypassMiddleware",
]


class ProbeBypassMiddleware:
    """Host validation and HTTPS redirection, bypassed for the unauthenticated probe paths.

    A liveness probe cannot satisfy either guard. The Dockerfile `HEALTHCHECK` requests `http://127.0.0.1:8001/api/v1/health` and a kubelet probe uses the pod IP, so both send a `Host` header that a production `ALLOWED_HOSTS` list - which must name explicit hostnames, enforced at startup - can never contain. `TrustedHostMiddleware` answers `400 Invalid host header` before routing and the container is permanently unhealthy. `HTTPSRedirectMiddleware` is the same story over plain HTTP: the probe gets a 307 to a URL it cannot reach.

    Both guards therefore have to be skipped, not just the first. Skipping only host validation would leave a probe request falling through to `HTTPSRedirectMiddleware`, which builds `Location` from the very `Host` header that was just left unchecked - an open redirect on `/api/v1/health`, which is exactly what the "TrustedHost before HTTPSRedirect" ordering exists to prevent.

    The exemption is safe because of what these two routes are: they take no input, read no request state and return a static payload, so a forged `Host` has nothing to influence. Anything reachable at any other path keeps both guards. The same reasoning keeps them unauthenticated - see `.claude/rules/backend/fastapi-routes.md`.

    Composed internally rather than registered as two more `app.add_middleware` calls, because the bypass has to wrap the pair as a unit while preserving their relative order.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        allowed_hosts: Sequence[str],
        force_https: bool,
        probe_paths: Iterable[str],
    ) -> None:
        """Build the guarded branch and record the paths that skip it.

        Args:
            app: The ASGI application to wrap.
            allowed_hosts: Host patterns `TrustedHostMiddleware` accepts.
            force_https: Whether to redirect plain-HTTP requests to HTTPS.
            probe_paths: Request paths served without either guard.
        """
        self.app = app
        self.probe_paths = frozenset(probe_paths)

        # Innermost first: TrustedHost must see the request before HTTPSRedirect reflects the
        # `Host` header into a `Location`.
        guarded: ASGIApp = HTTPSRedirectMiddleware(app) if force_https else app
        self.guarded = TrustedHostMiddleware(guarded, allowed_hosts=list(allowed_hosts))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Route probe requests past the guards and everything else through them."""
        # `scope["path"]` is what the ASGI server received, i.e. already stripped of any prefix
        # a proxy mounts the app under, so this matches whether the probe is local or proxied.
        if scope["type"] == "http" and scope["path"] in self.probe_paths:
            await self.app(scope, receive, send)
            return

        await self.guarded(scope, receive, send)
