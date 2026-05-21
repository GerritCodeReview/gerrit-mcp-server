---
name: writing-extensions
description: Guide for authoring a new in-process MCP tool extension for gerrit-mcp-server. Use when a user wants to add new Gerrit tools, port a standalone plugin MCP server into the extension framework, or needs a worked example of the ExtensionContext API.
---

# Writing a gerrit-mcp-server Extension

Extensions register new MCP tools inside the running `gerrit-mcp-server` process
via the `gerrit_mcp_server.extensions` entry-point group. They share the
server's auth, config, and HTTP machinery through the stable `ExtensionContext`
API.

## 1. Package layout

Each extension is a standalone Python package:

```
myext/
├── __init__.py          # empty
├── extension.py         # defines register(ctx)
└── pyproject.toml       # declares the entry point
```

This is a flat layout (package files alongside `pyproject.toml` rather than in a
`src/myext/` subdirectory). It requires an explicit `package-dir` in
`pyproject.toml` — see [section 8](#8_entry_point-declaration). Without it,
setuptools looks for a `./myext/` subdirectory and the build fails with
`package directory 'myext' does not exist`.

If the extension is a workspace member of a uv workspace, it lives at the repo
root alongside other workspace members.

## 2. The `register(ctx)` contract

`extension.py` must export a top-level
`register(ctx: ExtensionContext) -> None`. The server calls it once at startup.

```python
from gerrit_mcp_server.extensions import ExtensionContext

def register(ctx: ExtensionContext) -> None:
    """Register all tools for this extension."""

    @ctx.mcp.tool()
    async def my_tool(change_id: str, gerrit_base_url: str = None) -> str:
        """One-line description shown in the MCP tool list."""
        base_url = ctx.get_base_url(gerrit_base_url)
        result = await ctx.run_curl([f"{base_url}/changes/{change_id}"], base_url)
        return result
```

All tools must be `async def`. `ctx.mcp.tool()` is a FastMCP decorator —
register as many tools as needed.

## 3. Structured return types

All tools should declare a `TypedDict` return type rather than manually building
`[{"type": "text", "text": ...}]` content blocks. The MCP SDK auto-generates a
JSON `output_schema` from the annotation and produces both structured content
(for clients that support it) and a text fallback (for those that don't).

- Declare one `TypedDict` per tool result; use `NotRequired` for optional
  fields.
- Return the dict directly — no `json.dumps`, no content-block wrapping.
- Raise exceptions on error rather than returning a text error block.

```python
from typing import List, NotRequired, Optional, TypedDict

class _MyChange(TypedDict):
    change_number: int
    subject: str

class _MyToolResult(TypedDict):
    change_id: str
    changes: List[_MyChange]
    note: NotRequired[str]   # only present when changes is empty

def register(ctx: ExtensionContext) -> None:

    @ctx.mcp.tool()
    async def my_tool(
        change_id: str,
        gerrit_base_url: Optional[str] = None,
    ) -> _MyToolResult:
        """One-line description."""
        base_url = ctx.get_base_url(gerrit_base_url)
        url = f"{base_url}/changes/?q=parent:{change_id}"
        try:
            changes = json.loads(await ctx.run_curl([url], base_url))
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Gerrit response: {e}") from e
        result: _MyToolResult = {"change_id": change_id, "changes": changes}
        if not changes:
            result["note"] = "No changes found."
        return result
```

See `get_commit_message` in `gerrit_mcp_server/main.py` for a complete in-tree
example.

> [!IMPORTANT] Do **not** put `from __future__ import annotations` in a module
> that defines tool-result `TypedDict`s. With stringized annotations the MCP SDK
> fails to recognize `NotRequired`, marking every optional field as required in
> the generated `output_schema`; the tool then raises a validation error
> whenever an optional field is omitted. Keep annotations eager in extension
> modules.

## 4. `ExtensionContext` API reference

| Attribute                      | Type                             | Purpose                                                          |
| ------------------------------ | -------------------------------- | ---------------------------------------------------------------- |
| `ctx.mcp`                      | `FastMCP`                        | Register tools with `@ctx.mcp.tool()`                            |
| `ctx.get_base_url(url)`        | `Callable[[Optional[str]], str]` | Resolve a base URL (defaults from config if `None`)              |
| `ctx.normalize_url(url)`       | `Callable[[str], str]`           | Internal→external mapping, `/a` prefix for auth                  |
| `ctx.run_curl(args, base_url)` | `async Callable`                 | Authenticated HTTP; returns response body (XSSI prefix stripped) |
| `ctx.load_config()`            | `Callable[[], dict]`             | Full parsed `gerrit_config.json`                                 |
| `ctx.log_path`                 | `Path`                           | Shared `server.log`; open in append mode                         |
| `ctx.plugin_registry`          | `PluginRegistry \| None`         | Per-host plugin availability cache                               |
| `ctx.extension_config(name)`   | `method`                         | Returns `config["extensions"][name]` or `{}`                     |

`ctx.run_curl` takes a list where the first element is the full URL (including
query string), and the second argument is `base_url` (used to look up auth
credentials). Example:

```python
url = f"{base_url}/changes/?q=change:{change_id}&task--applicable"
body = await ctx.run_curl([url], base_url)
```

Note: `task--applicable` and other Gerrit DynamicOptions are plain query-string
parameters, **not** `&o=` output options. Pass them directly in the URL string.

Note: Gerrit REST API responses typically use `snake_case` field names
(`sub_tasks`, `has_pass`, `change_number`), even though the plugin's Java source
and SSH/documentation examples often show `camelCase` (`subTasks`, `hasPass`,
`changeNumber`). Plugin-defined attributes are serialized through Gerrit's
`LOWER_CASE_WITH_UNDERSCORES` policy on the REST path. Verify the actual wire
format against a real response (e.g. in `server.log`) before keying off a field,
rather than trusting the docs.

## 5. Per-host plugin gating with `requires_plugin`

Wrap tools that depend on an optional Gerrit plugin so they auto-route to a host
that has it and degrade gracefully when no host does.

```python
from typing import TypedDict

from gerrit_mcp_server.extensions import ExtensionContext, requires_plugin

class _MyPluginResult(TypedDict):
    change_id: str

def register(ctx: ExtensionContext) -> None:

    @ctx.mcp.tool()
    @requires_plugin("myplugin", ctx.plugin_registry)
    async def my_plugin_tool(
        change_id: str, gerrit_base_url: str = None
    ) -> _MyPluginResult:
        """Tool that requires the 'myplugin' Gerrit plugin."""
        base_url = ctx.get_base_url(gerrit_base_url)
        ...
```

**Decorator order matters**: `@requires_plugin` is the inner decorator;
`@ctx.mcp.tool()` is outer. FastMCP dispatches through the routing wrapper.

Behaviour:

- If `gerrit_base_url` is omitted, the first configured host with the plugin is
  used automatically.
- If the specified host lacks the plugin, the cache is refreshed once, then a
  `RuntimeError` listing available hosts is raised.
- If no host has the plugin, a `RuntimeError` is raised.

`requires_plugin` raises rather than returning a content-block list so it stays
compatible with the structured `TypedDict` return types from section 3: the MCP
SDK validates a tool's return value against its auto-generated output schema, so
a content-block list would fail validation.

`requires_plugin` is imported from `gerrit_mcp_server.extensions` (re-exported
there) or directly from `gerrit_mcp_server.plugin_registry`.

## 6. Namespaced config

Store extension-specific config under `config["extensions"]["myext"]` in
`gerrit_config.json`. Retrieve it via:

```python
cfg = ctx.extension_config("myext")   # returns {} if absent
timeout = cfg.get("timeout_seconds", 30)
```

Never read `ctx.load_config()` directly for extension-specific keys — use
`extension_config` to stay namespace-safe.

## 7. Logging

Append to the shared server log with the extension name as a prefix:

```python
import sys

def _log(ctx, msg: str) -> None:
    line = f"[myext] {msg}\n"
    try:
        ctx.log_path.open("a").write(line)
    except Exception:
        pass
    print(line.rstrip(), file=sys.stderr)
```

## 8. Entry-point declaration (`pyproject.toml`)

```toml
[project]
name = "myext"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["gerrit-mcp-server"]

[project.entry-points."gerrit_mcp_server.extensions"]
myext = "myext.extension:register"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["myext"]
package-dir = {"myext" = "."}
```

The entry-point key (`myext` on the left) is the name shown in server logs. The
value is `<module>:<callable>`.

`package-dir = {"myext" = "."}` is required by the flat layout from section 1.
Drop it only if you switch to a nested `src/myext/` layout.

## 9. Discovery at runtime

Two discovery mechanisms, combined at startup:

**Entry-point (preferred)**: install the package into the same venv as
`gerrit-mcp-server` and the server picks it up automatically.

```sh
# In a uv workspace — sync all members:
uv sync --all-packages

# Standalone:
uv pip install -e path/to/myext
```

**Environment variable**: for development or one-off use without installing:

```sh
GERRIT_MCP_EXTENSIONS=myext.extension uv run gerrit-mcp-server
# Multiple extensions:
GERRIT_MCP_EXTENSIONS=myext.extension,other.extension uv run gerrit-mcp-server
```

In a uv workspace where the extension is a workspace member,
`uv sync --all-packages` at the workspace root is all that's needed — entry
points in the extension's `pyproject.toml` become discoverable automatically.

The workspace root `pyproject.toml` must declare each member explicitly:

```toml
[tool.uv.workspace]
members = ["myext", "other_ext"]

[tool.uv.sources]
myext = { workspace = true }
other-ext = { workspace = true }
```

`members` entries are directory paths; `[tool.uv.sources]` keys must match the
`[project].name` values in each member's `pyproject.toml`. Without these blocks,
`uv sync` only installs the root package and the extension entry points are
never registered. Plain `uv sync` (without `--all-packages`) installs the root
package's dependencies but not the workspace members themselves.

> [!IMPORTANT] When you add a new workspace member, also add its directory to
> `dirs_to_copy` in `tests/integration/test_build_and_run.py`. That test does a
> clean build in a temp dir by copying in only the listed directories, so a
> missing member makes the workspace build fail there even though
> `uv run --extra dev pytest` passes everywhere else. Run
> `uv run --extra dev pytest` before shipping to catch this.

## 10. Testing

Use `pytest-asyncio` with a mocked `ExtensionContext`. Assert that `register`
registers the expected tools and that core logic produces correct output.

```python
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call
import pytest
from myext.extension import register

@pytest.fixture
def ctx(tmp_path):
    return MagicMock(
        mcp=MagicMock(),
        get_base_url=MagicMock(return_value="https://gerrit.example.com/a"),
        normalize_url=lambda u: u,
        run_curl=AsyncMock(return_value='[{"change_id": "123", "plugins": []}]'),
        load_config=MagicMock(return_value={}),
        log_path=tmp_path / "server.log",
        plugin_registry=MagicMock(),
        extension_config=MagicMock(return_value={}),
    )

def test_register_adds_tools(ctx):
    register(ctx)
    # At least one tool was registered
    assert ctx.mcp.tool.called

@pytest.mark.asyncio
async def test_my_tool_returns_structured_result(ctx):
    register(ctx)
    # Retrieve the registered tool function via the decorator call record
    tool_fn = ctx.mcp.tool.return_value.call_args[0][0]
    result = await tool_fn(change_id="123")
    # Tools return a TypedDict — assert on the dict directly, no json.loads
    assert result["change_id"] == "123"
```

## 11. Worked example — the `task` extension

See `gerrit_mcp_server_task/extension.py` for a complete, production-ready
example:

- Two tools (`get_task_tree`, `get_actionable_tasks`) both gated with
  `@requires_plugin("task", ...)`
- URL construction with `task--applicable` DynamicOption
- Depth-first `_find_actionable` walk (stop at PASS/DUPLICATE/SKIPPED/UNKNOWN;
  descend into WAITING)
- No bundled config or auth — fully delegated to `ExtensionContext`

## 12. Checklist before shipping

- [ ] All tools return a `TypedDict` with a declared return type annotation (not
  raw content blocks)
- [ ] `register(ctx)` in `extension.py` — no module-level side effects
- [ ] All tools are `async def` and accept
  `gerrit_base_url: Optional[str] = None`
- [ ] Plugin-dependent tools decorated with `@requires_plugin`
- [ ] Extension-specific config read via `ctx.extension_config("myname")`
- [ ] Entry point declared in `pyproject.toml` under
  `gerrit_mcp_server.extensions`
- [ ] `uv sync --all-packages` (or `pip install -e .`) installs without error
- [ ] New workspace member added to `dirs_to_copy` in
  `tests/integration/test_build_and_run.py`
- [ ] Server startup logs `extension myext.extension: registered`
- [ ] At least one pytest test verifying tool registration and core logic
