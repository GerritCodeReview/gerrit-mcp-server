# Extensions

The Gerrit MCP server can be extended with additional MCP tools without
modifying the core package. An **extension** is a Python module that exposes a
top-level `register(ctx)` function; the server discovers it at startup, calls
`register(ctx)`, and the tools it registers become visible from the first
request.

This is the supported way to ship tools that wrap a specific Gerrit plugin (or
any other host-specific capability) while keeping the core server generic.

## How extensions are discovered

At startup, `cli_main` builds an `ExtensionContext` and calls
`ExtensionLoader(context).load()`, which discovers modules from two sources and
loads each exactly once:

1. **Entry points** — any installed distribution that advertises the
   `gerrit_mcp_server.extensions` entry-point group.
2. **Environment variable** — `GERRIT_MCP_EXTENSIONS`, a comma-separated list of
   importable module names.

Both sources are combined and de-duplicated; a module discovered more than once
is loaded a single time and a `WARNING` is logged.

> [!IMPORTANT] An extension that fails to import, lacks a callable `register`,
> or raises from `register()` is logged to `server.log` (and stderr) and
> skipped. One broken extension never aborts server startup.

### Registering via an entry point

In the extension distribution's `pyproject.toml`:

```toml
[project.entry-points."gerrit_mcp_server.extensions"]
my_extension = "my_extension"
```

The entry-point *value* is the module that defines `register(ctx)`. The name on
the left is cosmetic.

### Registering via the environment variable

For local development or modules not packaged as a distribution:

```bash
export GERRIT_MCP_EXTENSIONS="my_extension,another.ext.module"
uv run gerrit-mcp-server
```

## Writing an extension

A minimal extension defines `register(ctx)` and registers tools on the FastMCP
instance exposed by the context:

```python
"""my_extension.py"""

def register(ctx):
    @ctx.mcp.tool()
    async def my_tool(change_id: str, gerrit_base_url: str | None = None) -> dict:
        """Return some detail about a change."""
        base_url = ctx.get_base_url(gerrit_base_url)
        body = await ctx.run_curl([f"{base_url}/changes/{change_id}/detail"], base_url)
        return {"change_id": change_id, "raw": body}
```

Tools you register follow the same conventions as the core tools — in
particular, prefer a typed `TypedDict` return value and raise exceptions on
error rather than returning text content blocks. See **Tool Design** in
[`AGENTS.md`](../AGENTS.md) for the structured-output contract.

### The `ExtensionContext`

`register(ctx)` receives an `ExtensionContext`, the only stable public surface
extensions should depend on. Everything else in the `gerrit_mcp_server` package
is internal and may change.

| Attribute / method         | Description                                                                                |
| -------------------------- | ------------------------------------------------------------------------------------------ |
| `mcp`                      | The FastMCP server. Register tools with `@ctx.mcp.tool()`.                                 |
| `get_base_url(url=None)`   | Resolve a Gerrit base URL — applies defaults/env, normalization, and the `/a` auth prefix. |
| `normalize_url(url)`       | Normalize a Gerrit URL (internal→external, `/a` prefix when needed).                       |
| `run_curl(args, base_url)` | Run an authenticated `curl` against a base URL and return the response body. Awaitable.    |
| `load_config()`            | Return the full parsed `gerrit_config.json`.                                               |
| `extension_config(name)`   | Return `config["extensions"][name]` (or `{}` if absent) — your namespaced config block.    |
| `log_path`                 | Path to the shared `server.log`; append diagnostics here.                                  |
| `plugin_registry`          | A `PluginRegistry` for plugin-backed tools (see below).                                    |

### Namespaced configuration

Extensions should read their settings from a namespaced block under the
top-level `extensions` key in `gerrit_config.json`, accessed via
`ctx.extension_config("<name>")`. Namespacing keeps the core config shape stable
and avoids collisions between extensions.

```json
{
  "default_gerrit_base_url": "https://gerrit.example.com/",
  "gerrit_hosts": [ ... ],
  "extensions": {
    "my_extension": {
      "some_option": true
    }
  }
}
```

```python
def register(ctx):
    options = ctx.extension_config("my_extension")
    enabled = options.get("some_option", False)
    ...
```

## Plugin-backed tools and `requires_plugin`

Many extensions wrap a specific Gerrit plugin's REST endpoints. Because a plugin
may be installed on some configured hosts but not others, the framework provides
`PluginRegistry` and the `requires_plugin` decorator to route a tool to a host
that actually has the plugin.

`PluginRegistry` queries `/plugins/?all` lazily, per host, caches the result
with a TTL (one hour by default), and filters out disabled plugins.

Decorate a tool with `requires_plugin(plugin_name, ctx.plugin_registry)`. The
wrapped coroutine must accept a `gerrit_base_url` keyword argument:

```python
from gerrit_mcp_server.extensions import requires_plugin


def register(ctx):
    @ctx.mcp.tool()
    @requires_plugin("task", ctx.plugin_registry)
    async def get_task_tree(change_id: str, gerrit_base_url: str | None = None) -> dict:
        """Return the task tree for a change (requires the `task` plugin)."""
        base_url = ctx.get_base_url(gerrit_base_url)
        body = await ctx.run_curl([f"{base_url}/a/changes/{change_id}/...", base_url])
        return {"change_id": change_id, "raw": body}
```

Routing behavior:

- **No `gerrit_base_url` supplied** → the first configured host that has the
  plugin is used automatically.
- **`gerrit_base_url` supplied but the host lacks the plugin** → the cache is
  refreshed once; if the plugin is still absent, a `RuntimeError` is raised
  naming the hosts that do have it.
- **No configured host has the plugin** → a `RuntimeError` is raised.

> [!NOTE] `requires_plugin` raises a `RuntimeError` (rather than returning a
> content-block list) on routing failure. This keeps it compatible with tools
> that declare a structured `TypedDict` return type: the MCP SDK validates a
> tool's return value against its auto-generated output schema, so a
> content-block list would fail validation. The raised error propagates to the
> caller as a normal tool error.

## Lifecycle

`ExtensionLoader.load()` is the registration hook. A complementary
`ExtensionLoader.unload()` hook exists as a placeholder for shutdown cleanup;
the contract is that an extension needing cleanup defines an `unregister(ctx)`
function, but a full implementation is not yet wired up.
