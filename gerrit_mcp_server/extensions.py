"""Extension hook for registering additional MCP tools.

Each extension is a Python module with a top-level ``register(ctx)``.
Discovered via the ``gerrit_mcp_server.extensions`` entry-point group or
the ``GERRIT_MCP_EXTENSIONS`` env var (comma-separated module names).

``ctx`` is an :class:`ExtensionContext` exposing the stable public
surface; everything else in this package is internal. Failures in an
extension are logged and skipped, never aborting startup.
"""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from gerrit_mcp_server.plugin_registry import PluginRegistry, requires_plugin

__all__ = [
    "ExtensionContext",
    "PluginRegistry",
    "load_extensions",
    "requires_plugin",
    "unload_extensions",
]

ENTRY_POINT_GROUP = "gerrit_mcp_server.extensions"
ENV_VAR = "GERRIT_MCP_EXTENSIONS"


@dataclass
class ExtensionContext:
    """Stable public API passed to each extension's ``register()``."""

    mcp: Any
    """FastMCP server. Register tools via ``@ctx.mcp.tool()``."""

    get_base_url: Callable[[Optional[str]], str]
    """Resolve a Gerrit base URL (defaults, env, normalization applied)."""

    normalize_url: Callable[[str], str]
    """Normalize a Gerrit URL (internal->external, /a prefix when needed)."""

    run_curl: Callable[[List[str], str], Awaitable[str]]
    """Authenticated curl against a base URL; returns the response body."""

    load_config: Callable[[], Dict[str, Any]]
    """Return the full parsed ``gerrit_config.json``."""

    log_path: Path
    """Shared ``server.log`` path; extensions append here."""

    plugin_registry: Any = None
    """Optional :class:`~gerrit_mcp_server.plugin_registry.PluginRegistry`."""

    def extension_config(self, name: str) -> Dict[str, Any]:
        """Return ``config['extensions'][name]`` (``{}`` if absent).

        Extensions should namespace their config under this key so the
        core config shape stays stable.
        """
        cfg = self.load_config() or {}
        return (cfg.get("extensions") or {}).get(name) or {}


def _discover_entry_point_modules() -> List[str]:
    return [ep.module for ep in entry_points(group=ENTRY_POINT_GROUP)]


def _discover_env_modules() -> List[str]:
    raw = os.environ.get(ENV_VAR, "").strip()
    if not raw:
        return []
    return [m.strip() for m in raw.split(",") if m.strip()]


def load_extensions(ctx: ExtensionContext) -> List[str]:
    """Discover and register every extension; return the successful names.

    Import or ``register()`` failures are logged to ``ctx.log_path`` and
    stderr, then skipped.
    """
    raw_modules = _discover_entry_point_modules() + _discover_env_modules()
    seen: Dict[str, int] = {}
    for m in raw_modules:
        seen[m] = seen.get(m, 0) + 1
    for m, count in seen.items():
        if count > 1:
            _log(ctx, m, f"WARNING: discovered {count} times; loading once")
    modules = list(dict.fromkeys(raw_modules))
    registered: List[str] = []

    for module_name in modules:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            _log(ctx, module_name, f"ERROR: import failed: {exc}")
            continue

        register = getattr(module, "register", None)
        if not callable(register):
            _log(ctx, module_name, "ERROR: missing register(ctx) function")
            continue

        try:
            register(ctx)
        except Exception as exc:
            _log(ctx, module_name, f"ERROR: register() raised: {exc}")
            continue

        registered.append(module_name)
        _log(ctx, module_name, "registered")

    return registered


def unload_extensions(ctx: ExtensionContext) -> None:
    """Lifecycle hook placeholder for server shutdown.

    Extensions that need cleanup should implement an ``unregister(ctx)``
    function. This stub establishes the contract; a full implementation
    requires tracking which modules were registered (see ``load_extensions``).
    """
    pass


def _log(ctx: ExtensionContext, module_name: str, msg: str) -> None:
    line = f"[gerrit-mcp-server] extension {module_name}: {msg}\n"
    try:
        with open(ctx.log_path, "a") as log_file:
            log_file.write(line)
    except Exception:
        pass
    print(line.rstrip(), file=sys.stderr)
