#!/usr/bin/env sh
# Purpose: Append-only audit record of every Bash invocation the agent attempts.
# Event:   Claude Code PreToolUse (matcher: Bash). Wired from .claude/settings.json.
# Canonical location: hooks/logging/ - Claude Code only (Cursor has no equivalent event).
#
# Contract:
#   stdin  - hook JSON: session_id, cwd, permission_mode, tool_use_id, tool_input.command
#   stdout - SILENT. PreToolUse stdout is not injected into context; nothing must reach the model.
#   stderr - only when the audit write itself fails, so a broken audit surfaces loudly.
#   exit   - ALWAYS 0. An audit trail must never block work, and only exit 2 blocks anyway.
#
# Records intent, not outcome: PreToolUse fires before the permission check in every mode
# (including bypassPermissions), so denied and hook-blocked commands are captured too.
#
# The log lives OUTSIDE the repository, so `git clean -x`, worktree checkouts and the agent's
# own view of the diff never touch it. Override the root with CLAUDE_AUDIT_DIR (used by tests).

set -u

AUDIT_ROOT="${CLAUDE_AUDIT_DIR:-$HOME/.claude/audit}"
ROOT="${CLAUDE_PROJECT_DIR:-${CURSOR_PROJECT_DIR:-$PWD}}"
PROJECT=$(basename "$ROOT")
LOG_DIR="$AUDIT_ROOT/$PROJECT"
LOG_FILE="$LOG_DIR/$(date -u '+%Y-%m-%d').jsonl"
TS=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

INPUT=$(cat 2>/dev/null || true)

# Strip credential-looking values before anything is persisted. Bracket classes rather than
# a case-insensitive flag, because BSD sed (macOS) has no `I` modifier.
redact() {
  sed -E \
    -e 's/([A-Za-z0-9_]*[Kk][Ee][Yy][A-Za-z0-9_]*=)[^[:space:]]+/\1<REDACTED>/g' \
    -e 's/([A-Za-z0-9_]*[Tt][Oo][Kk][Ee][Nn][A-Za-z0-9_]*=)[^[:space:]]+/\1<REDACTED>/g' \
    -e 's/([A-Za-z0-9_]*[Ss][Ee][Cc][Rr][Ee][Tt][A-Za-z0-9_]*=)[^[:space:]]+/\1<REDACTED>/g' \
    -e 's/([A-Za-z0-9_]*[Pp][Aa][Ss][Ss][A-Za-z0-9_]*=)[^[:space:]]+/\1<REDACTED>/g' \
    -e 's/(--password[ =])[^[:space:]]+/\1<REDACTED>/g' \
    -e 's/(--token[ =])[^[:space:]]+/\1<REDACTED>/g' \
    -e 's/([Aa]uthorization:[[:space:]]*[A-Za-z]+[[:space:]]+)[^[:space:]]+/\1<REDACTED>/g' \
    2>/dev/null || cat
}

if command -v jq >/dev/null 2>&1; then
  RAW_CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // .command // empty' 2>/dev/null || true)
else
  RAW_CMD=$(printf '%s' "$INPUT" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\(.*\)".*/\1/p' 2>/dev/null | head -1 || true)
fi

CMD=$(printf '%s' "$RAW_CMD" | redact)

mkdir -p "$LOG_DIR" 2>/dev/null || {
  printf 'audit-bash: cannot create %s - Bash audit trail is NOT being written\n' "$LOG_DIR" >&2
  exit 0
}
chmod 700 "$LOG_DIR" 2>/dev/null || true

LINE=""
if command -v jq >/dev/null 2>&1; then
  LINE=$(printf '%s' "$INPUT" | jq -c --arg ts "$TS" --arg cmd "$CMD" '{
    ts: $ts,
    event: (.hook_event_name // "PreToolUse"),
    session_id: (.session_id // null),
    tool_use_id: (.tool_use_id // null),
    permission_mode: (.permission_mode // null),
    cwd: (.cwd // null),
    tool: (.tool_name // null),
    command: $cmd
  }' 2>/dev/null || true)
fi

# jq absent or input unparseable: emit a minimal, manually escaped record rather than nothing.
if [ -z "$LINE" ]; then
  esc=$(printf '%s' "$CMD" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n\t' '  ')
  LINE=$(printf '{"ts":"%s","event":"PreToolUse","command":"%s","degraded":true}' "$TS" "$esc")
fi

umask 077
printf '%s\n' "$LINE" >> "$LOG_FILE" 2>/dev/null || {
  printf 'audit-bash: cannot append to %s - Bash audit trail is NOT being written\n' "$LOG_FILE" >&2
  exit 0
}
chmod 600 "$LOG_FILE" 2>/dev/null || true

exit 0
