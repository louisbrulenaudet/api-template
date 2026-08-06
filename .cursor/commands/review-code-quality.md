---
description: Code-quality review of app/ + tests/ - contract naming, type safety, Pydantic v2 usage, CoreError patterns, async correctness, testability. Outputs a plan only.
argument-hint: [paths, a subsystem, or "all"]
---

# Review code quality

Review the things a linter cannot see: contract naming, type safety, error patterns, async correctness, testability. Reply with a **plan only**: no edits, no implementation unless asked.

## Scope

Default to **the change under review**: `git diff`, `git diff --cached`, and untracked files. `$ARGUMENTS` overrides it. On `all`, say what you read and what you sampled.

## Authority

`.cursor/rules/` is authoritative; reading a file loads its rules, so **cite them and do not restate them**. Style and naming are `quality/python-style`; DTO and enum contracts are `contracts/pydantic-dtos`; errors are `backend/exceptions`; the layering split is `backend/services`; tests are `quality/testing`; Ruff and ty config decisions are `quality/lint-and-types`. Deeper framework patterns are the `fastapi` and `pydantic-best-practices` skills.

## Rank by enforcement gap

**Ruff and ty already run on every edit** via the `afterFileEdit` hook, and again in `make ci-check` and CI. So:

- **Do not report** formatting, line length, quote style, import grouping, unused imports, missing annotations that `ANN` covers, or PEP 8 casing. A gate fails on those without you, and re-reporting them is noise.
- **Do report** what no gate can see. Rank `Nothing enforces this:` violations first (`grep -rn 'Nothing enforces this' .cursor/rules/`) - those fail *open*, so review is the only check.

## What to examine

- **Dropped coroutines.** An async call neither awaited nor returned. Fails silently at runtime, invisible to lint. The highest-value thing in this file.
- **Suppressions that clear an error rather than explain one.** A `# noqa`, a widened `Any`, or a `# ty: ignore[...]` appearing in the same diff as the failure it silences is Critical. A bare `# ty: ignore` and a mypy-style `# type: ignore` are both wrong here - only `# ty: ignore[rule-name]` suppresses anything.
- **Contract naming**, because these names carry meaning a linter reads as arbitrary: `{Name}Response` / `{Name}Request` in `dtos/`, `{Name}Error` subclassing `CoreError` in `exceptions/`, `UPPER_SNAKE_CASE` members on a `PascalCase` enum, settings fields matching the env var they read.
- **Error discipline.** A domain failure raising bare `Exception` or `HTTPException` where a `CoreError` subclass exists; a new error with no `ErrorCodes` member, or a duplicated one; anything that could put internals - traceback, SQL, filesystem path, upstream body - into the client envelope. `details` stays withheld on 5xx.
- **Blocking work on an async path.** A sync call in an `async def` stalls every concurrent request, not just its own. Also flag a `def` handler that only builds a DTO: it pays a threadpool hop for nothing.
- **Validator cost and shape.** Heavy work inside a validator; `mode="before"` without the explicit `@classmethod` Ruff needs; parallel `TypedDict` / dataclass mirrors of a shape that already has one owner.
- **Duplication that will diverge.** A wire shape or an error code defined twice instead of imported once. Repetition that cannot diverge is cheaper than the wrong abstraction - say so rather than extracting on principle.
- **Testability.** Pure logic reachable without HTTP; dependencies injected rather than read from the environment inside a pure function; no module-scope state that persists across requests.
- **Test parity.** A DTO, enum or route contract that changed with no asserting test changed in the same diff.

## Output

**Critical** (dropped coroutine, suppression clearing an error, internals in the envelope, contract change with no test) → **Improvements** → **Optional** (prefix `Nit:`).

Each item: **what**, **where** (`file:line`), **why**, and the **rule it violates**. If no rule governs it, it is not a finding. One line per clean sub-area; silence is a valid result.

## Constraints

Read-only. `make check` and `make type-check` are the non-mutating gates; `make format` and `make ci` rewrite files. Hand off rather than duplicate: `security-reviewer` for auth/secrets, `test-runner` to actually run pytest. Defer architecture, performance and security to their own commands.
