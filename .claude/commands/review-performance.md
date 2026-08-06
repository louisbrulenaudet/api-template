---
description: Performance review - hot-path complexity, blocking I/O in async paths, Pydantic validation cost, aiocache keys/TTL, httpx2 timeouts, middleware overhead. Outputs a plan only.
argument-hint: [scope: files, directory, or "all"]
---

# Review performance

Review request-path cost: blocking I/O, complexity, validation overhead, caching, outbound calls, middleware. Reply with a **plan only**: no edits, no implementation unless asked.

## Scope

Default to **the change under review**: `git diff`, `git diff --cached`, and untracked files. `$ARGUMENTS` overrides it. On `all`, say what you read and what you sampled.

**Reason about the request path, not the whole tree.** A performance finding needs a caller: trace from a route handler outward through what it awaits. Code no request reaches is not a performance finding, however inefficient - say that rather than reporting it.

## Authority

`.cursor/rules/` is authoritative; reading a file loads its rules, so **cite them and do not restate them**. Handler shape is `backend/fastapi-routes`; the service boundary is `backend/services`; the middleware stack and lifespan resources are `backend/middleware`; the shared outbound client is `backend/middleware` too; DTO and validator cost is `contracts/pydantic-dtos`. Framework-level patterns are the `fastapi` and `pydantic-best-practices` skills.

## Rank by evidence, not suspicion

This is a reasoning review with no profiler, so **a claim you cannot ground is worse than silence**. For every finding, state the mechanism and the trigger: which request, what input size, and why the cost grows. "This could be slow" is not a finding.

Rank in this order:

1. **Correctness-shaped performance bugs** - a blocking call on an async path, a missing timeout, a per-request client. These are unbounded, not merely slow, and they degrade every concurrent request rather than one.
2. **Cost that grows with input** on a path a request reaches.
3. **Constant-factor tuning.** Usually `Nit:` territory. An unmeasured micro-optimisation traded against readability is a bad trade - say so.

## What to examine

- **Blocking I/O inside `async def`.** `time.sleep`, sync file reads, a sync HTTP or DB call. One of these stalls the whole event loop, so it is the highest-severity thing here. Conversely a plain `def` handler that only builds a DTO pays a threadpool hop for nothing.
- **Outbound HTTP.** Requests go through the shared lifespan-scoped client injected with `Depends(get_http_client)` - never a client constructed per request, which throws away connection reuse and HTTP/2 and leaks sockets under load. Every outbound call needs a timeout: without one a slow upstream converts into unbounded latency here.
- **Retry behaviour.** Retries multiply load on an already-failing dependency. Check that backoff is jittered, that a non-retryable error is not being retried, and that the retry budget cannot stack with a caller's own.
- **Complexity on a reached path.** Nested scans over request-sized input; a linear scan where a dict or set lookup fits; sorting inside a handler that did not need order; unbounded list endpoints with no pagination or limit.
- **Validation cost.** Heavy work in a validator runs on every request. Watch for CPU-bound work or, worse, an outbound call inside one. `wrap` validators are the most expensive form - avoid them on hot paths. Prefer `model_validate_json` over parsing then validating, and instantiate a `TypeAdapter` once rather than per call.
- **Cache keys and TTL.** A key missing a parameter that changes the result serves the wrong response - a correctness bug wearing a performance costume, so rank it as Critical. TTL is the only eviction this backend has: no TTL means unbounded growth. `maxsize` is not accepted in the alias config and raises lazily inside a route.
- **Long-lived state.** Module-level containers that only grow; per-request data captured in something that outlives the request; an unbounded `lru_cache` on a user-keyed or async helper (that decorator belongs on `get_settings` alone - use the async cache for anything keyed by a caller).
- **Middleware overhead.** Every middleware runs on every request, so ordering and thresholds matter: a compression threshold below typical payload size spends CPU to save nothing. Pure-ASGI middleware is cheaper than `BaseHTTPMiddleware`, and some of this stack is pure ASGI deliberately - do not "simplify" one into the other.

## Output

**Critical** (blocking call on an async path, missing timeout, per-request client, wrong or unbounded cache) → **Improvements** → **Optional** (prefix `Nit:`).

Each item: **what**, **where** (`file:line`), **why it costs** - stating the trigger and how the cost scales - and any **trade-off** (TTL against freshness, retries against load). If no rule governs it and you cannot ground the mechanism, it is not a finding. One line per clean sub-area; silence is a valid result.

## Constraints

Read-only and reasoning-only: no benchmarks, no servers, no load generators. `make check` and `make type-check` are non-mutating; `make format` and `make ci` rewrite files. Defer architecture, code quality and security to their own commands.
