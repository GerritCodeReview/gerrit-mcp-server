# Claude Code Configuration

You can use this MCP server with [Claude Code](https://claude.com/claude-code),
allowing you to interact with Gerrit directly from your terminal. This
repository ships as an installable **Claude Code plugin**.

## Claude Code Plugin

The plugin is defined by two files in the repository root:

- `.claude-plugin/plugin.json`: the plugin manifest (name and description)
  required by the Claude Code plugin system.

- `.mcp.json`: the MCP server configuration. It launches the server on-demand
  with `uv` and uses `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` so
  paths resolve correctly wherever the plugin is installed:

  ```json
  {
    "mcpServers": {
      "gerrit": {
        "command": "uv",
        "args": ["run", "--directory", "${CLAUDE_PLUGIN_ROOT}", "gerrit-mcp-server"],
        "env": {
          "UV_PROJECT_ENVIRONMENT": "${CLAUDE_PLUGIN_DATA}/.venv"
        }
      }
    }
  }
  ```

Load the plugin locally by pointing Claude Code at the project directory:

```bash
claude --plugin-dir <path-to-gerrit-mcp-server>
```

Because the server is launched with `uv run`, `uv` automatically creates the
environment at `${CLAUDE_PLUGIN_DATA}/.venv` and installs dependencies on first
launch. There is no need to run `./build-gerrit.sh` separately for the plugin.

The plugin starts the server on-demand, so no separate background process is
required. Once loaded, you can use the `gerrit` tools directly from `claude`.
