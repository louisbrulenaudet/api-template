@AGENTS.md

## Claude Code

- Hook scripts are canonical in `hooks/`; wire new hooks in `.claude/settings.json` and mirror in `.cursor/hooks.json` when Cursor supports the same event (Cursor: `beforeShellExecution` / `beforeReadFile` / `afterFileEdit`; Claude: `PreToolUse` / `PostToolUse`). Secret file reads are denied in Claude via `permissions.deny` and in Cursor via `hooks/security/guard-secret-read.sh`.
- Debug instruction loading with `tail -f hooks/logs/instructions-loaded.log` (InstructionsLoaded → `hooks/logging/instructions-loaded.sh`).
