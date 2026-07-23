# Session Usage

Per-project agent usage logging and reports.

Two independent packages (no shared runtime or log pipeline):

| Path | Product | Log dir |
| --- | --- | --- |
| [`cursor/`](cursor/) | Cursor plugin | `<project>/.cursor/usage-logs/` |
| [`claude-code/`](claude-code/) | Claude Code plugin | `<project>/.claude/usage-logs/` |

Install one or both.

## Cursor install

Individuals have no personal “import this git repo as a marketplace” path. Use a local plugin, Teams/Enterprise marketplace, or the [public Marketplace](https://cursor.com/marketplace/publish).

### Individuals (local plugin)

```bash
git clone https://github.com/stoph/session-usage.git
mkdir -p ~/.cursor/plugins/local
rm -rf ~/.cursor/plugins/local/session-usage
cp -R /path/to/session-usage/cursor ~/.cursor/plugins/local/session-usage
```

Fully quit and reopen Cursor (or Developer: Reload Window). Confirm under **Customize**, run an agent turn, then `/session-usage`.

Updates: `git pull`, re-copy `cursor/` into `~/.cursor/plugins/local/session-usage`, reload.

### Teams / Enterprise

1. **Dashboard → Plugins → Team Marketplaces → Add Marketplace → Import from Repo**
2. Add `session-usage` (source: `cursor/`)
3. Install from **Customize**
4. Optional: **Auto Refresh** (Cursor GitHub App) or manual **Refresh** after pushes

Package details: [cursor/README.md](cursor/README.md).

## Claude Code install

This repo is its own marketplace (not Anthropic official/community catalogs).

```bash
claude plugin marketplace add stoph/session-usage
claude plugin install session-usage@session-usage
```

Or from a local checkout: `claude plugin marketplace add /path/to/session-usage`, then the same install command.

`/reload-plugins` or a new session. Updates: `claude plugin update session-usage`.

Dev alternative: `ln -sfn /path/to/session-usage/claude-code ~/.claude/skills/session-usage`.

Package details: [claude-code/README.md](claude-code/README.md).

## Spec

[docs/specs/session-usage.md](docs/specs/session-usage.md)

## License

[MIT](LICENSE)
