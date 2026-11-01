# Gerrit MCP Server Configuration (`gerrit_config.json`)

The `gerrit_mcp_server` is configured via a central JSON file located at
`gerrit_mcp_server/gerrit_config.json`. This file allows you to define
connection and authentication details for multiple Gerrit instances.

Set `GERRIT_CONFIG_PATH` to use another location, such as
`~/.config/gerrit_config.json`.

A sample file is provided at `gerrit_mcp_server/gerrit_config.sample.json` which
you can copy and customize.

## Interactive Setup (`/gerrit:setup`)

If your harness supports skills (tested with Claude Code), the `/gerrit:setup`
skill can create or repair `gerrit_config.json` for you interactively instead of
hand-editing the JSON. It prompts for each Gerrit host's URL and authentication
method, sets `default_gerrit_base_url`, and writes the file.

The skill is `disable-model-invocation`, so the model cannot run it on your
behalf — you must invoke `/gerrit:setup` yourself. It is written against the
[Agent Skills](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)
open standard, so it is also expected to work in Gemini CLI, OpenAI Codex, and
other compatible harnesses, though only Claude Code has been verified.

The rest of this document describes the config file in full, which is useful
whether you write it by hand or want to understand what the skill produces.

## Top-Level Configuration

The configuration file has two main properties at its root:

| Key                       | Type   | Description                                                                                                                                                   |
| ------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `default_gerrit_base_url` | string | The full URL of the Gerrit instance to use if a tool is called without a specific `gerrit_base_url` parameter.                                                |
| `gerrit_hosts`            | array  | A list of objects, where each object defines the connection and authentication details for a specific Gerrit instance. This is the core of the configuration. |
| `extensions`              | object | (Optional) Namespaced configuration blocks for extensions, keyed by extension name. See [Extensions](extensions.md#namespaced-configuration).                 |

______________________________________________________________________

## The `gerrit_hosts` Array

This is a list where you define each Gerrit instance you want to interact with.
The server will look through this list to find a host that matches the URL of a
given request.

Each host object has the following structure:

| Key              | Type   | Description                                                                                                                                                                                                                   |
| ---------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`           | string | A user-friendly name for the Gerrit instance (e.g., "Fuchsia", "Public Gerrit").                                                                                                                                              |
| `internal_url`   | string | (Optional) An alternative URL for the same host, often used for internal network access. The server will recognize both this and the `external_url`.                                                                          |
| `external_url`   | string | The primary, publicly accessible URL for the Gerrit host. URLs are normalized to `https://`; a plain `http://` URL is kept only for a loopback host (`localhost`, `127.0.0.1`, `::1`, `0.0.0.0`), e.g. a local test instance. |
| `authentication` | object | A required object that specifies which authentication method to use for this host. See the detailed section below.                                                                                                            |

______________________________________________________________________

## Authentication Methods

The `authentication` object is the most important part of the configuration. It
tells the server how to authenticate its `curl` requests to the Gerrit API. You
must specify a `type` for each host. There are four supported types.

### 1. `git_cookies` (Recommended)

This method authenticates requests using the same `.gitcookies` file that Git
uses to authenticate command-line operations like `git push`. This is a
convenient option if you already have this set up.

To generate or update your credentials, log in to your Gerrit instance, navigate
to **Settings** (the gear icon), and find the **HTTP Credentials** section.
Gerrit will provide a script or commands to run that will configure your
`.gitcookies` file with the correct authentication token.

- **`type`**: `"git_cookies"`
- **`gitcookies_path`**: The path to your `.gitcookies` file (e.g.,
  `~/.gitcookies`).

**Example:**

```json
{
  "name": "GitCookies Auth Example",
  "external_url": "https://another-gerrit.com/",
  "authentication": {
    "type": "git_cookies",
    "gitcookies_path": "~/.gitcookies"
  }
}
```

If a matching cookie is not found in the file, the server will fall back to
making an unauthenticated request.

### 2. `gob_curl` (Google Internal)

This method is for developers working within Google's corporate network.
`gob-curl` is a tool that automatically handles authentication for internal
services.

- **`type`**: `"gob_curl"`

**Example:**

```json
{
  "name": "Fuchsia Open Source [Googlers]",
  "internal_url": "https://fuchsia-review.git.private.corporation.com/",
  "external_url": "https://fuchsia-review.googlesource.com/",
  "authentication": {
    "type": "gob_curl"
  }
}
```

### 3. `http_basic`

This is the standard and most common method for authenticating with a Gerrit
instance's REST API. It uses a generated HTTP password or token.

- **`type`**: `"http_basic"`

You can supply the credentials in one of two ways.

#### Preferred: credentials from a netrc file

If you omit both `username` and `auth_token`, the server lets `curl` read your
credentials from a netrc file (via `curl --netrc`), keyed by host. This is the
recommended setup — analogous to `git_cookies` — because it avoids duplicating
your token in `gerrit_config.json`.

Add an entry to your `~/.netrc` for the Gerrit host, e.g.:

```
machine fuchsia-review.googlesource.com login your-username password your-auth-token
```

- **`netrc_path`**: (Optional) Path to a non-default netrc file (e.g.
  `~/.netrc-gerrit`). Maps to `curl --netrc-file`. If omitted, curl uses your
  default `~/.netrc`.

**Example:**

```json
{
  "name": "Fuchsia Open Source",
  "external_url": "https://fuchsia-review.googlesource.com/",
  "authentication": {
    "type": "http_basic"
  }
}
```

#### Inline credentials

Alternatively, specify the credentials directly. If you set one of these, you
must set both.

- **`username`**: Your Gerrit username.
- **`auth_token`**: Your Gerrit HTTP password/token. You can usually generate
  this from your Gerrit user settings page under "HTTP Credentials - Obtain
  Password".

**Example:**

```json
{
  "name": "Fuchsia Open Source",
  "external_url": "https://fuchsia-review.googlesource.com/",
  "authentication": {
    "type": "http_basic",
    "username": "your-username",
    "auth_token": "your-auth-token"
  }
}
```

### 4. `git_credentials` (Git credential helpers)

Use Git's configured credential helpers to retrieve a username and Gerrit HTTP
password. This reuses an existing keyring-backed Git setup without putting the
password in this configuration or a netrc file.

```json
{
  "name": "OpenDev",
  "external_url": "https://review.opendev.org/",
  "authentication": {
    "type": "git_credentials",
    "username": "your-username"
  }
}
```

- **`type`**: `"git_credentials"`.
- **`username`**: (Optional) Select an account when several use the same host.
  Otherwise Git and its helpers determine the username.

Configure helpers in Git, not in this JSON. If a working helper is already
configured, no further helper configuration is needed. For example, if the
`libsecret` helper is installed:

```gitconfig
[credential "https://review.opendev.org"]
    helper = libsecret
    username = your-username
```

Other helpers include Git Credential Manager and `osxkeychain`; use whichever is
available on your system. Security depends on the configured helper: Git's
`store` helper saves plaintext, whereas keyring-backed helpers can keep the
password in the system credential store. Provision the Gerrit HTTP password
using your helper's normal workflow before starting the server.

The server runs `git credential fill` outside any repository, using user/system
Git configuration rather than the agent's current repository configuration. It
queries the actual Gerrit base URL (including an installation subpath, but
excluding the REST `/a` suffix), honouring Git's `credential.useHttpPath` rules.
No credentials are cached by the server, approved, or rejected.

Terminal/askpass prompting is disabled and lookup has a 30-second timeout.
Helpers may still display their own keyring-unlock UI. Missing credentials,
lookup failures, and timeouts produce an error; there is no fallback to netrc or
unauthenticated access. Retrieved credentials are passed to curl over stdin, not
in command-line arguments or temporary credential files.

## Complete Configuration Example

Here is an example of a `gerrit_config.json` file that defines multiple hosts
using all available authentication methods.

```json
{
  "default_gerrit_base_url": "https://fuchsia-review.googlesource.com/",
  "gerrit_hosts": [
    {
      "name": "Fuchsia Open Source",
      "external_url": "https://fuchsia-review.googlesource.com/",
      "authentication": {
        "type": "http_basic",
        "username": "your-username",
        "auth_token": "your-auth-token"
      }
    },
    {
      "name": "Fuchsia Open Source [Googlers]",
      "internal_url": "https://fuchsia-review.git.private.corporation.com/",
      "external_url": "https://fuchsia-review.googlesource.com/",
      "authentication": {
        "type": "gob_curl"
      }
    },
    {
      "name": "AOSP (via gitcookies)",
      "external_url": "https://android-review.googlesource.com/",
      "authentication": {
        "type": "git_cookies",
        "gitcookies_path": "~/.gitcookies"
      }
    },
    {
      "name": "OpenDev (via Git credential helpers)",
      "external_url": "https://review.opendev.org/",
      "authentication": {
        "type": "git_credentials",
        "username": "your-username"
      }
    }
  ]
}
```
