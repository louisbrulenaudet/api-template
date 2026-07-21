---
paths:
  - "app/api/**/*.py"
---

# FastAPI Routes

API handlers live under `app/api/`. Load the `fastapi` skill for current FastAPI patterns.

## Validation at the boundary

- Validate **every** path, query, and body input with Pydantic / FastAPI params - not bare untyped values for API inputs.
- Prefer `Annotated[..., Path()]`, `Annotated[..., Query()]`, `Annotated[..., Body()]` (or a dedicated request model) with constraints and descriptions.
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

## Thin handlers

1. Validate inputs (framework + Pydantic).
2. Resolve dependencies (`Annotated[..., Depends(...)]`).
3. Call core/service logic.
4. Return a DTO.

No business logic inline in route modules. Prefer `async def` for I/O; never block the event loop.

## Errors and status codes

- Raise `CoreError` subclasses for domain failures; let the global handler map status codes.
- Typical HTTP mapping: 400 validation/domain, 401/403 auth, 404 not found, 500 unexpected.
- Never put secrets or stack traces in client-facing `details`.

## Organization

- Keep routers modular; mount under `/api/v1` via `app/api/v1/router.py`.
- RESTful paths: plural nouns; verbs via HTTP method.

## Before finishing

Run `make check` and the affected tests (`uv run pytest tests/...`).
