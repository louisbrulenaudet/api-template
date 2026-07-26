---
paths:
  - "app/dtos/**"
  - "app/enums/**"
---

# Pydantic Contracts

Pydantic v2 models are the sole wire-shape source of truth. Load the `pydantic-best-practices` skill for performance patterns.

## Ownership

- A shape has exactly one owner under `app/dtos/` or `app/enums/`.
- Define it once; import everywhere else. Never copy a DTO or enum member across modules.
- Prefer one focused module per public model when practical; re-export from package `__init__.py`.

## Authoring

- No business logic in DTO modules - shapes and validation only.
- Use `Field(...)` with clear descriptions for OpenAPI.
- Keep validation error messages client-safe, to the standard in
  [exceptions.md](../backend/exceptions.md).
- Prefer additive field changes. Breaking changes need a deliberate API version / migration and consumer updates in the same PR.

## Validators

Ruff's `pep8-naming` cannot tell a `mode="before"` model validator (takes `cls`) from a `mode="after"` one (takes `self`), so the config resolves only the unambiguous half:

- `@field_validator` is registered in `[tool.ruff.lint.pep8-naming] classmethod-decorators`, so it satisfies `N805` on its own. Stacking `@classmethod` under it is still the Pydantic-documented form and stays clean either way.
- `@model_validator(mode="before")` **must** carry an explicit `@classmethod` beneath it - Ruff then recognises it natively. Without it you get a spurious `N805`.
- `@model_validator(mode="after")` takes `self` and returns `Self`; no `@classmethod`.

`ANN401` fires on the `Any` input of a `mode="before"` validator. That `Any` is genuine, so suppress it narrowly on that argument rather than widening the rule.

## Inference

- Do not maintain parallel `TypedDict` / dataclass mirrors of the same wire shape.
- Route handlers return the DTO type (or declare `response_model=`) so FastAPI/OpenAPI stay aligned.

## Discipline

When a contract changes, update producers, consumers, and tests in the **same** change. See [guardrails.md](../core/guardrails.md).
