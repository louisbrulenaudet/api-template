---
paths:
  - "app/api/**/*.py"
---

# FastAPI Routes

Handlers live under `app/api/`, mounted under `/api/v1`. Load the `fastapi` skill for current framework
patterns.

## Template surface

`GET /api/v1/ping` → `PingResponse` · `GET /api/v1/health` → `HealthResponse`. Both stay
**unauthenticated** - Docker/K8s probes call them, so adding auth breaks container health checks.

Protect a router with `APIRouter(dependencies=[Depends(require_api_key)])`
(`app/core/security.py`) - per-router, not per-handler.

## Validation at the boundary

- Validate **every** path, query and body input with Pydantic / FastAPI params - never a bare untyped value
  on an API input.
- Prefer `Annotated[..., Path()]`, `Annotated[..., Query()]`, `Annotated[..., Body()]` (or a dedicated
  request model) with constraints and descriptions.
- Declare return types and/or `response_model=` so OpenAPI stays accurate.

```python
# ❌ BAD - unvalidated query bag
async def list_items(limit: int = 10, q: str = ""): ...

# ✅ GOOD - constrained, documented params
async def list_items(
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    q: Annotated[str, Query(max_length=200)] = "",
) -> ItemListResponse: ...
```

## Handler shape

1. Validate inputs (framework + Pydantic).
2. Resolve dependencies (`Annotated[..., Depends(...)]`).
3. Call service logic - see [services.md](services.md) for what belongs there.
4. Return a DTO.

Prefer `async def` for I/O and never block the event loop: one synchronous call in an `async` handler stalls
every concurrent request, not just its own.

## Errors

Raise `CoreError` subclasses and let the global handler map the status code; see
[exceptions.md](exceptions.md) for the envelope and for what may appear in `details`.

RESTful paths: plural nouns, verbs expressed by HTTP method.
