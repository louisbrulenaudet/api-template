@AGENTS.md

## Claude Code

- Hook scripts are canonical in `hooks/`; wire new hooks in `.claude/settings.json` and mirror in `.cursor/hooks.json` only when Cursor has the same event. Claude's `Stop`, `ConfigChange`, `SessionStart` and pre-edit `PreToolUse` hooks have **no** Cursor counterpart.
- Claude handlers use **exec form** (`"command": "sh"` + `"args": ["${CLAUDE_PROJECT_DIR}/hooks/…"]`). Keep it that way: no shell, arguments verbatim, placeholder needs no quoting.
- **Exit 2 is the only blocking exit code.** Exit 1 is a non-blocking error and the action still runs. On exit 2 Claude reads **stderr** and discards stdout, so every block reason must reach stderr.
- Secret paths are protected primarily by `permissions.deny` - `Read(...)` **and** `Edit(...)`. `Edit(path)` rules cover Write and NotebookEdit too; a `Write(path)` rule is accepted but never matched and warns at startup, so never write one. `hooks/security/guard-protected-path.sh` backs this up with the `*.template` / `*.example` allowlist that rules cannot express.
- `hooks/git/guard-secret-commit.sh` **fails closed** - it refuses when it cannot complete. Every other hook here fails open on purpose.
- Bash commands and configuration changes are recorded to `~/.claude/audit/api-template/<date>.jsonl`, outside the repo, with credential-looking values redacted.
- `hooks/logs/**` is in `permissions.deny`, so `tail -f hooks/logs/…` is a **human** workflow - you cannot read those logs yourself, by design.
