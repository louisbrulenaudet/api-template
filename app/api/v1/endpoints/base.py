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
    # Uptime is `monotonic` so it cannot jump or go negative under NTP or a DST change; `timestamp`
    # stays wall-clock because that is what a client can correlate against.
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
    return HealthResponse(status="ok")
