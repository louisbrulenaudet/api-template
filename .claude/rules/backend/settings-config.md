---
paths:
  - "app/core/**"
---

# Settings and Config

Pydantic Settings in `app/core/config.py`. Required secrets and identifiers come from the environment, and
validation is allowed to raise - never invent a silent default for a secret.

- **No `alias=` on settings fields.** pydantic-settings already matches field names to env vars
  case-insensitively, so `api_key` reads `API_KEY` without help. Only `name` needs one, and it uses
  `validation_alias="APP_NAME"` plus `populate_by_name=True`. Using `alias=` combined with
  `extra="ignore"` makes `Settings(name="X")` **silently return the default** instead of raising - a wrong
  value with no error, which is the worst failure mode available here.
- **`ENVIRONMENT=production` is the fail-closed gate** (`app/enums/environment.py`).
  `_enforce_production_hardening` refuses to boot on wildcard `ALLOWED_ORIGINS`/`ALLOWED_HOSTS` or an empty
  `API_KEY`. Add new "safe locally, unsafe in prod" defaults **to that validator**, not to a comment.
- **`docs_enabled` is `bool | None`**: `None` derives from the environment (off in production), an explicit
  value always wins. Read it through the `docs_are_enabled` property, never the raw field.
- **`@lru_cache(maxsize=1)` belongs only on `get_settings()`.** Do not add unbounded `lru_cache` to
  user-keyed or async helpers - use aiocache for async TTL caches. Tests interacting with the cached global
  are covered in [testing.md](../quality/testing.md).
- **Keep `.env.template` in sync** when adding or removing a settings field - names and comments only, never
  a real value. It is committed on purpose, so it is the one `.env*` file you may read and edit.
