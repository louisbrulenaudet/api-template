from fastapi import APIRouter

from app.api.v1.endpoints import (
    base_router,
)

__all__ = [
    "API_V1_PREFIX",
    "PROBE_PATHS",
    "router",
]

# The mount point `app.main.create_app` uses, kept here so the probe paths cannot drift from it.
API_V1_PREFIX = "/api/v1"

# Exempted from host validation, HTTPS redirection and auth. Read backend/middleware before adding
# a path here - the exemption is only safe for static, input-free routes.
PROBE_PATHS: frozenset[str] = frozenset(
    {
        f"{API_V1_PREFIX}/health",
        f"{API_V1_PREFIX}/ping",
    },
)

router = APIRouter()

router.include_router(base_router)
