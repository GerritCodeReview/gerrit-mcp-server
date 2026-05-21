import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import quote

import pytest

from gerrit_mcp_server_depends_on.extension import register

# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------

BASE_URL = "https://gerrit.example.com/a"


@pytest.fixture
def ctx(tmp_path: Path):
    mock_ctx = MagicMock()
    mock_ctx.get_base_url = MagicMock(return_value=BASE_URL)
    mock_ctx.normalize_url = lambda u: u
    mock_ctx.run_curl = AsyncMock()
    mock_ctx.load_config = MagicMock(return_value={})
    mock_ctx.log_path = tmp_path / "server.log"
    mock_ctx.plugin_registry = MagicMock()
    mock_ctx.plugin_registry.host_has_plugin = AsyncMock(return_value=True)
    mock_ctx.extension_config = MagicMock(return_value={})
    return mock_ctx


def _capture_tools(ctx) -> dict:
    """Replace ctx.mcp.tool with a capturing decorator; return registered fns."""
    registered = {}

    def capture_decorator():
        def decorator(fn):
            registered[fn.__name__] = fn
            return fn

        return decorator

    ctx.mcp.tool = MagicMock(side_effect=lambda: capture_decorator())
    register(ctx)
    return registered


def _wrap_response(change_number, deps):
    return json.dumps(
        [
            {
                "_number": change_number,
                "plugins": [{"name": "depends-on", "depends_ons": deps}],
            }
        ]
    )


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------


class TestRegister:
    def test_registers_two_tools(self, ctx):
        register(ctx)
        assert ctx.mcp.tool.call_count == 2


# ---------------------------------------------------------------------------
# get_depends_on
# ---------------------------------------------------------------------------


class TestGetDependsOn:
    @pytest.mark.asyncio
    async def test_resolved_dependency(self, ctx):
        ctx.run_curl = AsyncMock(
            return_value=_wrap_response(
                200, [{"change_number": 100, "unresolved": None}]
            )
        )
        fn = _capture_tools(ctx)["get_depends_on"]
        data = json.loads(await fn(change_id="200", gerrit_base_url=BASE_URL))
        assert data["change_id"] == "200"
        assert len(data["depends_ons"]) == 1
        dep = data["depends_ons"][0]
        assert dep["resolved"] is True
        assert dep["change_number"] == 100
        assert dep["unresolved"] is None

    @pytest.mark.asyncio
    async def test_unresolved_dependency(self, ctx):
        i_hash = "Iabcdef1234567890abcdef1234567890abcdef12"
        ctx.run_curl = AsyncMock(
            return_value=_wrap_response(
                200, [{"change_number": None, "unresolved": i_hash}]
            )
        )
        fn = _capture_tools(ctx)["get_depends_on"]
        data = json.loads(await fn(change_id="200", gerrit_base_url=BASE_URL))
        dep = data["depends_ons"][0]
        assert dep["resolved"] is False
        assert dep["change_number"] is None
        assert dep["unresolved"] == i_hash

    @pytest.mark.asyncio
    async def test_multiple_mixed_dependencies(self, ctx):
        ctx.run_curl = AsyncMock(
            return_value=_wrap_response(
                300,
                [
                    {"change_number": 100, "unresolved": None},
                    {
                        "change_number": None,
                        "unresolved": "Ideadbeef0000000000000000000000000000dead",
                    },
                ],
            )
        )
        fn = _capture_tools(ctx)["get_depends_on"]
        data = json.loads(await fn(change_id="300", gerrit_base_url=BASE_URL))
        assert len(data["depends_ons"]) == 2
        assert data["depends_ons"][0]["resolved"] is True
        assert data["depends_ons"][1]["resolved"] is False

    @pytest.mark.asyncio
    async def test_no_plugin_data(self, ctx):
        ctx.run_curl = AsyncMock(
            return_value=json.dumps([{"_number": 400, "plugins": []}])
        )
        fn = _capture_tools(ctx)["get_depends_on"]
        data = json.loads(await fn(change_id="400", gerrit_base_url=BASE_URL))
        assert data["depends_ons"] == []
        assert "note" in data

    @pytest.mark.asyncio
    async def test_empty_depends_ons(self, ctx):
        ctx.run_curl = AsyncMock(return_value=_wrap_response(500, []))
        fn = _capture_tools(ctx)["get_depends_on"]
        data = json.loads(await fn(change_id="500", gerrit_base_url=BASE_URL))
        assert data["depends_ons"] == []
        assert "note" not in data

    @pytest.mark.asyncio
    async def test_change_not_found(self, ctx):
        ctx.run_curl = AsyncMock(return_value="[]")
        fn = _capture_tools(ctx)["get_depends_on"]
        result = await fn(change_id="9999", gerrit_base_url=BASE_URL)
        assert "No change found" in result

    @pytest.mark.asyncio
    async def test_url_includes_depends_on_all_option(self, ctx):
        ctx.run_curl = AsyncMock(return_value=_wrap_response(200, []))
        fn = _capture_tools(ctx)["get_depends_on"]
        await fn(change_id="200", gerrit_base_url=BASE_URL)
        called_url = ctx.run_curl.call_args[0][0][0]
        assert "--depends-on--all" in called_url


# ---------------------------------------------------------------------------
# get_dependents
# ---------------------------------------------------------------------------


class TestGetDependents:
    @pytest.mark.asyncio
    async def test_returns_dependent_changes(self, ctx):
        ctx.run_curl = AsyncMock(
            return_value=json.dumps(
                [
                    {"_number": 200, "subject": "Dependent A"},
                    {"_number": 201, "subject": "Dependent B"},
                ]
            )
        )
        fn = _capture_tools(ctx)["get_dependents"]
        data = json.loads(await fn(change_id="100", gerrit_base_url=BASE_URL))
        assert data["change_id"] == "100"
        numbers = [c["_number"] for c in data["dependents"]]
        assert 200 in numbers
        assert 201 in numbers

    @pytest.mark.asyncio
    async def test_no_dependents(self, ctx):
        ctx.run_curl = AsyncMock(return_value="[]")
        fn = _capture_tools(ctx)["get_dependents"]
        data = json.loads(await fn(change_id="100", gerrit_base_url=BASE_URL))
        assert data["dependents"] == []

    @pytest.mark.asyncio
    async def test_url_uses_independson_query_operator(self, ctx):
        ctx.run_curl = AsyncMock(return_value="[]")
        fn = _capture_tools(ctx)["get_dependents"]
        await fn(change_id="100", gerrit_base_url=BASE_URL)
        called_url = ctx.run_curl.call_args[0][0][0]
        assert f"{quote('independson:100')}" in called_url
