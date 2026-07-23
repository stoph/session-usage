# session-usage (Claude Code)

Log token usage into the open project and open HTML reports via the `session-usage` skill.

Independent of [`../cursor/`](../cursor/). Install only this if you use Claude Code.

**Install:** see the [root README](../README.md#claude-code-install).

Validate before sharing:

```bash
claude plugin validate /path/to/session-usage
claude plugin validate /path/to/session-usage/claude-code
```

## What you get

- Hooks: `SessionStart`, `Stop`, `SubagentStop`, `PreCompact`, `SessionEnd`
- Logs: `<project>/.claude/usage-logs/<session-id>.jsonl`
- Auto-refresh of `report.html` on each `Stop` / `SessionEnd`
- Skill to open/refresh the project report

Logging requires a project root. Logs stay under that project’s `.claude/usage-logs/`.

## Token source

Hook stdin usually has no token counts. On `Stop` / `SubagentStop`, the logger reads assistant `message.usage` from the transcript path in the hook payload and stores normalized totals for the reporter.

## Scripts

```bash
python3 scripts/project-report.py --open /path/to/project
```
