# session-usage (Claude Code)

Claude Code plugin: log token usage into the open project and open HTML reports via the `session-usage` skill.

Independent of the Cursor package in `../cursor/`. Install only this if you use Claude Code.

## Install (non-official)

Does not use Anthropic’s `claude-plugins-official` or `claude-plugins-community` catalogs. This repo is its own marketplace (see root `.claude-plugin/marketplace.json`).

### Marketplace from this repo (recommended)

```bash
claude plugin marketplace add stoph/session-usage
claude plugin install session-usage@session-usage
```

Or from a local checkout:

```bash
claude plugin marketplace add /path/to/session-usage
claude plugin install session-usage@session-usage
```

Then `/reload-plugins` or a new session.

Updates:

```bash
claude plugin update session-usage
```

Validate before sharing:

```bash
claude plugin validate /path/to/session-usage
claude plugin validate /path/to/session-usage/claude-code
```

### Local skills-dir (dev)

```bash
ln -sfn /path/to/session-usage/claude-code ~/.claude/skills/session-usage
```

New session or `/reload-plugins`. Updates: `git pull` in the clone.

## What you get

- Hooks: `SessionStart`, `Stop`, `SubagentStop`, `PreCompact`, `SessionEnd`
- Logs: `<project>/.claude/usage-logs/<session-id>.jsonl`
- Auto-refresh of `report.html` on each `Stop` / `SessionEnd`
- Skill to open/refresh the project report

No project root → nothing is logged.

## Token source

Hook stdin usually has no token counts. On `Stop` / `SubagentStop`, the logger reads assistant `message.usage` from the transcript path in the hook payload and stores normalized totals for the reporter.

## Manual report

```bash
python3 scripts/project-report.py --open /path/to/project
```
