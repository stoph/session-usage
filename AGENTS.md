# Agent Guide — session-usage

Two independent plugins in one git repo. **Never** share runtime, log dirs, or a common library between Cursor and Claude Code. Improve each package on its own; duplicate reporter scripts on purpose.

## Layout

| Path | Role |
| --- | --- |
| `cursor/` | Cursor plugin (`.cursor-plugin/`, `hooks/`, `scripts/`, `skills/`) |
| `claude-code/` | Claude Code plugin (`.claude-plugin/`, `hooks/`, `scripts/`, `skills/`) |
| `.cursor-plugin/marketplace.json` | Cursor multi-plugin manifest (`source: cursor`) |
| `.claude-plugin/marketplace.json` | Claude marketplace (`source: ./claude-code`) |
| `docs/specs/session-usage.md` | Product rules |
| `README.md` | Install paths (individual vs team) |

## Hard rules

- **Project-only logs.** Cursor → `<workspace>/.cursor/usage-logs/`. Claude → `<project>/.claude/usage-logs/`. No workspace/project root → do not write. **No** `~/.cursor/hooks/logs` (or any user-home JSONL fallback).
- **Do not install onto the user’s machine** (no `~/.cursor/plugins/local` copies or `~/.claude/skills` symlinks) unless they explicitly ask.
- **Do not invent token numbers.** Reports come from `project-report.py` / `summarize.py` only. HTML is self-contained (embedded JSON); do not hand-author `report.html`.
- Display columns: **Input** (`fresh_tokens`), **Cache write**, **Cache read**, **Prompt total** (`input_tokens`), **Output**. Cost math uses the four priced lines, not Prompt total twice.

## Where to edit

| Change | Cursor | Claude Code |
| --- | --- | --- |
| Hook events / command | `cursor/hooks/hooks.json` | `claude-code/hooks/hooks.json` |
| Logger | `cursor/scripts/log-usage.py` | `claude-code/scripts/log-usage.py` |
| HTML report | `cursor/scripts/project-report.py` | `claude-code/scripts/project-report.py` |
| Session JSON summary | `cursor/scripts/summarize.py` | `claude-code/scripts/summarize.py` |
| Skill UX | `cursor/skills/session-usage/SKILL.md` | `claude-code/skills/session-usage/SKILL.md` |
| Manifest | `cursor/.cursor-plugin/plugin.json` | `claude-code/.claude-plugin/plugin.json` |

Cursor hooks use `${CURSOR_PLUGIN_ROOT}/scripts/log-usage.py` (cwd can be the project root on some events). Claude hooks use `${CLAUDE_PLUGIN_ROOT}/scripts/log-usage.py` and must keep the nested `hooks` → `hooks` → `{type:command}` shape.

## Token sources

- **Cursor:** token fields on hook payloads (especially `stop`) when present; log them as-is into project JSONL.
- **Claude:** hooks usually omit usage. On `Stop` / `SubagentStop`, parse assistant `message.usage` from `transcript_path` / `agent_transcript_path`. Normalize: `input_tokens` = fresh + cache_creation + cache_read; `cache_write_tokens` = `cache_creation_input_tokens`; `cache_read_tokens` = `cache_read_input_tokens`.

## Install truth (do not confuse these)

- **Cursor individuals:** real copy of `cursor/` into `~/.cursor/plugins/local/session-usage` (Cursor rejects symlinks that point outside that directory). No personal git-marketplace import.
- **Cursor Teams/Enterprise:** Team Marketplace import of this GitHub repo.
- **Cursor public:** `cursor.com/marketplace/publish` (review).
- **Claude anyone:** `claude plugin marketplace add <repo-or-path>` then `claude plugin install session-usage@session-usage`. Validate with `claude plugin validate`.

Full commands: root `README.md`.

## Validation

```bash
claude plugin validate .
claude plugin validate ./claude-code
python3 -m py_compile cursor/scripts/*.py claude-code/scripts/*.py
```

## Known pitfalls

- Claude first `Stop` on a long existing transcript can attribute full history to one turn (delta from empty state).
- Claude `SessionEnd` timeouts are tight; HTML refresh also runs on `Stop`.
