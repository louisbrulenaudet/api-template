# Project configuration
PROJECT_NAME := ⚗️

# FastAPI app path (override when invoking make: `make dev APP=...`)
APP ?= app/main.py
# One of this value's three homes; keep them in step (ops/makefile).
ASGI_APP ?= app.main:app
DEV_PORT ?= 8000
PORT ?= 8001

# Docker configuration
APP_SERVICE := app
TUNNEL_SERVICE := cloudflared
TUNNEL_PROFILE := tunnel

# Never inline `docker compose` in a recipe - go through these. Every command naming a profiled
# service needs the profile flag, not just `up` (ops/makefile, ops/compose).
COMPOSE := docker compose
COMPOSE_TUNNEL := $(COMPOSE) --profile $(TUNNEL_PROFILE)

# Pydantic Logfire: do not export telemetry (defense-in-depth; applies to make dev/prod/check).
export LOGFIRE_SEND_TO_LOGFIRE := false
export LOGFIRE_PYDANTIC_PLUGIN_RECORD := off

# Colors for formatting
BLUE := \033[1;34m
CYAN := \033[1;36m
WHITE := \033[1;37m
RESET := \033[0m
