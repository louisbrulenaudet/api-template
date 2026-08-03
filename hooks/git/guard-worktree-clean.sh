#!/usr/bin/env sh
# Purpose: Refuse to end the turn while secret-looking files sit loose in the working tree.
# Event:   Claude Code Stop. Wired from .claude/settings.json.
# Canonical location: hooks/git/ - Claude Code only (Cursor has no equivalent event).
#
# Contract:
#   stdin  - hook JSON: stop_hook_active, cwd, session_id
#   stdout - SILENT. Stop stdout is not injected into context.
#   stderr - the offending paths and what to do about them; fed back to Claude on exit 2.
#   exit   - 2 prevents Claude from stopping and continues the turn; 0 lets it stop.
#
# MUST yield when stop_hook_active is true. Claude Code overrides a Stop hook after it blocks
# eight times in a row (CLAUDE_CODE_STOP_HOOK_BLOCK_CAP, default 8); without this check the
# hook would spin to the cap and end the turn with a warning instead of a clean result.
#
# Scope is deliberately narrow: only untracked or modified paths that look like secrets or key
# material. Blocking on *any* untracked file would fire constantly and be worked around.
# Files already covered by .gitignore never appear in `git status --porcelain`, so this
# catches exactly the dangerous case - a secret that is NOT ignored and could be committed.

set -u

INPUT=$(cat 2>/dev/null || true)

if command -v jq >/dev/null 2>&1; then
  ACTIVE=$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo false)
else
  ACTIVE=$(printf '%s' "$INPUT" | grep -q '"stop_hook_active"[[:space:]]*:[[:space:]]*true' && echo true || echo false)
fi

# Already asked Claude to continue once - do not loop toward the block cap.
[ "$ACTIVE" = "true" ] && exit 0

ROOT="${CLAUDE_PROJECT_DIR:-${CURSOR_PROJECT_DIR:-$PWD}}"

command -v git >/dev/null 2>&1 || exit 0
git -C "$ROOT" --no-optional-locks rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

SECRET_RE='(^|/)(\.env(\..*)?|.*\.pem|.*\.key|.*\.p12|.*\.pfx|.*\.keystore|id_rsa|id_ed25519|credentials(\..*)?|\.pypirc|\.netrc|\.dev\.vars|\.prod\.vars|\.staging\.vars)$'

OFFENDERS=$(git -C "$ROOT" --no-optional-locks status --porcelain 2>/dev/null \
  | sed -E 's/^...//; s/^.* -> //; s/^"//; s/"$//' \
  | grep -vE '\.(template|example)$' \
  | grep -vE '\.example\.' \
  | grep -E "$SECRET_RE" \
  || true)

[ -z "$OFFENDERS" ] && exit 0

printf 'Working tree is not clean: secret-looking files are present and NOT git-ignored:\n' >&2
printf '%s\n' "$OFFENDERS" | sed 's/^/  - /' >&2
printf '\nThese would be committable. Before finishing: add them to .gitignore, move them out of\n' >&2
printf 'the repository, or confirm with the user that they are intentional and non-secret.\n' >&2
printf 'See .claude/rules/core/guardrails.md ("Never commit secrets").\n' >&2

exit 2
