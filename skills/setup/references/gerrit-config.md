# Gerrit MCP Server Configuration Reference

Describes the `gerrit_config.json` file consumed by `gerrit_mcp_server`: where
it lives, the authentication methods it supports, and its full schema. Other
skills that read or write this config should rely on this reference rather than
duplicating the details.

## Config file location

Honor a nonempty `GERRIT_CONFIG_PATH` first. Otherwise use
`platformdirs.user_config_path("gerrit-mcp") / "gerrit_config.json"`:

- Linux: `${XDG_CONFIG_HOME:-~/.config}/gerrit-mcp/gerrit_config.json`.
- macOS: `~/Library/Application Support/gerrit-mcp/gerrit_config.json`.
- Windows: `%LOCALAPPDATA%\gerrit-mcp\gerrit_config.json`.

This location is outside the plugin installation and survives updates. A missing
or invalid override is reported without falling back to another file. Move an
existing repo-local config to this location, or keep using it by setting
`GERRIT_CONFIG_PATH`; credentials are not migrated automatically.

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
Gerrit → Settings → HTTP Credentials → "Obtain Password".

The preferred form omits the credentials from the config and lets `curl` read
them from a netrc file (keyed by host), so they aren't duplicated in
`gerrit_config.json`. Add a line to `~/.netrc` like
`machine gerrit.example.com login YOUR_USERNAME password YOUR_HTTP_TOKEN`, then
configure:

```json
{"type": "http_basic"}
```

Add an optional `"netrc_path"` to point at a non-default netrc file (maps to
`curl --netrc-file`).

Alternatively, store the credentials inline (both fields required):

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

`default_gerrit_base_url` should match one of the configured hosts' URLs;
conventionally it is set to the first host's URL.

`authentication` must be one of the [methods](#authentication-methods) listed
above.
