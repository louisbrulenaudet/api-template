#!/usr/bin/env sh
# Purpose: Record every Claude Code configuration mutation to the append-only audit log.
# Event:   Claude Code ConfigChange. Wired from .claude/settings.json.
# Canonical location: hooks/logging/ - Claude Code only (Cursor has no equivalent event).
#
# Contract:
#   stdin  - hook JSON: config_source, changed_keys[], file_path
#   stdout - a {"systemMessage": ...} object when hooks/permissions change; otherwise SILENT.
#            ConfigChange stdout is not injected into context, but systemMessage is shown
#            to the user, which is the point: a change to the enforcement surface is visible.
#   stderr - only when the audit write itself fails.
#   exit   - ALWAYS 0. Deliberately non-blocking: exit 2 here would block the user's own edits.
#
# Why this hook exists: settings files are hot-reloaded by a file watcher, and the current
# documentation has no review or confirmation step for that reload. ConfigChange is therefore
# the only in-session record that hooks, permissions or skills changed underneath the session.
# Note that policy_settings changes cannot be blocked by any hook, only observed.

set -u

AUDIT_ROOT="${CLAUDE_AUDIT_DIR:-$HOME/.claude/audit}"
ROOT="${CLAUDE_PROJECT_DIR:-${CURSOR_PROJECT_DIR:-$PWD}}"
PROJECT=$(basename "$ROOT")
LOG_DIR="$AUDIT_ROOT/$PROJECT"
LOG_FILE="$LOG_DIR/$(date -u '+%Y-%m-%d').jsonl"
TS=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

INPUT=$(cat 2>/dev/null || true)

mkdir -p "$LOG_DIR" 2>/dev/null || {
  printf 'audit-config-change: cannot create %s - config audit is NOT being written\n' "$LOG_DIR" >&2
  exit 0
}
chmod 700 "$LOG_DIR" 2>/dev/null || true

if ! command -v jq >/dev/null 2>&1; then
  umask 077
  printf '{"ts":"%s","event":"ConfigChange","degraded":true}\n' "$TS" >> "$LOG_FILE" 2>/dev/null || true
  exit 0
fi

LINE=$(printf '%s' "$INPUT" | jq -c --arg ts "$TS" '{
  ts: $ts,
  event: "ConfigChange",
  session_id: (.session_id // null),
  config_source: (.config_source // .source // null),
  file_path: (.file_path // null),
  changed_keys: (.changed_keys // [])
}' 2>/dev/null || true)

umask 077
[ -n "$LINE" ] && { printf '%s\n' "$LINE" >> "$LOG_FILE" 2>/dev/null || true; }
chmod 600 "$LOG_FILE" 2>/dev/null || true

# Surface changes to the enforcement surface itself. Anything touching hooks, permissions or
# the plugin set changes what is enforced, so the user is told rather than left to notice.
SENSITIVE=$(printf '%s' "$INPUT" \
  | jq -r '[(.changed_keys // [])[] | select(test("^(hooks|permissions|enabledPlugins|disableAllHooks)"))] | join(", ")' \
    2>/dev/null || true)

if [ -n "${SENSITIVE:-}" ]; then
  SRC=$(printf '%s' "$INPUT" | jq -r '.config_source // .source // "settings"' 2>/dev/null || echo settings)
  jq -cn --arg s "$SRC" --arg k "$SENSITIVE" \
    '{systemMessage: ("Claude Code enforcement config changed in " + $s + ": " + $k + " (recorded in the audit log).")}' \
    2>/dev/null || true
fi

exit 0
