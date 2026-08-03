#!/usr/bin/env sh
# Purpose: Block history-rewriting / working-tree-destroying git commands.
# Target: Cursor beforeShellExecution and Claude Code PreToolUse (Bash).
# Canonical location: hooks/git/ - wired from .cursor/hooks.json and .claude/settings.json.
#
# Mirrors guardrails. Cursor failClosed expects JSON on stdout; Claude uses exit 2 + stderr.
# Always emit allow JSON so empty output never fail-closes.

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

trap 'allow' EXIT INT TERM HUP

INPUT=$(cat 2>/dev/null || true)

if command -v jq >/dev/null 2>&1; then
  CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // .command // empty' 2>/dev/null || true)
else
  CMD=$(printf '%s' "$INPUT" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\(.*\)".*/\1/p' 2>/dev/null || true)
fi

[ -z "$CMD" ] && allow

case "$CMD" in
  *git*) ;;
  *) allow ;;
esac

word() { printf '%s' "$CMD" | grep -Eq "(^|[[:space:]])$1([[:space:]]|\$)"; }

REASON=""

if word 'reset' && word '\-\-hard'; then
  REASON="git reset --hard discards uncommitted changes"
elif word 'clean' && { printf '%s' "$CMD" | grep -Eq '(^|[[:space:]])-[A-Za-z]*f[A-Za-z]*([[:space:]]|$)' || word '\-\-force'; }; then
  REASON="git clean -f permanently deletes untracked files"
elif word 'push' && { word '\-\-force' || word '\-\-force-with-lease' || word '\-f'; }; then
  REASON="git push --force rewrites remote history"
elif word 'push' && word '\-\-delete'; then
  REASON="git push --delete removes a remote branch/tag"
elif word 'branch' && { word '\-d' || word '\-D' || word '\-\-delete'; }; then
  REASON="git branch -d/-D deletes a branch"
elif word 'tag' && { word '\-d' || word '\-\-delete'; }; then
  REASON="git tag -d deletes a tag"
elif word 'checkout' && { printf '%s' "$CMD" | grep -Eq '(^|[[:space:]])--([[:space:]]|$)' || word '\.'; }; then
  REASON="git checkout -- / git checkout . discards uncommitted changes"
elif word 'restore' && ! word '\-\-staged'; then
  REASON="git restore <path> discards uncommitted changes"
fi

# Default-branch guard. Checked after the chain above so a force-push keeps its own,
# more specific reason. Prose in guardrails could not guarantee this; a hook can.
# Fails open, like everything here except guard-secret-commit.sh: if git cannot name
# the current or default branch, we do not block.
if [ -z "$REASON" ] &&
  printf '%s' "$CMD" |
    grep -Eq '(^|[;&|[:space:]])git([[:space:]]+-[^[:space:]]+)*[[:space:]]+(commit|push)([[:space:]]|$)'; then
  ROOT="${CURSOR_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-.}}"
  CURRENT=$(git -C "$ROOT" symbolic-ref --quiet --short HEAD 2>/dev/null || true)
  if [ -n "$CURRENT" ]; then
    DEFAULT=$(git -C "$ROOT" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null |
      sed 's|^origin/||' || true)
    [ -z "$DEFAULT" ] && DEFAULT=$(git -C "$ROOT" config --get init.defaultBranch 2>/dev/null || true)
    if [ -z "$DEFAULT" ]; then
      case "$CURRENT" in
        main | master) DEFAULT="$CURRENT" ;;
      esac
    fi
    if [ -n "$DEFAULT" ] && [ "$CURRENT" = "$DEFAULT" ]; then
      REASON="this commits or pushes directly to the default branch ($DEFAULT)"
    fi
  fi
fi

[ -z "$REASON" ] && allow

deny "Blocked: $REASON. Per .cursor/rules/core/guardrails.mdc and .claude/rules/core/guardrails.md, destructive/irreversible git operations must not run autonomously. Ask the user to confirm this exact command, and let them run it themselves if they approve."
