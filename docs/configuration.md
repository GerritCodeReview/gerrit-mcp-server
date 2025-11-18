# Gerrit MCP Server Configuration (`gerrit_config.json`)

The `gerrit_mcp_server` is configured via a central JSON file located at `gerrit_mcp_server/gerrit_config.json`. This file allows you to define connection and authentication details for multiple Gerrit instances.

A sample file is provided at `gerrit_mcp_server/gerrit_config.sample.json` which you can copy and customize.

## Top-Level Configuration

The configuration file has two main properties at its root:

| Key                       | Type   | Description                                                                                                                                 |
| ------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `default_gerrit_base_url` | string | The full URL of the Gerrit instance to use if a tool is called without a specific `gerrit_base_url` parameter.                               |
| `gerrit_hosts`            | array  | A list of objects, where each object defines the connection and authentication details for a specific Gerrit instance. This is the core of the configuration. |

---

## The `gerrit_hosts` Array

This is a list where you define each Gerrit instance you want to interact with. The server will look through this list to find a host that matches the URL of a given request.

Each host object has the following structure:

| Key              | Type   | Description                                                                                                                                                           |
| ---------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`           | string | A user-friendly name for the Gerrit instance (e.g., "Fuchsia", "Public Gerrit").                                                                                      |
| `internal_url`   | string | (Optional) An alternative URL for the same host, often used for internal network access. The server will recognize both this and the `external_url`.                     |
| `external_url`   | string | The primary, publicly accessible URL for the Gerrit host.                                                                                                             |
| `authentication` | object | A required object that specifies which authentication method to use for this host. See the detailed section below.                                                    |

---

## Authentication Methods

The `authentication` object is the most important part of the configuration. It tells the server how to authenticate its `curl` requests to the Gerrit API. You must specify a `type` for each host. There are three supported types.


### 1. `git_cookies` (Recommended)

This method authenticates requests using the same `.gitcookies` file that Git uses to authenticate command-line operations like `git push`. This is a convenient option if you already have this set up.

To generate or update your credentials, log in to your Gerrit instance, navigate to **Settings** (the gear icon), and find the **HTTP Credentials** section. Gerrit will provide a script or commands to run that will configure your `.gitcookies` file with the correct authentication token.

*   **`type`**: `"git_cookies"`
*   **`gitcookies_path`**: The path to your `.gitcookies` file (e.g., `~/.gitcookies`).

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
If a matching cookie is not found in the file, the server will fall back to making an unauthenticated request.

### 2. `gob_curl` (Google Internal)

This method is for developers working within Google's corporate network. `gob-curl` is a tool that automatically handles authentication for internal services.

*   **`type`**: `"gob_curl"`

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

### 3. `http_basic` (Not Recommended)

This is the standard and most common method for authenticating with a Gerrit instance's REST API. It uses a generated HTTP password or token.

*   **`type`**: `"http_basic"`
*   **`username`**: Your Gerrit username.
*   **`auth_token`**: Your Gerrit HTTP password/token. You can usually generate this from your Gerrit user settings page under "HTTP Credentials - Obtain Password".

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

## Complete Configuration Example

Here is an example of a `gerrit_config.json` file that defines multiple hosts using all available authentication methods.

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
    }
  ]
}
```
