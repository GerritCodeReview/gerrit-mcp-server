"""gerrit-mcp-server extension for the Gerrit depends-on plugin.

Exposes two MCP tools:
  - get_depends_on: Depends-on plugin dependencies declared on a change
  - get_dependents: changes that declare Depends-on: on a given change

Both tools require the 'depends-on' Gerrit plugin via @requires_plugin.
"""

import json
from typing import Any, Dict, List, NotRequired, Optional, TypedDict
from urllib.parse import quote

from gerrit_mcp_server.extensions import ExtensionContext, requires_plugin


class _DependsOn(TypedDict):
    resolved: bool
    change_number: Optional[int]
    unresolved: Optional[str]


class _DependsOnResult(TypedDict):
    change_id: str
    depends_ons: List[_DependsOn]
    note: NotRequired[str]


class _DependentsResult(TypedDict):
    change_id: str
    dependents: List[Dict[str, Any]]


def register(ctx: ExtensionContext) -> None:
    """Register get_depends_on and get_dependents MCP tools."""

    @ctx.mcp.tool()
    @requires_plugin("depends-on", ctx.plugin_registry)
    async def get_depends_on(
        change_id: str,
        gerrit_base_url: Optional[str] = None,
    ) -> _DependsOnResult:
        """Return the Depends-on plugin dependencies declared on a change.

        Each item in the returned list is either resolved (has a change_number)
        or unresolved (has an unresolved I-hash that couldn't be matched to a
        change in the configured deliverables).

        Uses the --depends-on--all DynamicOption to include all dependencies
        regardless of deliverable scope.
        """
        base_url = ctx.get_base_url(gerrit_base_url)
        url = f"{base_url}/changes/?q=change:{quote(str(change_id))}&--depends-on--all"

        result_str = await ctx.run_curl([url], base_url)
        try:
            changes = json.loads(result_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse Gerrit response: {result_str}") from e

        if not changes:
            raise ValueError(f"No change found for ID: {change_id}")

        change = changes[0]
        plugins = change.get("plugins", [])
        plugin_data = next((p for p in plugins if p.get("name") == "depends-on"), None)

        if plugin_data is None:
            return {
                "change_id": change_id,
                "depends_ons": [],
                "note": (
                    "The depends-on plugin returned no data. "
                    "The plugin may not be installed on this Gerrit instance."
                ),
            }

        deps: List[_DependsOn] = []
        for dep in plugin_data.get("depends_ons", []):
            cn = dep.get("change_number")
            deps.append(
                {
                    "resolved": cn is not None,
                    "change_number": cn,
                    "unresolved": dep.get("unresolved"),
                }
            )

        return {"change_id": change_id, "depends_ons": deps}

    @ctx.mcp.tool()
    @requires_plugin("depends-on", ctx.plugin_registry)
    async def get_dependents(
        change_id: str,
        gerrit_base_url: Optional[str] = None,
    ) -> _DependentsResult:
        """Return changes that explicitly declare Depends-on: on the given change.

        Uses the independson:<change_id> query operator registered by the depends-on
        plugin.
        """
        base_url = ctx.get_base_url(gerrit_base_url)
        query = f"independson:{change_id}"
        url = f"{base_url}/changes/?q={quote(query)}"

        result_str = await ctx.run_curl([url], base_url)
        try:
            changes = json.loads(result_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse Gerrit response: {result_str}") from e

        return {"change_id": change_id, "dependents": changes}
