#!/usr/bin/env sh
# Purpose: Refuse any SQL statement that is not read-only.
# Event:   Claude Code PreToolUse, wired from the `db-reader` subagent's frontmatter
#          (matcher: the database MCP server's query tool), NOT from .claude/settings.json.
# Canonical location: hooks/security/
#
# Contract:
#   stdin  - hook JSON: tool_input.{sql,query,statement,command}
#   stdout - SILENT. PreToolUse stdout is not injected, and exit 2 discards it anyway.
#   stderr - actionable reason, fed back to Claude as the block reason.
#   exit   - 2 blocks the call, 0 allows. Exit 2 is the ONLY blocking code; exit 1 would NOT block.
#
# Failure posture: FAILS CLOSED, like git/guard-secret-commit.sh. A write executed against a
# database is unrecoverable, so a guard that cannot read the statement refuses rather than guesses.
# This is the opposite of guard-protected-path.sh, which backs up authoritative deny rules and can
# afford to fail open.
#
# This hook is defence in depth, NOT the primary control. The primary control is a database role
# with no write privilege. `tools` cannot constrain an MCP tool's arguments, and a subagent's
# permissionMode is inert whenever the parent session runs acceptEdits - so a PreToolUse hook
# exiting 2 is the only mechanism that binds here (it stops the call before permission rules are
# even evaluated). Do not treat it as sufficient on its own.

set -u

INPUT=$(cat 2>/dev/null || true)

deny() {
  printf 'Blocked: %s\n' "$1" >&2
  printf 'db-reader is read-only: SELECT, EXPLAIN, SHOW and DESCRIBE only.\n' >&2
  printf 'Do not rephrase to get around this - report that the operation is not permitted.\n' >&2
  exit 2
}

[ -z "$INPUT" ] && deny "the guard received no hook input, so the statement could not be checked"

if command -v jq >/dev/null 2>&1; then
  SQL=$(printf '%s' "$INPUT" | jq -r '
    .tool_input.sql // .tool_input.query // .tool_input.statement
    // .tool_input.command // empty' 2>/dev/null || true)
else
  SQL=$(printf '%s' "$INPUT" \
    | sed -n 's/.*"\(sql\|query\|statement\|command\)"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\2/p' 2>/dev/null \
    | head -1 || true)
fi

[ -z "$SQL" ] && deny "no SQL statement found in the tool input, so it could not be checked"

# Normalise: collapse whitespace, strip -- and /* */ comments, lowercase. Comment stripping matters
# because `/*x*/DELETE` and `--\nDROP` would otherwise slip past a naive prefix check.
NORM=$(printf '%s' "$SQL" \
  | sed -e 's,/\*[^*]*\*/, ,g' -e 's,--[^\n]*, ,g' \
  | tr '\n\r\t' '   ' \
  | tr -s ' ' \
  | sed -e 's/^ *//' -e 's/ *$//' \
  | tr '[:upper:]' '[:lower:]')

[ -z "$NORM" ] && deny "the statement was empty once comments were stripped"

# Reject write and DDL verbs anywhere in the statement, not only at the start: a CTE or a subquery
# can carry them (`with x as (delete from t returning *) select * from x`).
printf '%s' "$NORM" | grep -Eq '(^|[^a-z_])(insert|update|delete|drop|alter|truncate|create|replace|grant|revoke|merge|upsert|copy|call|do|vacuum|reindex|refresh|lock|set|begin|commit|rollback|savepoint|attach|detach|pragma|load_extension)([^a-z_]|$)' \
  && deny "the statement contains a write, DDL, or session-control keyword"

# Postgres/MySQL escapes to the filesystem or shell.
printf '%s' "$NORM" | grep -Eq '(^|[^a-z_])(pg_read_file|pg_ls_dir|pg_read_binary_file|lo_import|lo_export|load_file|outfile|dumpfile|system)([^a-z_]|$)' \
  && deny "the statement uses a filesystem or shell escape function"

# Statement stacking: one trailing semicolon is fine, an inner one is not.
STRIPPED=$(printf '%s' "$NORM" | sed 's/;[[:space:]]*$//')
case "$STRIPPED" in
  *';'*) deny "the statement stacks more than one command" ;;
esac

# Allowlist the opening verb. Everything not explicitly read-only is refused.
case "$STRIPPED" in
  select\ *|with\ *|explain\ *|show\ *|describe\ *|desc\ *|table\ *|values\ *) ;;
  *) deny "the statement does not begin with a read-only verb" ;;
esac

exit 0
