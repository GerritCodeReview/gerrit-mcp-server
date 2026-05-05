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
from typing import Any, Awaitable, Callable, Final

from mcp.server.fastmcp import FastMCP

from gerrit_mcp_server.plugin_registry import PluginRegistry, requires_plugin

__all__ = [
    "ExtensionContext",
    "ExtensionLoader",
    "PluginRegistry",
    "requires_plugin",
]

ENTRY_POINT_GROUP: Final[str] = "gerrit_mcp_server.extensions"
ENV_VAR: Final[str] = "GERRIT_MCP_EXTENSIONS"


@dataclass
class ExtensionContext:
    """Stable public API passed to each extension's ``register()``."""

    mcp: FastMCP
    """FastMCP server. Register tools via ``@ctx.mcp.tool()``."""

    get_base_url: Callable[[str | None], str]
    """Resolve a Gerrit base URL (defaults, env, normalization applied)."""

    normalize_url: Callable[[str], str]
    """Normalize a Gerrit URL (internal->external, /a prefix when needed)."""

    run_curl: Callable[[list[str], str], Awaitable[str]]
    """Authenticated curl against a base URL; returns the response body."""

    load_config: Callable[[], dict[str, Any]]
    """Return the full parsed ``gerrit_config.json``."""

    log_path: Path
    """Shared ``server.log`` path; extensions append here."""

    plugin_registry: Any = None
    """Optional :class:`~gerrit_mcp_server.plugin_registry.PluginRegistry`."""

    def extension_config(self, name: str) -> dict[str, Any]:
        """Return ``config['extensions'][name]`` (``{}`` if absent).

        Extensions should namespace their config under this key so the
        core config shape stays stable.
        """
        config = self.load_config() or {}
        return (config.get("extensions") or {}).get(name) or {}


class ExtensionLoader:
    """Discover, register, and (eventually) tear down extensions.

    Holds the :class:`ExtensionContext` so the discovery, registration,
    and logging steps share it without passing it around explicitly.
    """

    def __init__(self, context: ExtensionContext) -> None:
        self._context = context

    def load(self) -> list[str]:
        """Discover and register every extension; return the successful names.

        Import or ``register()`` failures are logged to the context's
        ``log_path`` and stderr, then skipped.
        """
        raw_modules = (
            self._discover_entry_point_modules() + self._discover_env_modules()
        )
        seen: dict[str, int] = {}
        for module_name in raw_modules:
            seen[module_name] = seen.get(module_name, 0) + 1
        for module_name, count in seen.items():
            if count > 1:
                self._log(
                    module_name, f"WARNING: discovered {count} times; loading once"
                )
        modules = list(dict.fromkeys(raw_modules))
        registered: list[str] = []

        for module_name in modules:
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:
                self._log(module_name, f"ERROR: import failed: {exc}")
                continue

            register = getattr(module, "register", None)
            if not callable(register):
                self._log(module_name, "ERROR: missing register(ctx) function")
                continue

            try:
                register(self._context)
            except Exception as exc:
                self._log(module_name, f"ERROR: register() raised: {exc}")
                continue

            registered.append(module_name)
            self._log(module_name, "registered")

        return registered

    def unload(self) -> None:
        """Lifecycle hook placeholder for server shutdown.

        Extensions that need cleanup should implement an ``unregister(ctx)``
        function. This stub establishes the contract; a full implementation
        requires tracking which modules were registered (see :meth:`load`).
        """
        pass

    def _discover_entry_point_modules(self) -> list[str]:
        """Discover entry-point modules, honoring the never-abort-startup contract.

        A single malformed entry point in the environment can make
        ``entry_points()`` raise; log and fall back to no entry-point
        modules rather than aborting startup.
        """
        try:
            return [
                entry_point.module
                for entry_point in entry_points(group=ENTRY_POINT_GROUP)
            ]
        except Exception as exc:
            self._log("<entry-point-discovery>", f"ERROR: discovery failed: {exc}")
            return []

    def _discover_env_modules(self) -> list[str]:
        raw = os.environ.get(ENV_VAR, "").strip()
        if not raw:
            return []
        return [module.strip() for module in raw.split(",") if module.strip()]

    def _log(self, module_name: str, message: str) -> None:
        line = f"[gerrit-mcp-server] extension {module_name}: {message}\n"
        try:
            with open(self._context.log_path, "a") as log_file:
                log_file.write(line)
        except Exception:
            pass
        print(line.rstrip(), file=sys.stderr)
