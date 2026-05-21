"""gerrit-mcp-server extension for the Gerrit task plugin.

Exposes two MCP tools:
  - get_task_tree: full task tree for a change (task--applicable pruned)
  - get_actionable_tasks: depth-first walk returning only READY/FAIL nodes

Both tools require the 'task' Gerrit plugin via @requires_plugin; they
auto-route to a host that has it and return a soft hint when none does.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from gerrit_mcp_server.extensions import ExtensionContext, requires_plugin


def _find_actionable(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Walk the task tree depth-first; collect READY and FAIL nodes.

    WAITING nodes are not returned but descended into — actionable leaf
    nodes hide beneath WAITING parents in nested task hierarchies.
    PASS, DUPLICATE, SKIPPED, and UNKNOWN are terminal (stop, don't yield).
    """
    status = node.get("status", "")
    if status in ("READY", "FAIL"):
        return [node]
    if status == "WAITING":
        result: List[Dict[str, Any]] = []
        for child in node.get("sub_tasks", []):
            result.extend(_find_actionable(child))
        return result
    return []


def register(ctx: ExtensionContext) -> None:
    """Register get_task_tree and get_actionable_tasks MCP tools."""

    async def _fetch_task_tree(
        change_id: str,
        task_only: Optional[str],
        gerrit_base_url: Optional[str],
    ) -> str:
        """Core logic shared by both tools — not registered as an MCP tool."""
        base_url = ctx.get_base_url(gerrit_base_url)
        url = f"{base_url}/changes/?q=change:{quote(str(change_id))}&task--applicable"
        if task_only:
            url += f"&task--only={quote(task_only)}"

        result_str = await ctx.run_curl([url], base_url)
        try:
            changes = json.loads(result_str)
        except json.JSONDecodeError:
            return f"Could not parse Gerrit response: {result_str}"

        if not changes:
            return f"No change found for ID: {change_id}"

        change = changes[0]
        plugins = change.get("plugins", [])
        task_data = next((p for p in plugins if p.get("name") == "task"), None)

        if task_data is None:
            return json.dumps(
                {
                    "change_id": change_id,
                    "roots": [],
                    "note": (
                        "The task plugin returned no data. "
                        "The plugin may not be installed on this Gerrit instance."
                    ),
                },
                indent=2,
            )

        return json.dumps(
            {"change_id": change_id, "roots": task_data.get("roots", [])},
            indent=2,
        )

    @ctx.mcp.tool()
    @requires_plugin("task", ctx.plugin_registry)
    async def get_task_tree(
        change_id: str,
        task_only: Optional[str] = None,
        gerrit_base_url: Optional[str] = None,
    ) -> str:
        """Return the full task tree attached to a Gerrit change.

        Uses task--applicable to prune tasks that don't apply to this change. Pass
        task_only to scope to a single root task.

        Returns a JSON object with change_id and roots (list of task nodes, each with
        name, status, hint, in_progress, has_pass, exported, change, and sub_tasks
        fields). If the task plugin is not installed on the target host, a note is
        included and roots is empty.
        """
        return await _fetch_task_tree(change_id, task_only, gerrit_base_url)

    @ctx.mcp.tool()
    @requires_plugin("task", ctx.plugin_registry)
    async def get_actionable_tasks(
        change_id: str,
        task_only: Optional[str] = None,
        gerrit_base_url: Optional[str] = None,
    ) -> str:
        """Return only actionable tasks (status READY or FAIL) for a change.

        Walks the full task tree depth-first and collects every node whose
        status is READY or FAIL. WAITING nodes are descended into but not
        returned. PASS, DUPLICATE, SKIPPED, and UNKNOWN are not returned.

        Pass task_only to scope to a single root task.
        """
        tree_json = await _fetch_task_tree(change_id, task_only, gerrit_base_url)
        try:
            tree = json.loads(tree_json)
        except json.JSONDecodeError:
            return tree_json

        if "note" in tree:
            return tree_json

        actionable: List[Dict[str, Any]] = []
        for root in tree.get("roots", []):
            actionable.extend(_find_actionable(root))

        return json.dumps(
            {"change_id": change_id, "actionable_tasks": actionable},
            indent=2,
        )
