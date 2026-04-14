import time
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.dtos import HealthResponse, PingResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/ping",
    summary="Ping endpoint",
    description="Health check endpoint for readiness/liveness probes.",
)
def ping(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PingResponse:
    """Health check endpoint for readiness/liveness probes.

    Args:
        settings: The application settings.

    Returns:
        PingResponse: A structured ping response payload.

    Example:
        >>> await ping()
        {'status': 'ok', 'uptime': 100, 'timestamp': 1716806400}
    """
    now: int = int(time.time())
    uptime: int = now - int(settings.service_start_time)

    return PingResponse(
        status="ok",
        uptime=uptime,
        timestamp=now,
    )


@router.get(
    "/health",
    summary="Health check endpoint",
    description="Lightweight healthcheck endpoint for Docker/K8s.",
)
def health() -> HealthResponse:
    """Lightweight healthcheck endpoint for Docker/K8s.

    Returns:
        HealthResponse: A structured health status payload.

    Example:
        >>> await health()
        {'status': 'ok'}
    """
    return HealthResponse(status="ok")
