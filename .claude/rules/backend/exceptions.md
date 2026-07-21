---
paths:
  - "app/exceptions/**"
  - "app/enums/**"
---

# Exceptions and Error Codes

All domain errors subclass `CoreError` and use a symbolic code from `ErrorCodes` (`app/enums/error_codes.py`).

## Adding an error

1. Add a member to `ErrorCodes`.
2. Create a focused exception module under `app/exceptions/` that calls `super().__init__(message, code, details=...)`.
3. If a non-default HTTP status is required, set it on the class (e.g. `http_status_code = 404`) so `app/main.py`'s handler can read it - or extend the handler mapping intentionally.
4. Re-export from package `__init__.py` when public.

## Client-facing payloads

- `to_dict()` / handler JSON: `error`, `message`, `code`, `details`.
- `details` must be JSON-safe and free of secrets, tokens, and filesystem internals.

## Discipline

Never raise bare `Exception` / `HTTPException` for domain failures when a `CoreError` subclass is appropriate. See [guardrails.md](../core/guardrails.md).
