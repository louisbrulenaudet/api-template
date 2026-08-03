# Agent Hooks

Shared shell hooks for **Cursor** and **Claude Code**. Scripts live here; wiring stays in tool-specific config files.

These hooks run in the **AI agent loop** only. They do **not** replace human git hooks or CI.

## Layout

```
hooks/
├── git/
│   ├── guard-destructive-git.sh   # Block reset --hard, push --force, etc.
│   ├── guard-secret-commit.sh     # Block staging/committing secret files (FAILS CLOSED)
│   └── guard-worktree-clean.sh    # Stop: refuse to finish with loose secret files
├── security/
│   ├── guard-protected-path.sh    # Block writes to secret paths (Claude PreToolUse)
│   ├── guard-readonly-sql.sh      # Block non-read-only SQL (db-reader agent frontmatter) FAILS CLOSED
│   └── guard-secret-read.sh       # Block Agent/Tab reads of secrets (Cursor)
├── quality/
│   ├── check-changed.sh           # Sequential format-then-lint entry point
│   ├── format-changed.sh          # ruff format after Python edits (non-blocking)
│   └── lint-changed.sh            # ruff check after Python edits (exit 2 on errors)
├── logging/
│   ├── session-start.sh           # Cursor sessionStart + Claude SessionStart
│   ├── instructions-loaded.sh     # Claude Code InstructionsLoaded
│   ├── audit-bash.sh              # Append-only Bash audit trail
│   └── audit-config-change.sh     # Append-only config-mutation audit trail
├── logs/                          # Cursor/Claude debug output (git-ignored)
├── AGENTS.md                      # Agent guide (Cursor + nested AGENTS.md)
├── CLAUDE.md                      # Claude Code entry
└── README.md                      # This file
```

## Wiring

| Tool | Config file | Runs from |
|------|-------------|-----------|
| Cursor | [`.cursor/hooks.json`](../.cursor/hooks.json) | Project root |
| Claude Code | [`.claude/settings.json`](../.claude/settings.json) | Project root |

Claude Code handlers use **exec form** - `"command": "sh"` plus `"args": ["${CLAUDE_PROJECT_DIR}/hooks/…"]`. Exec form skips the shell entirely, so arguments pass verbatim and the path placeholder needs no quoting.

Scripts read JSON on **stdin** and accept both Claude (`tool_input.*`) and Cursor (flat `command` / `file_path`) shapes. The shared git/security guards also emit Cursor permission JSON on stdout; Claude Code discards stdout whenever a hook exits 2, so the same reason is always written to **stderr**, which is the stream Claude actually reads.

## When hooks run

| Event | Script | Blocks? | Behaviour |
|-------|--------|---------|-----------|
| `beforeShellExecution` (Cursor) / `PreToolUse` Bash (Claude) | `git/guard-secret-commit.sh` | **yes, exit 2** | Refuses commands that would stage/commit a secret. **Fails closed.** |
| `beforeShellExecution` (Cursor) / `PreToolUse` Bash (Claude) | `git/guard-destructive-git.sh` | **yes, exit 2** | Refuses `reset --hard`, `push --force`, `clean -f`, branch/tag deletion, … |
| `PreToolUse` Bash (Claude) | `logging/audit-bash.sh` | no | Appends one redacted JSON line per command to the audit log |
| `PreToolUse` Edit\|Write\|NotebookEdit\|MultiEdit (Claude) | `security/guard-protected-path.sh` | **yes, exit 2** | Refuses writes to `.env`, keys, credentials; allows `*.template` / `*.example` |
| `beforeReadFile` / `beforeTabFileRead` (Cursor) | `security/guard-secret-read.sh` | **yes, exit 2** | Refuses reads of `.env*`, keys, credentials |
| `PreToolUse` on the DB query tool (Claude, wired from the `db-reader` agent's own frontmatter, **not** `settings.json`) | `security/guard-readonly-sql.sh` | **yes, exit 2** | Refuses any statement that is not `SELECT` / `EXPLAIN` / `SHOW` / `DESCRIBE`, including write verbs hidden in a CTE, comment, or stacked statement. **Fails closed.** Inert until a `db` MCP server exists |
| `afterFileEdit` (Cursor) / `PostToolUse` Edit\|Write\|NotebookEdit (Claude) | `quality/check-changed.sh` | feedback only | Format, then lint the edited Python file |
| `Stop` (Claude) | `git/guard-worktree-clean.sh` | **yes, exit 2** | Refuses to end the turn while non-ignored secret-looking files are loose |
| `ConfigChange` (Claude) | `logging/audit-config-change.sh` | no | Records settings mutations; warns when `hooks`/`permissions` change |
| `sessionStart` (Cursor) / `SessionStart` (Claude) | `logging/session-start.sh` | no | Appends to `logs/session-start.log` |
| `InstructionsLoaded` (Claude, `async`) | `logging/instructions-loaded.sh` | no | Appends to `logs/instructions-loaded.log` |

Exit code **2** is the only blocking code - exit 1 is treated as a non-blocking error and the action proceeds. On `PostToolUse` even exit 2 only feeds the message back; it cannot roll back an edit that already ran. Cursor security guards set `failClosed: true`, so scripts always print `{"permission":"allow"}` on the allow path to avoid an empty-stdout block.

## Enforcement is layered

Hooks are the *second* line. Read/write protection for secret paths lives in `permissions.deny` in [`.claude/settings.json`](../.claude/settings.json), because deny rules are unconditionally authoritative - a hook returning `allow` can never loosen them, and they apply to Bash file commands (`cat`, `sed`, …) too. The hooks add what rules cannot express: parsed Bash arguments, a `*.template` allowlist, an actionable reason, and an audit trail.

## Audit log

`audit-bash.sh` and `audit-config-change.sh` write JSON Lines to `~/.claude/audit/<project>/<YYYY-MM-DD>.jsonl` (directory `0700`, files `0600`). Set `CLAUDE_AUDIT_DIR` to relocate it.

Deliberately **outside** the repository: `git clean -x` cannot delete it, worktree checkouts do not copy it, and it never appears in a diff the agent reads back. Values that look like credentials (`*KEY=`, `*TOKEN=`, `*SECRET=`, `*PASS*=`, `--password`, `--token`, `Authorization:`) are replaced with `<REDACTED>` before anything is written.

## Manual test (before wiring)

Run these from a shell, **not** through the agent: the git guards inspect the raw command string, so a test harness that quotes their own trigger patterns gets blocked by them.

```bash
# Protected paths - deny, then allow
printf '{"tool_input":{"file_path":"/x/.env"}}'          | sh hooks/security/guard-protected-path.sh; echo "exit=$?"
printf '{"tool_input":{"file_path":"/x/.env.template"}}' | sh hooks/security/guard-protected-path.sh; echo "exit=$?"

# Destructive git - deny, then allow
printf '{"tool_input":{"command":"git push --force"}}' | sh hooks/git/guard-destructive-git.sh; echo "exit=$?"
printf '{"tool_input":{"command":"git status"}}'       | sh hooks/git/guard-destructive-git.sh; echo "exit=$?"

# Stop guard must yield once it has already asked for a continuation
printf '{"stop_hook_active":true}' | sh hooks/git/guard-worktree-clean.sh; echo "exit=$?"

# Audit redaction - write somewhere disposable and inspect the line
printf '{"tool_input":{"command":"deploy API_KEY=sk-real"}}' \
  | CLAUDE_AUDIT_DIR=/tmp/audit-test sh hooks/logging/audit-bash.sh
cat /tmp/audit-test/*/*.jsonl

# Python quality (requires uv + ruff in the project env)
printf '{"file_path":"app/main.py"}' | sh hooks/quality/check-changed.sh
```

## Debugging

```bash
# Cursor session events / Claude session starts
tail -f hooks/logs/session-start.log

# Claude instruction loading
tail -f hooks/logs/instructions-loaded.log

# Bash and configuration audit trail
tail -f ~/.claude/audit/api-template/$(date -u +%F).jsonl

# Cursor hook output channel
# Customize → Hooks

# Claude Code
claude --debug     # hook stdout/stderr and exit codes
/hooks             # read-only browser of the effective hook set
```

`hooks/logs/**` is listed in `permissions.deny` → `Read(...)`, so these are a **human** debugging workflow: Claude itself cannot read them, by design, to keep noisy logs out of context.

## Adding a hook

1. Add the script under the right subfolder (`git/`, `security/`, `quality/`, `logging/`).
2. `chmod +x hooks/<category>/<script>.sh`
3. Register in [`.claude/settings.json`](../.claude/settings.json), and in [`.cursor/hooks.json`](../.cursor/hooks.json) when Cursor has an equivalent event. Several Claude events (`Stop`, `ConfigChange`, pre-edit) have no Cursor counterpart.
4. Update [AGENTS.md](AGENTS.md) and this README.

See [AGENTS.md](AGENTS.md) for authoring conventions and guardrail alignment.
