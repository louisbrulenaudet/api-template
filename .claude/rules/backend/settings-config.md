---
paths:
  - "app/core/**"
---

# Settings and Config

Configuration lives in `app/core/config.py` via Pydantic Settings.

## Rules

- Required secrets and identifiers come from the environment (`.env` locally; never commit `.env`).
- **No `alias=` on settings fields.** pydantic-settings matches field names to env vars case-insensitively, so `api_key` already reads `API_KEY`. Only `name` needs one, and it uses `validation_alias="APP_NAME"` plus `populate_by_name=True`. Never use `alias=`: combined with `extra="ignore"` it makes `Settings(name="X")` **silently return the default** instead of raising.
- Keep `.env.template` in sync when adding/removing settings fields - without real secret values.
- Fail closed on missing required config (let Settings validation raise), do not invent silent defaults for secrets.
- **`ENVIRONMENT=production` is the fail-closed gate** (`app/enums/environment.py`). `_enforce_production_hardening` refuses to boot when `ALLOWED_ORIGINS`/`ALLOWED_HOSTS` are still `*` or `API_KEY` is empty. Add new "safe locally, unsafe in prod" defaults to that validator rather than to a comment.
- `docs_enabled` is `bool | None`: `None` derives from the environment (off in production), an explicit value always wins. Read it through the `docs_are_enabled` property, never the raw field.
- `@lru_cache(maxsize=1)` belongs only on `get_settings()`. Do not add unbounded `lru_cache` on user-keyed or async helpers.
- For async TTL caches use aiocache (configured in app lifespan), not `lru_cache`.
- Tests that change env/settings must call `get_settings.cache_clear()` - or better, avoid the global entirely and build settings with `tests.conftest.build_settings()`, which uses `model_validate` so no env/`.env` is consulted.

## Telemetry defaults

Keep Logfire send/plugin flags off unless the user explicitly enables them (see Makefile variables / Docker / CI).
