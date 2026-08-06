---
paths:
  - "app/services/**/*.py"
  - "app/api/**/*.py"
  - "app/core/**"
---

# Service Layer

Business logic lives in `app/services/`, not in route handlers and not in `app/core/` - which is cross-cutting infrastructure only (settings, shared HTTP client). Handlers stay thin and delegate here. This is the canonical statement of that split; other rules point at it rather than restate it.

## When to add a service

Add an `app/services/<capability>.py` function when a handler would otherwise hold any of:

- a decision or branch beyond input validation,
- a write or other side effect,
- orchestration of more than one dependency or I/O call,
- logic worth unit-testing without HTTP, or reused by more than one entrypoint.

Keep the handler inline, with no service, when it only validates input, resolves dependencies, and shapes one resolved value into a DTO - as `app/api/v1/endpoints/base.py` does for `ping` / `health`.

## Contract

- **Transport-agnostic**: take and return domain values or DTOs, never `Request` / `Response`.
- **Raise `CoreError` subclasses, never `HTTPException`** - the handler maps status codes. See [exceptions.md](exceptions.md).
- **No anemic pass-throughs**: a function that only forwards its arguments with no logic should be inlined until it earns its place.
- One focused module per capability; import specific callables (`from app.services.<capability> import <callable>`).

Reusable wire shapes belong in `app/dtos/`, error codes in `app/enums/`, exceptions in `app/exceptions/` - defined once, per [guardrails.md](../core/guardrails.md).
