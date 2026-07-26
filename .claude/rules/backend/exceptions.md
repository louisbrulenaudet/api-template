---
paths:
  - "app/exceptions/**"
  - "app/enums/**"
---

# Exceptions and Error Codes

All domain errors subclass `CoreError` and carry a symbolic code from `ErrorCodes`
(`app/enums/error_codes.py`). Never raise a bare `Exception` or `HTTPException` for a domain failure when a
`CoreError` subclass would do - this rule is the canonical statement of that, and other rules point here.

## Adding an error

1. Add a member to `ErrorCodes`.
2. Create a focused exception module under `app/exceptions/` that calls
   `super().__init__(message, code, details=...)`.
3. For a non-default HTTP status, set `http_status_code` on the class so the `CoreError` handler reads it -
   or extend the handler mapping deliberately.
4. Re-export from the package `__init__.py` when public.

## Client-facing payloads

`app/exceptions/handlers.py` registers handlers for `CoreError`, `RequestValidationError`,
`StarletteHTTPException` and a catch-all `Exception`, so every failure leaves through the same envelope.

- **One owner:** `app/dtos/error_response.py::ErrorResponse`. `CoreError` has **no `to_dict()`** - that was
  a second serializer and it drifted (lost `request_id`, echoed 5xx details). Do not reintroduce one.
- **`details` is withheld on 5xx** and logged instead: server-side `details` describe an internal failure.
  4xx `details` are client-actionable and preserved.
- **`details` must be JSON-safe and free of secrets, tokens, and filesystem internals.** This is the
  canonical rule for everything that reaches a client - DTO error messages and log lines included.
- **The catch-all runs inside `ServerErrorMiddleware`, *outside* `RequestIDMiddleware`**, so correlation
  must come from `request_id_from(request)` (scope-backed), not `get_request_id()` - the ContextVar has
  already been reset by then.
