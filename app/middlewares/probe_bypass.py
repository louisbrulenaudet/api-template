from collections.abc import Iterable, Sequence

from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

__all__ = [
    "ProbeBypassMiddleware",
]


class ProbeBypassMiddleware:
    """Host validation and HTTPS redirection, bypassed for the unauthenticated probe paths.

    Both guards are skipped together, and the pair is composed here rather than registered
    separately, for reasons that are load-bearing rather than stylistic. Read
    `.claude/rules/backend/middleware.md` before adding a path to `probe_paths` or splitting these up.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        allowed_hosts: Sequence[str],
        force_https: bool,
        probe_paths: Iterable[str],
    ) -> None:
        """Build the guarded branch and record the paths that skip it."""
        self.app = app
        self.probe_paths = frozenset(probe_paths)

        # Innermost first: TrustedHost must see the request before HTTPSRedirect reflects the
        # `Host` header into a `Location`. Reversing these two is an open redirect.
        guarded: ASGIApp = HTTPSRedirectMiddleware(app) if force_https else app
        self.guarded = TrustedHostMiddleware(guarded, allowed_hosts=list(allowed_hosts))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Route probe requests past the guards and everything else through them."""
        # `scope["path"]` is already prefix-stripped, so this matches proxied probes too.
        if scope["type"] == "http" and scope["path"] in self.probe_paths:
            await self.app(scope, receive, send)
            return

        await self.guarded(scope, receive, send)
