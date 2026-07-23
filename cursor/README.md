# session-usage (Cursor)

Log agent token usage into the open project and open HTML reports via `/session-usage`.

**Install:** see the [root README](../README.md#cursor-install).

## What you get

- Hooks writing `<workspace>/.cursor/usage-logs/<session-id>.jsonl`
- Auto-refresh of `report.html` on each agent turn
- Skill `/session-usage` to open/refresh the project report

Logging requires a workspace root. Logs stay under that project’s `.cursor/usage-logs/`.

## Scripts

From this `cursor/` directory (or the installed plugin copy):

```bash
# Project HTML report (also used by /session-usage)
python3 scripts/project-report.py --open /path/to/project

# Plaintext session list / report (CLI / CI)
python3 scripts/report-usage.py --project /path/to/project
python3 scripts/report-usage.py --project /path/to/project --latest
python3 scripts/report-usage.py --project /path/to/project <session_id>
```

`project-report.py` writes `report.html` and `report-data.json`.  
`report-usage.py` lists sessions and prints a text report from project JSONL (optional `--rebuild`).
