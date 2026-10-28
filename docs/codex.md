# Codex Configuration

This repository includes a portable Agent Plugin package for
[OpenAI Codex](https://developers.openai.com/codex). The package exposes the
same MCP server and shared skills used by the Claude Code plugin.

## Plugin Package

The portable package is defined by two files at the repository root:

- `plugin.json`: the portable plugin manifest.
- `mcp.json`: the Codex MCP configuration. It starts the server on demand with
  `uv`, uses `${PLUGIN_ROOT}` for the installed plugin directory, stores the
  virtual environment below `${PLUGIN_DATA}`, and uses the shared user config
  location unless `GERRIT_CONFIG_PATH` is explicitly set.

The Codex-specific `.codex-plugin/plugin.json` overlays `env_vars` for the
portable MCP server, forwarding `GERRIT_CONFIG_PATH` and `XDG_CONFIG_HOME` from
the Codex process. This preserves explicit overrides and custom XDG config
directories without setting defaults for either variable. The portable
`mcp.json` remains the source of the server command, arguments, and virtual
environment; it does not support Codex's `env_vars` field directly.

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

The setup skill is explicit-only. Invoke it as `$gerrit:setup` in Codex. It
creates or repairs the [shared user config file](configuration.md), outside the
plugin installation and data directories. Claude Code and Codex use
`platformdirs.user_config_path("gerrit-mcp") / "gerrit_config.json"` by default;
a nonempty `GERRIT_CONFIG_PATH` overrides it. The manifest does not set that
override. Move an existing plugin-data config to the shared location or select
it explicitly with `GERRIT_CONFIG_PATH`; no credentials are copied
automatically. The setup skill supports the same authentication methods as the
Claude Code setup flow.

The root `plugin.json` declares `hooks/hooks.json` through
`extensions.com.openai.hooks`, so supported Codex versions can run the
`SessionStart` configuration hook. Review and trust the plugin hook in `/hooks`
after installation. Codex CLI 0.155.1 ignored plugin-bundled `SessionStart`
hooks even with this declaration (openai/codex#39895); upgrade Codex rather than
removing `plugin.json`. Removing it leaves `${CLAUDE_PLUGIN_ROOT}` unexpanded in
`.mcp.json`, and the MCP server cannot start. Run `$gerrit:setup` to create or
repair the configuration; MCP startup success or failure is the authoritative
validation.

The hook accepts `PLUGIN_ROOT` and `PLUGIN_DATA` as well as the
Claude-compatible names. Plugin hooks must be reviewed and trusted before Codex
runs them.

## Testing

Run the package and hook tests without launching Codex:

```bash
uv run pytest tests/integration/test_plugin_package.py
```

For the manual Codex client smoke test and the full test commands, see the
[Testing Guide](testing.md).
