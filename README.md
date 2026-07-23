# session-usage

Per-project agent usage logging and reports.

This repository contains **two independent packages**:

| Path | Product | Install if you use… |
| --- | --- | --- |
| [`cursor/`](cursor/) | Cursor plugin | Cursor |
| [`claude-code/`](claude-code/) | Claude Code plugin | Claude Code |

Install one or both. They do not share runtime, config, or log pipelines.

| | Cursor | Claude Code |
| --- | --- | --- |
| Log dir | `<project>/.cursor/usage-logs/` | `<project>/.claude/usage-logs/` |

## Cursor install

Cursor does **not** give individual accounts a “add this git repo as a marketplace” path. That exists only for Teams/Enterprise. Individuals use a local plugin (documented by Cursor), or submit to the public Marketplace.

### Individuals (local plugin)

This is the supported way to run a plugin that is not on the public Cursor Marketplace.

```bash
git clone https://github.com/stoph/session-usage.git
# or use an existing checkout
mkdir -p ~/.cursor/plugins/local
rm -rf ~/.cursor/plugins/local/session-usage
cp -R /path/to/session-usage/cursor ~/.cursor/plugins/local/session-usage
```

Cursor rejects symlinks whose target is outside `~/.cursor/plugins/local/`. Use a real copy.

1. Fully quit and reopen Cursor (or Developer: Reload Window).
2. Confirm the plugin appears under **Customize**.
3. Run an agent turn in a project → `<project>/.cursor/usage-logs/`.
4. `/session-usage` to open the report.

Updates: `git pull` in the clone, then re-copy `cursor/` into `~/.cursor/plugins/local/session-usage` and reload Cursor.

Public distribution for strangers: [cursor.com/marketplace/publish](https://cursor.com/marketplace/publish) (manual review).

### Teams / Enterprise (Team Marketplace)

Requires a Cursor Teams or Enterprise plan.

1. Push this repo to GitHub.
2. **Dashboard → Plugins → Team Marketplaces → Add Marketplace → Import from Repo**.
3. Import the repo; add the `session-usage` plugin (source: `cursor/`).
4. Teammates install from **Customize**.
5. Optional: enable **Auto Refresh** (Cursor GitHub App on the repo), or click **Refresh** after pushes.

Details: [cursor/README.md](cursor/README.md).

## Claude Code install

Individuals can add this repo as a marketplace. No Anthropic community/official listing required.

### Marketplace from this repo (recommended)

```bash
# from GitHub
claude plugin marketplace add stoph/session-usage
claude plugin install session-usage@session-usage

# or from a local checkout
claude plugin marketplace add /path/to/session-usage
claude plugin install session-usage@session-usage
```

Then `/reload-plugins` or a new session. Updates: `claude plugin update session-usage`.

### Local skills-dir (dev)

```bash
ln -sfn /path/to/session-usage/claude-code ~/.claude/skills/session-usage
```

New session or `/reload-plugins`. Updates: `git pull` in the clone.

Details: [claude-code/README.md](claude-code/README.md).

## Spec

[docs/specs/session-usage.md](docs/specs/session-usage.md)
