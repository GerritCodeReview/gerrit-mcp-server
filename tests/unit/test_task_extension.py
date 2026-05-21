import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from gerrit_mcp_server_task.extension import _find_actionable, register

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx(tmp_path: Path):
    mock_ctx = MagicMock()
    mock_ctx.get_base_url = MagicMock(return_value="https://gerrit.example.com/a")
    mock_ctx.normalize_url = lambda u: u
    mock_ctx.run_curl = AsyncMock()
    mock_ctx.load_config = MagicMock(return_value={})
    mock_ctx.log_path = tmp_path / "server.log"
    mock_ctx.plugin_registry = MagicMock()
    # requires_plugin awaits host_has_plugin — must be an AsyncMock
    mock_ctx.plugin_registry.host_has_plugin = AsyncMock(return_value=True)
    mock_ctx.extension_config = MagicMock(return_value={})
    return mock_ctx


def _gerrit_response(roots):
    """Wrap roots in the Gerrit /changes/ response envelope."""
    return json.dumps(
        [{"change_id": "123", "plugins": [{"name": "task", "roots": roots}]}]
    )


# ---------------------------------------------------------------------------
# _find_actionable unit tests
# ---------------------------------------------------------------------------


class TestFindActionable:
    def test_ready_node_returned(self):
        node = {"name": "t", "status": "READY", "sub_tasks": []}
        assert _find_actionable(node) == [node]

    def test_fail_node_returned(self):
        node = {"name": "t", "status": "FAIL", "sub_tasks": []}
        assert _find_actionable(node) == [node]

    def test_pass_node_not_returned(self):
        assert _find_actionable({"name": "t", "status": "PASS"}) == []

    def test_duplicate_node_not_returned(self):
        assert _find_actionable({"name": "t", "status": "DUPLICATE"}) == []

    def test_skipped_node_not_returned(self):
        assert _find_actionable({"name": "t", "status": "SKIPPED"}) == []

    def test_unknown_node_not_returned(self):
        assert _find_actionable({"name": "t", "status": "UNKNOWN"}) == []

    def test_waiting_descends_into_children(self):
        leaf = {"name": "leaf", "status": "READY", "sub_tasks": []}
        waiting = {"name": "parent", "status": "WAITING", "sub_tasks": [leaf]}
        assert _find_actionable(waiting) == [leaf]

    def test_waiting_not_returned_itself(self):
        waiting = {"name": "w", "status": "WAITING", "sub_tasks": []}
        assert _find_actionable(waiting) == []

    def test_nested_waiting_reaches_leaf(self):
        leaf = {"name": "leaf", "status": "FAIL", "sub_tasks": []}
        mid = {"name": "mid", "status": "WAITING", "sub_tasks": [leaf]}
        root = {"name": "root", "status": "WAITING", "sub_tasks": [mid]}
        assert _find_actionable(root) == [leaf]

    def test_mixed_children(self):
        pass_node = {"name": "pass", "status": "PASS"}
        ready_node = {"name": "ready", "status": "READY"}
        waiting = {
            "name": "w",
            "status": "WAITING",
            "sub_tasks": [pass_node, ready_node],
        }
        assert _find_actionable(waiting) == [ready_node]


# ---------------------------------------------------------------------------
# register() integration tests
# ---------------------------------------------------------------------------


class TestRegister:
    def test_register_adds_two_tools(self, ctx):
        register(ctx)
        assert ctx.mcp.tool.call_count == 2

    @pytest.mark.asyncio
    async def test_get_task_tree_returns_roots(self, ctx):
        roots = [{"name": "coral", "status": "WAITING", "sub_tasks": []}]
        ctx.run_curl = AsyncMock(return_value=_gerrit_response(roots))

        registered = {}

        def capture_decorator():
            def decorator(fn):
                registered[fn.__name__] = fn
                return fn

            return decorator

        ctx.mcp.tool = MagicMock(side_effect=lambda: capture_decorator())
        register(ctx)

        # get_task_tree is wrapped by requires_plugin; call __wrapped__ directly
        fn = registered.get("get_task_tree")
        assert fn is not None
        data = await fn(change_id="123", gerrit_base_url="https://gerrit.example.com/a")
        assert data["change_id"] == "123"
        assert data["roots"] == roots

    @pytest.mark.asyncio
    async def test_get_actionable_tasks_filters_status(self, ctx):
        roots = [
            {
                "name": "top",
                "status": "WAITING",
                "sub_tasks": [
                    {"name": "pass-task", "status": "PASS", "sub_tasks": []},
                    {"name": "ready-task", "status": "READY", "sub_tasks": []},
                ],
            }
        ]
        ctx.run_curl = AsyncMock(return_value=_gerrit_response(roots))

        registered = {}

        def capture_decorator():
            def decorator(fn):
                registered[fn.__name__] = fn
                return fn

            return decorator

        ctx.mcp.tool = MagicMock(side_effect=lambda: capture_decorator())
        register(ctx)

        fn = registered.get("get_actionable_tasks")
        assert fn is not None
        data = await fn(change_id="123", gerrit_base_url="https://gerrit.example.com/a")
        assert len(data["actionable_tasks"]) == 1
        assert data["actionable_tasks"][0]["name"] == "ready-task"

    @pytest.mark.asyncio
    async def test_get_task_tree_no_plugin_data(self, ctx):
        ctx.run_curl = AsyncMock(
            return_value=json.dumps([{"change_id": "123", "plugins": []}])
        )

        registered = {}

        def capture_decorator():
            def decorator(fn):
                registered[fn.__name__] = fn
                return fn

            return decorator

        ctx.mcp.tool = MagicMock(side_effect=lambda: capture_decorator())
        register(ctx)

        fn = registered.get("get_task_tree")
        assert fn is not None
        data = await fn(change_id="123", gerrit_base_url="https://gerrit.example.com/a")
        assert data["roots"] == []
        assert "note" in data

    @pytest.mark.asyncio
    async def test_get_task_tree_no_change_found(self, ctx):
        ctx.run_curl = AsyncMock(return_value="[]")

        registered = {}

        def capture_decorator():
            def decorator(fn):
                registered[fn.__name__] = fn
                return fn

            return decorator

        ctx.mcp.tool = MagicMock(side_effect=lambda: capture_decorator())
        register(ctx)

        fn = registered.get("get_task_tree")
        assert fn is not None
        with pytest.raises(ValueError, match="No change found"):
            await fn(change_id="999", gerrit_base_url="https://gerrit.example.com/a")
