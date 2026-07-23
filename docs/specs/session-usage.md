# Session Usage

Track agent token usage per project and open HTML (or canvas) reports. Cursor and Claude Code are independent products with independent installs. This repo holds both packages side by side; runtime is never shared.

## Layout

```text
session-usage/
  cursor/           # Cursor plugin
  claude-code/      # Claude Code package (separate install)
  docs/specs/       # Product specs
```

One git repository. Two distributables. Install only what you use.

## Logging rules

- Cursor logs: `<workspace>/.cursor/usage-logs/`
- Claude Code logs: `<project>/.claude/usage-logs/`
- No project/workspace root → do not log.
- Session JSONL is written only under the project log dir above.
- Report HTML is self-contained (embedded JSON). Sidecar `report-data.json` is optional for scripts.

## Cursor package (`cursor/`)

Cursor plugin bundling:

- Hooks: `sessionStart`, `stop`, `subagentStart`, `subagentStop`, `preCompact`, `sessionEnd`
- Scripts: `log-usage.py`, `project-report.py`, `summarize.py`, `report-usage.py`
- Skill: `session-usage` (`/session-usage`) for refreshing/opening reports

Install: Cursor Marketplace / Customize, or a real copy of `cursor/` into `~/.cursor/plugins/local/session-usage`.

## Claude Code package (`claude-code/`)

Independent Claude Code plugin:

- Hooks: `SessionStart`, `Stop`, `SubagentStop`, `PreCompact`, `SessionEnd`
- Scripts: `log-usage.py` (transcript-derived tokens), `project-report.py`, `summarize.py`
- Skill: `session-usage`
- Install: skills-dir symlink under `~/.claude/skills/session-usage`, or marketplace entry in `.claude-plugin/marketplace.json`

Token source: Claude hook payloads generally omit usage; the logger reads assistant `message.usage` from `transcript_path` / `agent_transcript_path` and normalizes to the reporter’s Input / Cache write / Cache read / Output columns.

## Non-goals

- Shared runtime library between Cursor and Claude Code
- Cross-tool log aggregation
- Billing/pricing inside the reporter (display token columns only)
