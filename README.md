# FastAPI starter with Pydantic validation, Docker, and Cloudflare Tunnel 🚚⛅

[![FastAPI](https://img.shields.io/static/v1?label=framework&message=FastAPI&color=blue&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Pydantic](https://img.shields.io/static/v1?label=validation&message=Pydantic&color=blue&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![Docker](https://img.shields.io/static/v1?label=deployment&message=Docker&color=blueviolet&logo=docker&logoColor=white)](https://www.docker.com/)
[![uv](https://img.shields.io/static/v1?label=package%20manager&message=uv&color=blueviolet&logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/static/v1?label=linting&message=Ruff&color=blueviolet&logo=ruff&logoColor=white)](https://github.com/astral-sh/ruff)
[![GitHub Actions](https://img.shields.io/static/v1?label=ci/cd&message=GitHub%20Actions&color=blueviolet&logo=github-actions&logoColor=white)](https://github.com/features/actions)

A minimal, production-ready FastAPI template with strict request/response validation (Pydantic v2 settings and DTOs), a hardened multi-stage Docker image, Compose for local development, and an optional Cloudflare Tunnel for a public HTTPS URL without exposing an inbound port on your host.

Use the Makefile and **uv** for dependency management and day-to-day commands.

## Tech Stack

- **Language:** Python 3.14+ (strict type hints)
- **Framework:** FastAPI (async web framework)
- **Validation:** Pydantic v2 (data validation and settings management)
- **HTTP Client:** httpx2 (async HTTP client with brotli + HTTP/2)
- **Caching:** aiocache (async caching)
- **Formatting/Linting:** Ruff (fast Python linter and formatter)
- **Package Manager:** uv (fast Python package installer and resolver)
- **Build Tools:** Docker, Docker Compose
- **Automation:** Makefile
- **Environment:** python-dotenv (.env)
- **Testing:** pytest, pytest-asyncio, pytest-cov

## Project Structure

```
.
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   └── base.py          # Health check endpoints (ping, health)
│   │       └── router.py            # API router configuration
│   ├── core/
│   │   ├── config.py                # Application settings and configuration
│   │   ├── http_client.py           # Shared lifespan-scoped httpx2.AsyncClient (typed accessors)
│   │   ├── logging_config.py        # dictConfig + request-ID log filter / JSON formatter
│   │   └── security.py              # require_api_key: X-API-Key dependency
│   ├── dtos/                        # Pydantic DTOs for request/response validation
│   │   └── error_response.py        # The single error envelope for every failure
│   ├── enums/
│   │   ├── environment.py           # development | staging | production
│   │   └── error_codes.py           # Centralized error code definitions
│   ├── exceptions/
│   │   ├── core_exception.py        # Base exception class with structured error handling
│   │   ├── authentication_error.py  # 401 for a missing/invalid credential
│   │   ├── client_initialization_error.py  # Client initialization error
│   │   └── handlers.py              # CoreError / validation / HTTP / catch-all -> ErrorResponse
│   ├── middlewares/
│   │   ├── request_id.py            # X-Request-ID correlation middleware (pure ASGI)
│   │   ├── security_headers.py      # nosniff / DENY / no-referrer / COOP (+ HSTS)
│   │   └── setup.py                 # configure_middleware(): the LIFO middleware stack
│   ├── utils/
│   │   └── decorators.py            # Utility decorators (retry, async_retry)
│   └── main.py                      # create_app() factory, middleware/handlers, lifespan
├── make/
│   ├── dev.mk                       # Development commands
│   ├── docker.mk                    # Docker-related commands
│   ├── help.mk                      # Help command implementation
│   └── variables.mk                 # Makefile variables
├── tests/                           # Test suite
├── pyproject.toml                    # Project configuration, dependencies, and tool settings
├── compose.yaml                     # Docker Compose (local development)
├── Dockerfile                       # Docker image definition
├── Makefile                         # Main Makefile with command shortcuts
├── uv.lock                          # Locked dependency graph (canonical for uv, CI, and Docker)
└── requirements.txt                 # Optional pip-style export (`make export-requirements`; `uv.lock` is canonical)
```

## Environment Configuration

### Required Environment Variables

The application uses Pydantic Settings for configuration management. Field names map to environment variables case-insensitively, so `api_key` reads `API_KEY`; only `name` carries an alias (`APP_NAME`). All settings live in `app/core/config.py`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENVIRONMENT` | `development` | `development` \| `staging` \| `production`. Production enforces the guards below. |
| `APP_NAME` | `Backend` | Application name (OpenAPI title). |
| `API_KEY` | *(empty)* | Shared secret checked by `require_api_key`. |
| `API_CLIENT` | *(empty)* | API client identifier. |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins. |
| `ALLOW_CREDENTIALS` | `false` | Allow credentialed CORS. Never valid together with `*` origins. |
| `ALLOWED_HOSTS` | `*` | Comma-separated `Host` allowlist (`TrustedHostMiddleware`). |
| `DOCS_ENABLED` | *(auto)* | Unset ⇒ on outside production, off in production. Explicit value always wins. |
| `FORCE_HTTPS` | `false` | Redirect HTTP→HTTPS and send HSTS. |
| `ROOT_PATH` | *(empty)* | ASGI `root_path` when a proxy serves the app under a sub-path. |
| `LOG_LEVEL` | `INFO` | Standard level name. |
| `LOG_JSON` | `false` | Emit one JSON object per log record. |

### Production fails closed

With `ENVIRONMENT=production`, the app **refuses to start** unless you replace the permissive template defaults - a misconfiguration becomes a startup error with a precise message rather than a silently insecure deployment:

- `ALLOWED_ORIGINS` must list explicit origins (not `*`)
- `ALLOWED_HOSTS` must list explicit hostnames (not `*`)
- `API_KEY` must be set

`/docs`, `/redoc` and `/openapi.json` are also disabled in production unless `DOCS_ENABLED=true`.

### Authentication

`API_KEY` is enforced by `require_api_key` (`app/core/security.py`), which compares in constant time and reports failures through the standard error envelope. It is **not** applied globally, because the health probes must stay unauthenticated. Apply it where you need it:

```python
from fastapi import APIRouter, Depends
from app.core.security import require_api_key

router = APIRouter(dependencies=[Depends(require_api_key)])
```

### Error responses

Every failure - domain `CoreError`, request validation, a bare `HTTPException`, or an unhandled exception - returns the same `ErrorResponse` shape (`app/dtos/error_response.py`), documented in OpenAPI:

```json
{
  "error": "RequestValidationError",
  "message": "Request validation failed.",
  "code": "VALIDATION_ERROR",
  "details": [{"type": "int_parsing", "loc": ["query", "n"], "msg": "..."}],
  "request_id": "0f9c1d2e3a4b5c6d7e8f9a0b1c2d3e4f"
}
```

`details` is withheld on 5xx responses (it describes an internal failure and is logged instead), and `request_id` always matches the `X-Request-ID` response header.

### Behind a proxy

The image sets `FORWARDED_ALLOW_IPS` to the RFC1918 ranges so `X-Forwarded-For` / `X-Forwarded-Proto` from a sidecar proxy (the `cloudflared` service) are honoured. uvicorn's default trusts only `127.0.0.1`, which never matches another container - leaving `request.client.host` wrong and making `FORCE_HTTPS` redirect-loop. Override per deployment if your proxy sits elsewhere.

### Telemetry and tooling

This project avoids the FastAPI Cloud CLI stack (`fastapi-cloud-cli` / `sentry-sdk`) by depending on `fastapi-cli[standard-no-fastapi-cloud-cli]` with the same “standard” pieces as `fastapi[standard]`. Logfire export is disabled by default via environment variables in the Makefile, Docker, Compose, and CI. **uv** does not document a switch to turn off PyPI User-Agent metadata; see [astral-sh/uv#8474](https://github.com/astral-sh/uv/issues/8474).

### Setup Instructions

1. **Install dependencies:**

   ```sh
   make sync
   ```

   (`make install` is an alias for `sync`. `make sync` runs `uv sync --frozen` - it installs `uv.lock` exactly; the `dev` dependency group is included by default, matching CI.)

2. **Configure environment:**

   Copy `.env.template` to `.env` and fill in required variables:

   ```
   APP_NAME=Backend
   ...
   ```

3. **(Optional) Run with Docker Compose**

   Your `compose.yaml` uses `env_file: .env` to pass these values at **container start** (this is runtime configuration; it is not related to `.dockerignore`).

   Example:

   ```sh
   docker compose up --watch   # live reload via Compose watch (see below)
   # or
   make docker-run-dev
   ```

   `--watch` syncs edits under `app/` into the running container (instant reload) and rebuilds the image when `pyproject.toml` / `uv.lock` change - no bind mount needed. The app is published on **127.0.0.1:8000** on the host (loopback only), matching `make dev`. Use [http://127.0.0.1:8000](http://127.0.0.1:8000) or `localhost` from the same machine.

   If you want to set values explicitly in YAML (not recommended for real secrets), you can use:

   ```yaml
   environment:
     APP_NAME: "Backend"
     ...
   ```

4. **(Optional) Cloudflare Tunnel (development sharing)**

   To share the API without opening port `8000` on your LAN (e.g. for testing): set `TUNNEL_TOKEN` in your shell or in `.env`, then run `make docker-run-dev-tunnel` (tunnel is opt-in via the Compose profile `tunnel`). `cloudflared` prints the public tunnel URL in the terminal (or use `make docker-tunnel-logs`).

   `TUNNEL_TOKEN` is read by **Compose**, not by the app: it feeds the top-level `secrets:` element, which delivers the value to the `cloudflared` container as a file at `/run/secrets/tunnel_token`. Because `.env` is *also* loaded into the app container via `env_file:`, `compose.yaml` explicitly sets `TUNNEL_TOKEN: ""` on the `app` service so the tunnel's bearer credential never reaches the internet-facing process. Do not remove that line.

   > **This is a demo link, not a deployment.** `compose.yaml` pins `ENVIRONMENT=development`, which leaves `/docs`, the full OpenAPI schema, and any wildcard `ALLOWED_ORIGINS` / `ALLOWED_HOSTS` in place, and lets an empty `API_KEY` boot. Tear the tunnel down when you are done (`make docker-tunnel-stop`). Compose here is local development only - for anything durable, deploy the `runtime` image with `ENVIRONMENT=production`, which fails closed unless `ALLOWED_ORIGINS`, `ALLOWED_HOSTS` and `API_KEY` are set explicitly.

5. **Development:**

   ```sh
   make dev
   ```

   Default dev port is **8000** (`DEV_PORT` in [`make/variables.mk`](make/variables.mk)); Docker Compose dev uses the same port on the host.

   - The API will be available at [http://localhost:8000](http://localhost:8000)
   - Ping endpoint: [http://localhost:8000/api/v1/ping](http://localhost:8000/api/v1/ping)

## Common Commands

The following Makefile commands are available for development, formatting, testing, and deployment:

### Development Commands

| Command                | Description                                 |
|------------------------|---------------------------------------------|
| `make dev`             | Run development server with hot reloading   |
| `make test`            | Run the test suite with coverage            |
| `make sync`            | Sync `.venv` from `uv.lock` (`--frozen`; `dev` group) |
| `make sync-all`        | Sync all dependency groups from `uv.lock`   |
| `make install`         | Alias for `make sync`                       |
| `make lock`            | Lock project dependencies                   |
| `make update`         | Update locked deps (`uv lock --upgrade` + sync) |
| `make export-requirements` | Regenerate `requirements.txt` from `uv.lock` |
| `make clean-venv`      | Remove local `.venv`                        |
| `make type-check`      | Type check the source code using Ty         |
| `make check`           | Run code quality checks (Ruff linting)      |
| `make format`          | Format the codebase using Ruff              |
| `make ci`              | Ruff format/lint + ty (no tests)            |
| `make pre-commit`      | Run pre-commit checks on all files          |

### Docker Commands

| Command                | Description                                  |
|------------------------|----------------------------------------------|
| `make docker-check`    | Verify Docker installation and configuration |
| `make docker-check-build` | Run Docker's build checks without building (CI gate) |
| `make docker-config`   | Validate `compose.yaml`, with and without the tunnel profile (CI gate) |
| `make docker-build`    | Create application containers                |
| `make docker-rebuild`  | Rebuild containers with fresh configuration  |
| `make docker-start`    | Launch application services                  |
| `make docker-stop`     | Stop all running services                    |
| `make docker-restart`  | Restart all application services             |
| `make docker-logs`     | Display container logs                       |
| `make docker-clean`    | Remove all containers and volumes            |
| `make docker-run-dev`  | Start development server with live reload    |
| `make docker-run-dev-tunnel`  | Start dev + Cloudflare Tunnel (opt-in)       |
| `make docker-tunnel-logs`     | Follow Cloudflare Tunnel logs                |
| `make docker-tunnel-stop`     | Stop Cloudflare Tunnel (keeps app)           |

The [`Dockerfile`](Dockerfile) exposes two targets: `runtime` (uvicorn, dependencies only-what CI builds) and `reload` (same dependency set as `runtime`, but runs `fastapi dev` with reload for local Compose). Optional `[dev]` extras (pytest, ruff, etc.) are for local/CI tooling, not installed in the image.

The [`.dockerignore`](.dockerignore) uses an **allowlist** strategy: everything is excluded by default (`*`) and only the three paths the Dockerfile actually copies are re-included - `pyproject.toml`, `uv.lock`, and `app/`. This keeps the build context minimal and ensures any file added to the repository in the future is automatically excluded without requiring a `.dockerignore` update.

## Best Practices

- Always validate request/response data using Pydantic models before processing
- Always use DTO objects for data propagation during runtime
- Implement comprehensive error handling with meaningful error messages
- Use environment variables for configuration and secrets (never hardcode sensitive data)
- Always run `make check` and `make format` before committing
- Use Makefile for common tasks to ensure consistency across the team
- Follow RESTful API design principles
- Use utility decorators (`retry`, `async_retry`) for operations that may fail transiently
- Implement proper async/await patterns throughout the application
- Use dependency injection for testability and maintainability
- Document all public functions and classes with docstrings

- **Template / modular development:** Keep components modular and independent to enable parallel work and clean merges

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose for containerization and local development.
- [uv](https://github.com/astral-sh/uv) (Python dependency manager)
- [ruff](https://docs.astral.sh/ruff/) (linter/formatter)

In order to run the backend the fastest way possible, you can use the makefile setup and uv for Python dependency management as this:

```sh
make sync
make update
make dev
```

Then you can ping the API at [http://127.0.0.1:8000/api/v1/ping](http://127.0.0.1:8000/api/v1/ping).

If you need to install packages such as transformers, you can do so with the following command:

```sh
uv add transformers
```

## Code Quality

- Lint and check code:
  ```sh
  make check
  ```

- Format code:
  ```sh
  make format
  ```

- Type check:
  ```sh
  make type-check
  ```

## Citing this project

If you use this code in your research, please use the following BibTeX entry.

```BibTeX
@misc{louisbrulenaudet2026,
author = {Louis Brulé Naudet},
title = {A minimal, production-ready template for building APIs with FastAPI, featuring strict data validation and Docker-based containerization, tailored for express deployment via a secure Cloudflare Tunnel 🚚⛅},
howpublished = {\url{https://github.com/louisbrulenaudet/api-template}},
year = {2026}
}
```

---

## Feedback

If you have any feedback, please reach out at [louisbrulenaudet@icloud.com](mailto:louisbrulenaudet@icloud.com).
