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

### Install from the marketplace

Register the Gerrit plugin marketplace and install the plugin:

```
/plugin marketplace add https://gerrit.googlesource.com/gerrit-mcp-server
/plugin install gerrit@gerrit-mcp
```

### Load locally

Load the plugin locally by pointing Claude Code at the project directory:

```bash
claude --plugin-dir <path-to-gerrit-mcp-server>
```

Because the server is launched with `uv run`, `uv` automatically creates the
environment at `${CLAUDE_PLUGIN_DATA}/.venv` and installs dependencies on first
launch. There is no need to run `./build-gerrit.sh` separately for the plugin.

The plugin starts the server on-demand, so no separate background process is
required. Once loaded, you can use the `gerrit` tools directly from `claude`.

## Prerequisites

Users must [configure](../README.md#3_configure-the-server) the server with the
`gerrit_config.json` file.

## Setup diagnostics

A `SessionStart` hook (`hooks/check-config.sh`, registered in
`hooks/hooks.json`) checks the server environment and configuration at the start
of every session, so a broken setup surfaces with clear guidance instead of MCP
tools failing silently.

The hook runs the `gerrit-check-config` console script, whose exit code reports
the setup state:

- `0`: config is valid — the hook stays quiet and reports that the tools are
  available.
- `1`: config file is missing — the normal first-run state. The hook asks the
  user to run `/gerrit:setup`.
- `2`: config is present but invalid (bad JSON or `default_gerrit_base_url`
  mismatch) — the hook asks the user to run `/gerrit:setup` to repair it.
- any other non-zero code: the Python environment is not built. The hook offers
  the exact `build-gerrit.sh` command to rebuild it.

The hook emits JSON with a `systemMessage` (shown to the user) and
`additionalContext` (telling the model what to do), because `SessionStart`
stdout goes to the model's context rather than the user's terminal.

## `/gerrit:setup` skill

`skills/setup/SKILL.md` provides an interactive `/gerrit:setup` skill that
guides the user through creating or updating
`gerrit_mcp_server/gerrit_config.json`. The exit-code 1 and 2 states above ask
the user to run it. See
[Interactive Setup](configuration.md#interactive-setup-gerritsetup) in the
configuration guide for details.

## `gerrit-workflow` skill

`skills/gerrit-workflow/SKILL.md` teaches the model how to drive the git side of
Gerrit Code Review — pushing for review via `refs/for/<branch>`, creating new
patch sets by amending without disturbing the `Change-Id` trailer, working with
dependent change stacks and topics, and diagnosing common push errors such as
`missing Change-Id in commit message footer` or `prohibited by Gerrit`.

Unlike `/gerrit:setup`, this skill is model-invocable: Claude Code activates it
automatically whenever a task involves Gerrit git operations, so you do not need
to invoke it by name. Two reference files ship alongside it:

- `references/gerrit-vs-github.md` — a side-by-side comparison of Gerrit and
  GitHub/GitLab workflows for common tasks.
- `references/change-id-details.md` — a deep dive on `Change-Id` creation,
  squashing, cherry-picks, and edge cases.
