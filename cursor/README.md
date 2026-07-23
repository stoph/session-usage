# session-usage (Cursor)

Cursor plugin: log agent token usage into the open project and open HTML reports via `/session-usage`.

## Install

Cursor has no personal “import this git repo as a marketplace” for individual accounts. Use a local plugin, or a Team Marketplace if you are on Teams/Enterprise. Public listing is a separate review process.

### Individuals (local plugin)

Documented Cursor path for loading a plugin that is not on the public Marketplace:

```bash
mkdir -p ~/.cursor/plugins/local
ln -sfn /path/to/session-usage/cursor ~/.cursor/plugins/local/session-usage
```

Fully quit and reopen Cursor (or Developer: Reload Window). Check **Customize**, run an agent turn, confirm `<project>/.cursor/usage-logs/`, then `/session-usage`.

Updates: `git pull` in the clone, then reload.

To publish for anyone: [cursor.com/marketplace/publish](https://cursor.com/marketplace/publish).

### Teams / Enterprise (Team Marketplace)

Requires Teams or Enterprise.

1. Push this repository to GitHub.
2. **Dashboard → Plugins → Team Marketplaces → Add Marketplace → Import from Repo**.
3. Add the `session-usage` plugin (source directory: `cursor/`, via the repo’s `.cursor-plugin/marketplace.json`).
4. Install from **Customize**.
5. Optional: **Auto Refresh** (Cursor GitHub App) or manual **Refresh** after pushes.

## What you get

- Hooks writing `<workspace>/.cursor/usage-logs/<session-id>.jsonl`
- Auto-refresh of `report.html` on each agent turn
- Skill `/session-usage` to open/refresh the project report

No workspace root → nothing is logged. No `~/.cursor` log fallback.

## Migrate from the old hook install

If `~/.cursor/hooks.json` still lists `./hooks/log-usage.py`, remove those usage entries (keep unrelated hooks). Otherwise every turn is logged twice.

You can delete obsolete copies under `~/.cursor/hooks/log-usage.py` and `~/.cursor/skills/session-usage/` after the plugin is working.

## Manual report

```bash
python3 scripts/project-report.py --open /path/to/project
```
