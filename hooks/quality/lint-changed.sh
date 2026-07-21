#!/usr/bin/env sh
# Purpose: Apply safe lint autofixes to an edited Python file, then feed remaining problems back.
# Target: called by check-changed.sh after Cursor afterFileEdit or Claude Edit|Write.
# Canonical location: hooks/quality/ - wired from .cursor/hooks.json and .claude/settings.json.
#
# Exits 2 with ruff output on stderr when the file has problems. Post-tool
# callers receive feedback, but the completed edit is not rolled back.

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

RUFF_CMD=""
if command -v uv >/dev/null 2>&1; then
  RUFF_CMD="uv run ruff"
elif command -v ruff >/dev/null 2>&1; then
  RUFF_CMD="ruff"
fi
[ -z "$RUFF_CMD" ] && exit 0

# --fix is passed explicitly (rather than via [tool.ruff] fix=true) so a bare
# `ruff check` in CI still reports violations instead of silently fixing them.
if OUT=$($RUFF_CMD check --fix "$FILE" 2>&1); then
  exit 0
fi

printf 'ruff reported problems in %s:\n%s\n' "$FILE" "$OUT" >&2
exit 2
