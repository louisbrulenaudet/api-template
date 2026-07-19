@AGENTS.md

## Claude Code

- Prefer plan mode for multi-file or ambiguous changes; implement only after the plan is clear.
- Path rules under `.claude/rules/` load when matching files are touched — follow them over generic advice.
- Use subagents for noisy work: `docs-researcher` (library docs), `test-runner` (pytest), `ci-verifier` (before PRs / after edit batches).
- Finish with `make ci` (Ruff + ty); use `test-runner` / `make test` for pytest. Never paper over Ruff/ty/pytest failures.
- Hooks live in `hooks/` and are wired in `.claude/settings.json` (git guards, Ruff on edit, InstructionsLoaded logging).
- Auto memory is enabled for this project; durable team conventions still belong in `AGENTS.md` or `.claude/rules/`, not only memory notes.
- Always use Context7 (MCP / plugin) for library, framework, SDK, API, or CLI documentation — even for well-known stacks — without waiting to be asked.
