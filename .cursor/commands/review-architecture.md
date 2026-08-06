---
description: Architecture review - layering, dependency direction, import cycles, coupling/cohesion, build parity. Outputs a plan only.
argument-hint: [paths, a subsystem, or "all"]
---

# Review architecture

Review layering, dependency direction, coupling and build-boundary parity. Reply with a **plan only**: no edits, no implementation unless asked.

## Scope

Default to **the change under review**, not the repo: `git diff`, `git diff --cached`, and untracked files. `$ARGUMENTS` overrides it (paths, a subsystem, or `all`). A whole-repo pass is only meaningful on a small tree - if you run one, say what you actually read and what you sampled, so nobody mistakes a sample for coverage.

For each changed file, widen to its **import neighbourhood**: what it imports, and what imports it. That is the unit an architecture finding lives in. Ignoring the rest is correct, not lazy.

## Authority

`.claude/rules/` is authoritative; this command is a procedure, not a second copy of the conventions. Reading a file loads its rules automatically, so **cite the rule and do not restate it**. The layering contract is `backend/services.md`; the app factory and middleware stack are `backend/middleware.md`; errors are `backend/exceptions.md`; build parity is `ops/dockerfile.md`, `ops/compose.md`, `ops/makefile.md`.

**Discover the structure; never trust a list of it.** A hardcoded module inventory in a review prompt is wrong the day someone adds a package:

```sh
git ls-files 'app/**/*.py' | sed 's|/[^/]*$||' | sort -u        # packages that exist now
grep -rn '^from app\.\|^import app\.' app/ | sed 's/:.*from /  <- /'  # the real import graph
```

## Rank by enforcement gap

1. **`Nothing enforces this:` violations first.** That marker in a rule means the invariant fails *open* - every gate stays green and review is the only thing standing in the way. `grep -rn 'Nothing enforces this' .claude/rules/` is the set.
2. Then structural problems no gate covers: cycles, inverted dependencies, boundary leaks.
3. **Do not report what a gate already catches.** Ruff, ty, pytest and CI fail loudly on their own; re-reporting them pads the review and trains the reader to skim.

## What to examine

- **Dependency direction.** Imports point one way: `api/` → `services/` → `dtos/` `enums/` `exceptions/` `utils/`, with `utils/` a leaf. `core/` is **cross-cutting infrastructure only** - settings, logging, the shared HTTP client, auth primitives - and is *not* where business logic goes (`backend/services.md`). Flag any import that runs uphill, and any `core/` module that has grown a domain decision.
- **Cycles**, including ones formed through `__init__.py` re-exports rather than direct imports.
- **Handler thinness.** A handler that validates, resolves dependencies and shapes one value into a DTO is correct. One that branches, orchestrates two I/O calls, or writes has earned a service.
- **Transport leakage.** `Request` / `Response` / `Depends` types below the API layer.
- **Public surface.** Explicit `__all__` over deep imports into internals; flag callers reaching past a stable export into file layout.
- **God modules by measurement, not reputation.** Rank by line count and by fan-in from the import graph above, and judge the top few. Do not assume a specific file is the problem.
- **Import-time side effects.** Work at module scope that belongs behind settings or lazy init - it makes startup order load-bearing and tests order-dependent.
- **Build parity.** The entrypoint has three homes (`make/variables.mk`, the Dockerfile `runtime` `CMD`, `[tool.fastapi] entrypoint`) and nothing checks that they agree. Healthchecks are **per stage**: each must target the port that stage serves.

## Output

**Critical** (cycles, inverted dependency, boundary leak, broken build wiring) → **Improvements** → **Optional** (prefix `Nit:`).

Each item: **what**, **where** (`file:line`), **why**, and the **rule it violates**. If nothing governs it, it is not a finding - say so rather than padding. One line per clean sub-area; silence is a valid result.

## Constraints

Read-only. `make check` and `make type-check` are the non-mutating gates; `make format` and `make ci` rewrite files. Hand off rather than duplicate: `code-reviewer` for rule conformance on a diff, `security-reviewer` for auth/secrets/config, `/code-review` for semantic bugs. Defer performance and security findings to their own commands. If context is short, name the files you still need.
