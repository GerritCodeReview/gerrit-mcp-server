---
name: setup
description: Interactive setup for gerrit_mcp_server configuration. Creates or updates gerrit_config.json with Gerrit host URLs and authentication details.
disable-model-invocation: true
argument-hint: [gerrit-url]
---

Help the user create or update their Gerrit MCP Server configuration.

## Build check

Before touching the config, verify the server environment and config state by
running:

```
UV_PROJECT_ENVIRONMENT="${CLAUDE_PLUGIN_DATA}/.venv" uv run --directory "${CLAUDE_PLUGIN_ROOT}" gerrit-check-config
```

Interpret the result as follows:

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

The config file is `gerrit_mcp_server/gerrit_config.json` relative to the repo
root. Check whether it already exists before proceeding.

## What to do

**If the config already exists**, read it, show the current hosts, and ask the
user what they want to change: add a host, modify a host, remove a host, or
update the default URL. Apply the change and write the updated file.

**If the config does not exist**, guide the user through creating it:

1. Ask for their primary Gerrit instance URL (or use `$ARGUMENTS` if a URL was
   provided).
2. Ask which authentication method they use for that host — present the three
   options below.
3. Collect the additional fields required by the chosen method.
4. Ask if they have more Gerrit hosts to add; repeat steps 2–3 for each.
5. Set `default_gerrit_base_url` to the first host's URL.
6. Write the complete JSON to `gerrit_mcp_server/gerrit_config.json` and confirm
   success.

## Authentication methods

**`git_cookies`** — recommended when you already push to Gerrit via `git` over
HTTP. Uses your `.gitcookies` file. Go to Gerrit → Settings → HTTP Credentials
to generate or refresh it.

```json
{"type": "git_cookies", "gitcookies_path": "~/.gitcookies"}
```

**`gob_curl`** — Google internal only. `gob-curl` handles auth automatically; no
extra fields needed.

```json
{"type": "gob_curl"}
```

**`http_basic`** — username and HTTP password token. Generate the token in
Gerrit → Settings → HTTP Credentials → "Obtain Password". Not recommended for
storing plaintext credentials, but supported.

```json
{"type": "http_basic", "username": "YOUR_USERNAME", "auth_token": "YOUR_HTTP_TOKEN"}
```

## Config schema

```json
{
  "default_gerrit_base_url": "https://primary-gerrit.example.com/",
  "gerrit_hosts": [
    {
      "name": "Human-readable label",
      "external_url": "https://gerrit.example.com/",
      "internal_url": "https://gerrit.internal.example.com/",
      "authentication": {}
    }
  ]
}
```

`internal_url` is optional. When present, the server recognises both URLs as the
same host, which is useful if you access the same instance via both an internal
and external address.
