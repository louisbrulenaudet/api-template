---
description: Configuration review - env/secrets handling, .env.template, Docker/Compose parity, uv frozen installs, Pydantic Settings contract, Ruff config, ports/healthcheck. Outputs a plan only.
argument-hint: [scope: files, directory, or "all"]
---

# Review configuration

Review environment and secrets handling, the settings contract, and dev/prod parity. Reply with a **plan only**: no edits, no implementation unless asked.

## Scope

Default to **the change under review**: `git diff`, `git diff --cached`, and untracked files. `$ARGUMENTS` overrides it. On `all`, say what you read and what you sampled.

## Authority

`.cursor/rules/` is authoritative; reading a file loads its rules, so **cite them and do not restate them**. The settings contract is `backend/settings-config`; image build and secrets-in-layers are `ops/dockerfile`; the Compose stack and runtime secrets are `ops/compose`; targets and parity are `ops/makefile`; workflow hardening is `ops/ci`; dependency pins are `quality/uv-dependencies`; Ruff and ty config are `quality/lint-and-types`.

**Read the files; never assert from memory what the config contains.** Ports, stage names, probe mechanisms and install flags all change. Check the file, then review it.

## Never open a secret

Do not read or print `.env` or any key, certificate or credential file - `permissions.deny` blocks most of them and that is deliberate. Review the **variable names the code expects**, and whether `.gitignore` / `.dockerignore` / Compose cover them. `.env.template` is the one `.env*` file you may read and edit: it is committed on purpose and holds names and comments only.

## Rank by enforcement gap

Configuration is where fail-open dominates, so this is the ranking that matters most:

1. **`Nothing enforces this:` violations first** (`grep -rn 'Nothing enforces this' .cursor/rules/`). Every one of them passes CI. The clearest example: deleting the line in `compose.yaml` that scrubs a sidecar-only credential from the app service is a silent leak, and `docker compose config` is happy either way.
2. **Version pins with more than one home**, because nothing compares them: the uv pin has three, the entrypoint has three, and the Python version has four. A partial bump leaves the tree internally inconsistent and every gate green.
3. **Do not report** what `make ci-check`, `make docker-check-build`, `make docker-config`, `check-requirements`, `verify-base-digests` or the image smoke step already fail on.

## What to examine

- **Secrets never reach an image layer or a container environment.** Not in `ENV`, not in `ARG`, not via `COPY .env` - they persist in `docker history`, so the leak outlives the build. Build-time secrets use `RUN --mount=type=secret`; runtime uses Compose `secrets:` / `env_file`. `assert-no-baked-credentials` catches the shapes it knows, not all of them.
- **`.env` is read twice by Compose** - once for interpolation, once through `env_file:` - so a credential only a sidecar needs must be scrubbed explicitly in the app service's `environment:`, which outranks `env_file`. `env_file` has no exclusion mechanism.
- **The build context is an allowlist.** `.dockerignore` excludes everything, then re-includes what the Dockerfile copies, so a new `COPY` needs a matching `!` entry in the same change. It does **not** consult `.gitignore`, so gitignored-but-present files still need explicit re-exclusion.
- **The production gate fails closed.** Under `ENVIRONMENT=production`, wildcard origins or hosts and an empty API key must still refuse to boot, and docs must default off. A new "safe locally, unsafe in prod" default belongs in that validator, not in a comment.
- **Settings contract.** No `alias=` where case-insensitive env matching already works - combined with `extra="ignore"` it makes a constructor silently return the default instead of raising. `.env.template` updated whenever a field is added or removed.
- **Parity, per stage.** Each servable stage's healthcheck must target the port *that stage* serves, and a Compose `healthcheck` replaces the image's wholesale, flags included. Check what the probe actually is before reviewing it - and check whether the tools it needs exist in that image.
- **Deterministic installs.** `--frozen`, never `--locked`; `uv.lock` changed only through `make lock` / `make update`; `requirements.txt` re-exported after every one of them, since that export and not the lockfile is what the dependency graph reads.
- **Compose is dev-only.** One file, one dev stage. Production posture belongs in the k8s manifests, and the proof the runtime image is deployable is CI's smoke step. A second Compose file modelling production is a finding.

## Output

**Critical** (secret reachable in a layer or container env, production gate weakened, pin drift, broken runtime wiring) → **Improvements** → **Optional** (prefix `Nit:`).

Each item: **what**, **where** (`file:line`), **why**, and the **rule it violates**. If no rule governs it, it is not a finding. One line per clean sub-area; silence is a valid result.

## Constraints

Read-only. `make check` and `make type-check` are non-mutating; `make format` and `make ci` rewrite files. Never hand-edit `uv.lock` - if the review concludes it is stale, the finding is "run `make lock`". Hand off to `security-reviewer` for a full credential and fail-open audit. Defer architecture and performance to their own commands.
