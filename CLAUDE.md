@AGENTS.md

## Claude Code

- Prefer plan mode for multi-file or ambiguous changes; implement only after the plan is clear.
- Path rules under `.claude/rules/` load when you read a matching file - follow them over generic advice. `core/guardrails.md` is the only always-on rule.
- **Delegate** work whose output you will not re-read: library docs → `docs-researcher`, pytest → `test-runner`, Ruff + ty → `ci-verifier`, rule conformance on a diff → `code-reviewer`, auth/secrets/config/harness → `security-reviewer`, repo-wide mechanical edits → `refactorer`. Stay in the **main thread** for edits you already understand, anything sequential, and anything sharing state with work in progress - a subagent starts with no conversation history, so re-explaining can cost more than it saves. Use a **bundled skill** where one already fits: `/code-review` (semantic bugs), `/verify` (behaviour), `/simplify` (cleanup). Never let a subagent's summary stand in for reading the diff.
- Subagent privilege comes from `tools` **only**: `permissionMode` in agent frontmatter is inert here because the project `defaultMode` is `acceptEdits`, which a subagent cannot tighten. Auto memory, conversation history and output style do not reach a subagent either, so durable facts belong in `AGENTS.md` or `.claude/rules/`, never only in a memory note. Both reviewers are read-only and have no `Bash`: write the diff to a path **outside** the repo (`$TMPDIR`) and pass it.
- Finish with `make ci` (Ruff + ty); `make test` for pytest. Never paper over a failure.
- Hooks live in `hooks/` and are wired in `.claude/settings.json`. **Exit 2 is the only blocking exit code and the reason must go to stderr** - any other code fails open silently. Details when you edit them: `hooks/CLAUDE.md`.
- Always use Context7 (MCP / plugin) for library, framework, SDK, API, or CLI documentation - even for well-known stacks - without waiting to be asked.
