---
name: session-usage
description: >-
  Show Cursor agent token usage from local hook logs. Project-wide report is
  script-generated HTML (all sessions). Single-session view can use a canvas.
  Use when the user asks for session usage, project usage, token usage, cache
  reads, usage report, usage canvas, or to open/show `.cursor/usage-logs`.
---

# Session Usage

Local hook logs power usage reporting. Prefer **scripts** over agent-authored markup so refreshes cost almost no tokens.

## Model preference

When the user only wants usage opened or refreshed, a small/fast model is enough (composer-2.5 or composer-2.5-fast). Skills cannot switch models; if the chat is already on a large model, still do the script-only path (do not generate HTML/canvas by hand).

## Data source

| Path | Contents |
| --- | --- |
| `<workspace>/.cursor/usage-logs/<session-id>.jsonl` | Session events |
| `<workspace>/.cursor/usage-logs/report.html` | Self-contained HTML report |
| `<workspace>/.cursor/usage-logs/report-data.json` | Sidecar for scripts |

No workspace → hooks do not log. There is no user-home log fallback.

`stop` events may include `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`. Display labels match pricing: **Input** (uncached prompt, from `fresh_tokens`), **Cache write**, **Cache read**, **Prompt total** (`input_tokens`), **Output**. Models are attributed only from `stop` events. `by_model` has per-model totals and share %.

Hooks auto-regenerate `report.html` on each `stop` and `sessionEnd` (zero LLM tokens).

## Resolve report scripts

Scripts ship inside this Cursor plugin (`scripts/` next to `skills/`). Resolve the plugin root, then run scripts from `<plugin-root>/scripts/`.

Try, in order:

1. `~/.cursor/plugins/local/session-usage/scripts/project-report.py` (local install)
2. Any installed plugin path whose directory contains `.cursor-plugin/plugin.json` with `"name": "session-usage"` and `scripts/project-report.py`
3. If this repo is open as the workspace: `cursor/scripts/project-report.py`

## Choose the surface

| User intent | Do this |
| --- | --- |
| Project / all-time / all sessions | **HTML report** (default) |
| One session / this chat / named session id | **Canvas** (optional) or point at that session in the HTML |
| Raw numbers only | Run summarize / project-report and print paths |

Never dump JSONL in chat.

## Project report (default)

1. Refresh (always safe; cheap):

```bash
python3 <plugin-root>/scripts/project-report.py --open
# or with explicit project root:
python3 <plugin-root>/scripts/project-report.py --open /path/to/project
```

2. Reply with:
   - Path to `report.html` as a markdown link/file path
   - One-line summary from stdout/`report-data.json`: session count, turns, input, cache %, output
   - Do **not** rewrite the HTML yourself

If the report is missing and the script finds no logs, say hooks have not logged yet and point at `.cursor/usage-logs/`.

## Single-session canvas (optional)

Only when the user wants a canvas for one session:

1. Summarize:

```bash
python3 <plugin-root>/scripts/summarize.py --latest
# or a specific jsonl path
```

2. Read `~/.cursor/skills-cursor/canvas/SKILL.md` and write:

`/Users/<user>/.cursor/projects/<workspace-slug>/canvases/session-usage.canvas.tsx`

Embed summarize JSON inline (session totals only; do not plot every turn). Import only from `cursor/canvas`. Layout: header, stats, **prompt breakdown** rows matching the HTML report (Input / Cache write / Cache read / Prompt total / Output — one bar row each with %). No per-turn charts. No inventing labels like "Fresh". Point to HTML for per-turn tables.

3. Short chat summary + link to the canvas.

## Rules

- Never invent token numbers. Only use script output.
- Do not hand-author or LLM-regenerate `report.html`.
- Prefer overwriting `session-usage.canvas.tsx` for latest single-session views.
- Fail clearly if no logs exist.
