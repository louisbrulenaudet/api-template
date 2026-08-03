#!/usr/bin/env sh
# Purpose: Refuse writes to secret / protected paths.
# Event:   Claude Code PreToolUse (matcher: Edit|Write|NotebookEdit|MultiEdit).
# Canonical location: hooks/security/ - wired from .claude/settings.json.
#
# Contract:
#   stdin  - hook JSON: tool_input.file_path (also .tool_input.notebook_path for NotebookEdit)
#   stdout - SILENT. PreToolUse stdout is not injected, and exit 2 discards it anyway.
#   stderr - actionable reason, fed back to Claude as the block reason.
#   exit   - 2 blocks the call, 0 allows. Exit 2 is the ONLY blocking code; exit 1 would NOT block.
#
# Defence in depth behind the permissions.deny Edit(...) rules. Those rules are authoritative
# and cheaper, and a hook can never loosen them - but they cannot express the
# *.template / *.example allowlist, and they hand Claude no actionable reason. This does both.
#
# Why this hook exists at all: a Read deny also blocks the Edit tool (v2.1.208+), but NOT the
# Write or NotebookEdit tools. Without an Edit(...) deny plus this guard, `Write` could create
# or clobber .env / id_rsa / *.pem with no prompt under defaultMode "acceptEdits".

set -u

INPUT=$(cat 2>/dev/null || true)

if command -v jq >/dev/null 2>&1; then
  FILE_PATH=$(printf '%s' "$INPUT" | jq -r '
    .tool_input.file_path // .tool_input.notebook_path // .file_path // empty' 2>/dev/null || true)
else
  FILE_PATH=$(printf '%s' "$INPUT" | sed -n 's/.*"\(file_path\|notebook_path\)"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\2/p' 2>/dev/null | head -1 || true)
fi

# No path to judge - nothing to protect. Fail open: this guard backs up authoritative
# deny rules, so an unparseable payload must not wedge every edit in the session.
[ -z "$FILE_PATH" ] && exit 0

BASE=$(printf '%s' "$FILE_PATH" | sed 's|.*/||')

block() {
  printf 'Blocked: refusing to write %s (%s).\n' "$FILE_PATH" "$1" >&2
  printf 'Secrets and key material must never be written by the agent - see .claude/rules/core/guardrails.md.\n' >&2
  printf 'If you need an example value, edit .env.template or a *.example file instead.\n' >&2
  exit 2
}

# Path traversal, per the hooks documentation's security best practices.
case "$FILE_PATH" in
  *../*|*/..) block "path traversal" ;;
esac

# Committed, non-secret templates stay editable. Checked before the deny patterns so that
# .env.template and *.example.* survive the .env.* rule below.
case "$BASE" in
  .env.template|*.template|*.example|*.example.*) exit 0 ;;
esac

case "$BASE" in
  .env|.env.*)                    block "environment file holding real credentials" ;;
  *.pem|*.key|*.p12|*.pfx|*.keystore|*.crt)
                                  block "private key or certificate material" ;;
  id_rsa|id_rsa.pub|id_ed25519|id_ed25519.pub)
                                  block "SSH key material" ;;
  credentials|credentials.*|.pypirc|.netrc)
                                  block "stored credentials file" ;;
  .dev.vars|.prod.vars|.staging.vars)
                                  block "deployment secrets file" ;;
esac

# Directory-scoped protection for anything filed under a secrets/ tree.
printf '%s' "$FILE_PATH" | grep -Eq '(^|/)(secrets?|\.ssh|\.gnupg)/' \
  && block "path inside a protected secrets directory"

exit 0
