# make/variables.mk

# Project configuration
PROJECT_NAME := ⚗️

# FastAPI app path (override when invoking make: `make dev APP=...`)
APP ?= app/main.py
HOST ?= 0.0.0.0
DEV_PORT ?= 8000
PORT ?= 8001

# Docker configuration
APP_SERVICE := app

# Pydantic Logfire: do not export telemetry (defense-in-depth; applies to make dev/prod/check).
export LOGFIRE_SEND_TO_LOGFIRE := false
export LOGFIRE_PYDANTIC_PLUGIN_RECORD := off

# Colors for formatting
BLUE := \033[1;34m
CYAN := \033[1;36m
WHITE := \033[1;37m
RESET := \033[0m
