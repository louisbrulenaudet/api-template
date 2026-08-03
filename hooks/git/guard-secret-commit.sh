#!/usr/bin/env sh
# Purpose: Block shell git commands that would stage/commit a secret file.
# Target: Cursor beforeShellExecution and Claude Code PreToolUse (Bash).
# Canonical location: hooks/git/ - wired from .cursor/hooks.json and .claude/settings.json.
#
# Enforces "Never commit secrets" (guardrails). Cursor failClosed expects JSON on stdout;
# Claude uses exit 2 + stderr. The allow path emits allow JSON so Cursor never sees empty output.
#
# Claude Code note: on exit 2 the stdout JSON is discarded and only stderr is fed back, so the
# reason is written to BOTH streams. The stdout object exists purely for Cursor's contract.
#
# This guard FAILS CLOSED (unlike the other hooks in this repo, which fail open): if it cannot
# parse its input or complete its checks, it refuses the command rather than letting a possible
# secret through. A guard that errors is a guard that is not enforcing.

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
  printf '%s\n' "{\"permission\":\"deny\",\"user_message\":\"$json_msg\",\"agent_message\":\"$json_msg\"}"
  exit 2
}

# Unexpected failure → refuse. Every deliberate exit path (allow / deny) clears this trap
# first, so it only fires on a genuine fault: unset variable under `set -u`, a killed pipeline,
# or a timeout signal. Staging a secret is not recoverable, so the safe default is "no".
fail_closed() {
  trap - EXIT INT TERM HUP
  msg="Blocked: the secret-staging guard (hooks/git/guard-secret-commit.sh) could not complete, so the command is refused rather than risk staging a secret. Fix the guard, or stage specific non-secret files explicitly."
  printf '%s\n' "$msg" >&2
  printf '%s\n' "{\"permission\":\"deny\",\"user_message\":\"$msg\",\"agent_message\":\"$msg\"}"
  exit 2
}

trap 'fail_closed' EXIT INT TERM HUP

INPUT=$(cat 2>/dev/null || true)
ROOT="${CURSOR_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-.}}"

if command -v jq >/dev/null 2>&1; then
  CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // .command // empty' 2>/dev/null || true)
else
  CMD=$(printf '%s' "$INPUT" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\(.*\)".*/\1/p' 2>/dev/null || true)
fi

[ -z "$CMD" ] && allow

# Only inspect commands that actually invoke git staging. Both words must appear as
# whitespace-delimited tokens. The previous `*git*add*` glob matched any string merely
# containing those letters anywhere - including this script's own path, `hooks/git/...`,
# which blocked unrelated commands and taught users to route around the guard.
if ! printf '%s' "$CMD" | grep -Eq '(^|[[:space:]])git([[:space:]]|$)' \
   || ! printf '%s' "$CMD" | grep -Eq '(^|[[:space:]])(add|commit|stage)([[:space:]]|$)'; then
  allow
fi

set -f

SECRET_RE='(\.env|\.dev\.vars|\.prod\.vars|\.staging\.vars|\.pem|\.key|\.p12|\.pfx|id_rsa|credentials)'
BLOCK_MSG="Blocked: this command looks like it would stage/commit a secret file (.env / .dev.vars / *.pem / *.key / credentials). Never commit secrets - see .cursor/rules/core/guardrails.mdc and .claude/rules/core/guardrails.md. Confirm the file is git-ignored and stage only non-secret files."

for tok in $CMD; do
  case "$tok" in
    *.example|*.example[!a-z]*) continue ;;
  esac
  if printf '%s' "$tok" | grep -Eiq "$SECRET_RE"; then
    deny "$BLOCK_MSG"
  fi
done

is_bulk() {
  { printf '%s' "$CMD" | grep -Eq '(^|[[:space:]])git[[:space:]]+add([[:space:]]|$)' \
      && printf '%s' "$CMD" | grep -Eq '(^|[[:space:]])(\.|-A|-u|--all|--update)([[:space:]]|$)'; } \
  || { printf '%s' "$CMD" | grep -Eq '(^|[[:space:]])git[[:space:]]+commit([[:space:]]|$)' \
      && printf '%s' "$CMD" | grep -Eq '(^|[[:space:]])-[A-Za-z]*a[A-Za-z]*([[:space:]]|$)'; }
}

if is_bulk; then
  # A bulk stage is exactly the case this guard exists for, so it cannot be waved through
  # when the working set is unknowable. No git, no verdict, no staging.
  command -v git >/dev/null 2>&1 \
    || deny "Blocked: cannot verify what a bulk stage would include because git is unavailable. Stage specific files explicitly."
  git -C "$ROOT" --no-optional-locks rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || deny "Blocked: cannot verify what a bulk stage would include because $ROOT is not a git work tree. Stage specific files explicitly."

  if git -C "$ROOT" status --porcelain 2>/dev/null \
       | sed -E 's/^...//; s/^.* -> //' \
       | grep -vE '\.example([^a-z]|$)' \
       | grep -Eiq "$SECRET_RE"; then
    deny "$BLOCK_MSG"
  fi
fi

allow
