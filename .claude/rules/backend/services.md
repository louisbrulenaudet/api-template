---
paths:
  - "app/services/**/*.py"
  - "app/api/**/*.py"
---

# Service Layer

Business logic lives in `app/services/`, not in route handlers and not in `app/core/` (which is cross-cutting infrastructure only: settings, shared HTTP client). Handlers stay thin and delegate here.

## When to add a service

Add an `app/services/<capability>.py` function when a handler would otherwise hold any of:

- a decision / branching beyond input validation,
- a write or other side effect,
- orchestration of more than one dependency or I/O call,
- logic worth unit-testing without HTTP, or reused by more than one entrypoint.

Keep the handler inline (no service) when it only validates input, resolves dependencies, and shapes one resolved value into a DTO - e.g. `app/api/v1/endpoints/base.py` (`ping` / `health`).

## Contract

- Transport-agnostic: take and return domain values or DTOs, never `Request` / `Response`.
- Raise `CoreError` subclasses for domain failures, never `HTTPException` - let the handler in `app/exceptions/handlers.py` map status codes.
- No anemic pass-through services: if a function only forwards its args with no logic, inline it until it earns its place.
- One focused module per capability; import specific callables (`from app.services.<capability> import <callable>`).

## Shared vs local

Reusable wire shapes stay in `app/dtos/`, error codes in `app/enums/`, exceptions in `app/exceptions/`. Never duplicate a shared DTO or `ErrorCodes` member. See [pydantic-dtos.md](../contracts/pydantic-dtos.md) and [guardrails.md](../core/guardrails.md).
