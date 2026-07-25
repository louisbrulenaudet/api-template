import time
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.config import Settings, get_settings
from app.dtos import HealthResponse, PingResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/ping",
    summary="Ping endpoint",
    description="Health check endpoint for readiness/liveness probes.",
    status_code=status.HTTP_200_OK,
)
async def ping(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PingResponse:
    """Health check endpoint for readiness/liveness probes.

    Declared ``async def`` (not sync ``def``): the body is trivial and non-blocking, so running it directly on the event loop avoids the threadpool hop FastAPI applies to sync path operations (see https://fastapi.tiangolo.com/async/).

    Args:
        settings: The application settings.

    Returns:
        PingResponse: A structured ping response payload.

    Example:
        >>> await ping(settings)
        PingResponse(status='ok', uptime=100, timestamp=1716806400)
    """
    # Uptime comes from `time.monotonic` (matching `Settings.service_start_time`) so it cannot
    # jump or go negative when the wall clock is adjusted by NTP or a DST change; `timestamp`
    # stays wall-clock because it is what a client can actually correlate against.
    uptime: int = int(time.monotonic() - settings.service_start_time)

    return PingResponse(
        status="ok",
        uptime=uptime,
        timestamp=int(time.time()),
    )


@router.get(
    "/health",
    summary="Health check endpoint",
    description="Lightweight healthcheck endpoint for Docker/K8s.",
    status_code=status.HTTP_200_OK,
)
async def health() -> HealthResponse:
    """Lightweight healthcheck endpoint for Docker/K8s.

    Declared ``async def`` (not sync ``def``): the body is trivial and non-blocking, so it runs directly on the event loop rather than in FastAPI's sync threadpool (see https://fastapi.tiangolo.com/async/).

    Returns:
        HealthResponse: A structured health status payload.

    Example:
        >>> await health()
        HealthResponse(status='ok')
    """
    return HealthResponse(status="ok")
