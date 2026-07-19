#!/usr/bin/env sh
# Purpose: Block Agent/Tab reads of secret files (.env, keys, credentials).
# Target: Cursor beforeReadFile and beforeTabFileRead (failClosed).
# Canonical location: hooks/security/ - wired from .cursor/hooks.json.
#
# Complements .cursorignore: Terminal/MCP are not bound by ignore files;
# this closes the Agent/Tab read path. Always emit allow JSON on the allow path
# so failClosed never sees empty stdout.

set -u

allow() {
  trap - EXIT INT TERM HUP
  printf '%s\n' '{"permission":"allow"}'
  exit 0
}

deny() {
  trap - EXIT INT TERM HUP
  msg="$1"
  printf '%s\n' "$msg" >&2
  json_msg=$(printf '%s' "$msg" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n' ' ')
  printf '%s\n' "{\"permission\":\"deny\",\"user_message\":\"$json_msg\"}"
  exit 2
}

trap 'allow' EXIT INT TERM HUP

INPUT=$(cat 2>/dev/null || true)

if command -v jq >/dev/null 2>&1; then
  FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.file_path // .tool_input.file_path // empty' 2>/dev/null || true)
else
  FILE_PATH=$(printf '%s' "$INPUT" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\(.*\)".*/\1/p' 2>/dev/null | head -1 || true)
fi

[ -z "$FILE_PATH" ] && allow

# Basename for extension checks; full path for .env / credentials patterns.
BASE=$(printf '%s' "$FILE_PATH" | sed 's|.*/||')

# Allow committed templates.
case "$BASE" in
  .env.template|*.example|*.example.*)
    allow
    ;;
esac

BLOCK_MSG="Blocked: refusing to read a secret file ($BASE). Secrets must not enter the model context — see .cursor/rules/core/guardrails.mdc. Use .env.template for non-secret examples."

# Match common secret filenames and key material.
case "$BASE" in
  .env|.env.*|*.pem|*.key|*.p12|*.pfx|id_rsa|id_rsa.pub|credentials|credentials.*|*credentials*|*secret*)
    deny "$BLOCK_MSG"
    ;;
esac

# Path segments (e.g. secrets/.env.local already covered by basename .env.*)
printf '%s' "$FILE_PATH" | grep -Eiq '(/|^)(\.env$|\.env\.|/credentials|/secrets?/)' && deny "$BLOCK_MSG"

allow
