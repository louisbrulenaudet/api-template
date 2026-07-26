#!/usr/bin/env sh
# Purpose: Log session starts for debugging agent context loading.
# Target: Cursor sessionStart and Claude Code SessionStart.
# Canonical location: hooks/logging/ - wired from .cursor/hooks.json and .claude/settings.json.
#
# Contract:
#   stdout - SILENT, and deliberately so. SessionStart is one of the three events whose stdout
#            IS injected into the model's context; anything printed here costs context on every
#            single session. All output goes to the log file instead.
#   exit   - always 0. Exit codes are non-blocking on SessionStart anyway.
#
# Appends each event to hooks/logs/session-start.log (git-ignored). Cursor sends composer_mode /
# is_background_agent; Claude Code sends source (startup|resume|clear|compact|fork) and model.

INPUT=$(cat 2>/dev/null || true)
ROOT="${CURSOR_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-.}}"
LOG_DIR="$ROOT/hooks/logs"
LOG_FILE="$LOG_DIR/session-start.log"

mkdir -p "$LOG_DIR" 2>/dev/null || exit 0

LINE=""
if command -v jq >/dev/null 2>&1; then
  LINE=$(printf '%s' "$INPUT" | jq -c '{
    event: (.hook_event_name // "sessionStart"),
    session_id: (.session_id // null),
    source: (.source // null),
    model: (.model // null),
    permission_mode: (.permission_mode // null),
    composer_mode: (.composer_mode // null),
    is_background_agent: (.is_background_agent // null)
  }' 2>/dev/null || true)
fi
[ -z "$LINE" ] && LINE=$(printf '%s' "$INPUT" | tr '\n' ' ')

printf '%s\t%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$LINE" >> "$LOG_FILE" 2>/dev/null || true
exit 0
