---
name: session-usage
description: >-
  Show Claude Code token usage from local hook logs. Project-wide report is
  script-generated HTML (all sessions). Use when the user asks for session
  usage, project usage, token usage, cache reads, usage report, or to
  open/show `.claude/usage-logs`.
---

# Session Usage (Claude Code)

Local hook logs power usage reporting. Prefer **scripts** over agent-authored markup so refreshes cost almost no tokens.

## Data source

| Path | Contents |
| --- | --- |
| `<project>/.claude/usage-logs/<session-id>.jsonl` | Session events |
| `<project>/.claude/usage-logs/report.html` | Self-contained HTML report |
| `<project>/.claude/usage-logs/report-data.json` | Sidecar for scripts |

No project root → hooks do not log. There is no user-home log fallback.

Claude Code hooks do not include token fields on most events. The logger reads assistant `usage` blocks from the session transcript and normalizes them to **Input** / **Cache write** / **Cache read** / **Prompt total** / **Output**.

## Resolve report scripts

Scripts ship in this plugin (`scripts/` next to `skills/`).

Try, in order:

1. `$CLAUDE_PLUGIN_ROOT/scripts/project-report.py` when set
2. `~/.claude/skills/session-usage/scripts/project-report.py` (skills-dir local install)
3. If this repo is the cwd: `claude-code/scripts/project-report.py`

## Project report (default)

```bash
python3 <plugin-root>/scripts/project-report.py --open
# or:
python3 <plugin-root>/scripts/project-report.py --open /path/to/project
```

Reply with the `report.html` path and a one-line summary from stdout/`report-data.json`. Do **not** rewrite the HTML yourself.

## Rules

- Never invent token numbers. Only use script output.
- Do not hand-author or LLM-regenerate `report.html`.
- Fail clearly if no logs exist.
