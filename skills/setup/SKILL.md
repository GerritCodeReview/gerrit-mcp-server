---
name: setup
description: Interactive setup for gerrit_mcp_server configuration. Creates or updates gerrit_config.json with Gerrit host URLs and authentication details.
disable-model-invocation: true
argument-hint: [gerrit-url]
---

Help the user create or update their Gerrit MCP Server configuration.

## Build check

Before touching the config, Claude Code can verify the server environment and
config state with:

```
UV_PROJECT_ENVIRONMENT="${CLAUDE_PLUGIN_DATA}/.venv" uv run --directory "${CLAUDE_PLUGIN_ROOT}" gerrit-check-config
```

Codex does not expose `PLUGIN_ROOT` or `PLUGIN_DATA` to Bash commands, so do not
run a separate Codex build check from this skill. Codex validates the MCP server
command and environment when it starts; treat an MCP startup failure as the
environment/configuration check and repair the setup as needed.

When invoked as a Claude Code skill, use `/gerrit:setup`. When invoked as a
Codex skill, use `$gerrit:setup`. Both forms are explicit-only and interactively
guide the user through the same configuration flow.

For the Claude Code check, interpret the result as follows:

- **`uv run` itself fails** (uv not found, env broken, package not installed):
  offer to run `./build-gerrit.sh` from the repo root. Do not proceed until it
  succeeds.
- **Exit 0**: config is already valid — skip to the "config already exists" flow
  and ask what the user wants to change.
- **Exit 1** (config file missing): proceed directly into the "create new
  config" flow.
- **Exit 2** (config invalid — bad JSON or `default_gerrit_base_url` mismatch):
  show the error output, then offer to fix the existing file in place
  (preserving valid entries where possible) rather than starting from scratch.

## Config file location

Both Claude Code and Codex use the same config location. Use the
`GERRIT_CONFIG_PATH` override when nonempty; otherwise resolve
`platformdirs.user_config_path("gerrit-mcp") / "gerrit_config.json"` as
described in `references/gerrit-config.md`. Check whether that file already
exists. Create its parent directory when needed. Do not write into the plugin
cache.

## What to do

**If the config already exists**, read it, show the current hosts, and ask the
user what they want to change: add a host, modify a host, remove a host, or
update the default URL. Apply the change and write the updated file.

**If the config does not exist**, guide the user through creating it:

1. Ask for their primary Gerrit instance URL (or use `$ARGUMENTS` if a URL was
   provided).
2. Ask which authentication method they use for that host — present the three
   options from `references/gerrit-config.md` (`git_cookies`, `gob_curl`,
   `http_basic`).
3. Collect the additional fields required by the chosen method.
4. Ask if they have more Gerrit hosts to add; repeat steps 2–3 for each.
5. Set `default_gerrit_base_url` to the first host's URL.
6. Write the complete JSON to the selected config path above and confirm
   success.

## Configuration details

See [gerrit config reference](references/gerrit-config.md) for the full
configuration reference: authentication methods (with example JSON snippets for
each), the config schema, the file location and `GERRIT_CONFIG_PATH` override,
and the optional `internal_url` field. Consult it when collecting fields and
assembling the file.
