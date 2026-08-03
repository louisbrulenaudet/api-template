from fastapi import APIRouter

from app.api.v1.endpoints import (
    base_router,
)

__all__ = [
    "API_V1_PREFIX",
    "PROBE_PATHS",
    "router",
]

# The mount point `app.main.create_app` uses, kept here so the probe paths below cannot drift
# from it.
API_V1_PREFIX = "/api/v1"

# Fully-qualified paths of the unauthenticated liveness/readiness probes.
#
# `app.middlewares.probe_bypass` exempts exactly these from host validation and HTTPS
# redirection: a container or orchestrator probe reaches the app by IP (`127.0.0.1` for the
# Dockerfile HEALTHCHECK, the pod IP for a kubelet probe), so it sends a `Host` header that no
# production `ALLOWED_HOSTS` list can name - the same reason these two routes stay
# unauthenticated.
PROBE_PATHS: frozenset[str] = frozenset(
    {
        f"{API_V1_PREFIX}/health",
        f"{API_V1_PREFIX}/ping",
    },
)

router = APIRouter()

# Include all routers
router.include_router(base_router)
