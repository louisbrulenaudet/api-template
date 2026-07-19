#!/usr/bin/env sh
# Purpose: Format a Python file right after an agent writes/edits it, so edits stay CI-clean.
# Target: called by check-changed.sh after Cursor afterFileEdit or Claude Edit|Write.
# Canonical location: hooks/quality/ - wired from .cursor/hooks.json and .claude/settings.json.
#
# Non-blocking: always exits 0. Missing uv/ruff is a no-op.

INPUT=$(cat 2>/dev/null || true)
ROOT="${CURSOR_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-.}}"

if command -v jq >/dev/null 2>&1; then
  FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .file_path // empty' 2>/dev/null || true)
else
  FILE=$(printf '%s' "$INPUT" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' 2>/dev/null || true)
fi

[ -z "$FILE" ] && exit 0
[ -f "$FILE" ] || exit 0

case "$FILE" in
  *.py) ;;
  *) exit 0 ;;
esac

cd "$ROOT" || exit 0

if command -v uv >/dev/null 2>&1; then
  uv run ruff format "$FILE" >/dev/null 2>&1 || true
elif command -v ruff >/dev/null 2>&1; then
  ruff format "$FILE" >/dev/null 2>&1 || true
fi
exit 0
