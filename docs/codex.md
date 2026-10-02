# Codex Configuration

This repository includes a portable Agent Plugin package for
[OpenAI Codex](https://developers.openai.com/codex). The package exposes the
same MCP server and shared skills used by the Claude Code plugin.

## Plugin Package

The portable package is defined by two files at the repository root:

- `plugin.json`: the portable plugin manifest.
- `mcp.json`: the Codex MCP configuration. It starts the server on demand with
  `uv`, uses `${PLUGIN_ROOT}` for the installed plugin directory, and stores the
  virtual environment below `${PLUGIN_DATA}`.

The shared `skills/` directory is discovered automatically by the portable
plugin manifest. The Claude-specific `.claude-plugin/plugin.json` and
`.mcp.json` remain in place for Claude Code and are intentionally separate from
the portable files.

## Install Locally

Codex can use a local or Git-backed marketplace. For a local checkout, add the
repository or a marketplace containing the repository plugin:

```bash
codex plugin marketplace add <path-to-gerrit-mcp-server>
codex plugin list --available --json
codex plugin add gerrit@gerrit-mcp --json
```

Open a new Codex session after installation. Use `/plugins` to inspect installed
plugins and verify that the Gerrit tools are available.

## Setup

The setup skill is explicit-only. Invoke it as `$setup` in Codex. It creates or
repairs `gerrit_mcp_server/gerrit_config.json` and supports the same
authentication methods as the Claude Code setup flow.

The `SessionStart` configuration hook also runs locally when the plugin is
enabled. Codex exposes `PLUGIN_ROOT` and `PLUGIN_DATA`; the hook accepts those
variables as well as the Claude-compatible names. Plugin hooks must be reviewed
and trusted before Codex runs them.

## Testing

Run the package and hook tests without launching Codex:

```bash
uv run pytest tests/integration/test_plugin_package.py
```

For the manual Codex client smoke test and the full test commands, see the
[Testing Guide](testing.md).
