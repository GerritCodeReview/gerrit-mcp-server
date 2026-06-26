import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import quote

import pytest

from gerrit_mcp_server_code_owners.extension import register

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


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------


class TestRegister:
    def test_registers_three_tools(self, ctx):
        register(ctx)
        assert ctx.mcp.tool.call_count == 3


# ---------------------------------------------------------------------------
# get_code_owner_status
# ---------------------------------------------------------------------------


class TestGetCodeOwnerStatus:
    def _make_status_response(self, patch_set=1, files=None, more=False):
        data = {
            "patchSetNumber": patch_set,
            "fileCodeOwnerStatuses": files or [],
        }
        if more:
            data["more"] = True
        return json.dumps(data)

    @pytest.mark.asyncio
    async def test_approved_file(self, ctx):
        ctx.run_curl = AsyncMock(
            return_value=self._make_status_response(
                patch_set=2,
                files=[
                    {
                        "changeType": "MODIFIED",
                        "newPathStatus": {
                            "path": "src/foo.py",
                            "status": "APPROVED",
                        },
                    }
                ],
            )
        )
        fn = _capture_tools(ctx)["get_code_owner_status"]
        data = await fn(change_id="100", gerrit_base_url=BASE_URL)
        assert data["change_id"] == "100"
        assert data["patch_set_number"] == 2
        assert len(data["file_code_owner_statuses"]) == 1
        status = data["file_code_owner_statuses"][0]
        assert status["change_type"] == "MODIFIED"
        assert status["new_path_status"]["path"] == "src/foo.py"
        assert status["new_path_status"]["status"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_pending_file_with_reasons(self, ctx):
        ctx.run_curl = AsyncMock(
            return_value=self._make_status_response(
                files=[
                    {
                        "newPathStatus": {
                            "path": "src/bar.py",
                            "status": "PENDING",
                            "reasons": ["<GERRIT_ACCOUNT_1> is a reviewer"],
                        },
                    }
                ],
            )
        )
        fn = _capture_tools(ctx)["get_code_owner_status"]
        data = await fn(change_id="200", gerrit_base_url=BASE_URL)
        path_status = data["file_code_owner_statuses"][0]["new_path_status"]
        assert path_status["status"] == "PENDING"
        assert len(path_status["reasons"]) == 1

    @pytest.mark.asyncio
    async def test_renamed_file_has_old_and_new_path(self, ctx):
        ctx.run_curl = AsyncMock(
            return_value=self._make_status_response(
                files=[
                    {
                        "changeType": "RENAMED",
                        "oldPathStatus": {"path": "old/path.py", "status": "APPROVED"},
                        "newPathStatus": {"path": "new/path.py", "status": "APPROVED"},
                    }
                ],
            )
        )
        fn = _capture_tools(ctx)["get_code_owner_status"]
        data = await fn(change_id="300", gerrit_base_url=BASE_URL)
        entry = data["file_code_owner_statuses"][0]
        assert entry["old_path_status"]["path"] == "old/path.py"
        assert entry["new_path_status"]["path"] == "new/path.py"

    @pytest.mark.asyncio
    async def test_more_flag_included_when_true(self, ctx):
        ctx.run_curl = AsyncMock(return_value=self._make_status_response(more=True))
        fn = _capture_tools(ctx)["get_code_owner_status"]
        data = await fn(change_id="400", gerrit_base_url=BASE_URL)
        assert data.get("more") is True

    @pytest.mark.asyncio
    async def test_more_flag_absent_when_false(self, ctx):
        ctx.run_curl = AsyncMock(return_value=self._make_status_response(more=False))
        fn = _capture_tools(ctx)["get_code_owner_status"]
        data = await fn(change_id="400", gerrit_base_url=BASE_URL)
        assert "more" not in data

    @pytest.mark.asyncio
    async def test_limit_and_start_in_url(self, ctx):
        ctx.run_curl = AsyncMock(return_value=self._make_status_response())
        fn = _capture_tools(ctx)["get_code_owner_status"]
        await fn(change_id="500", limit=10, start=5, gerrit_base_url=BASE_URL)
        called_url = ctx.run_curl.call_args[0][0][0]
        assert "-n=10" in called_url
        assert "-S=5" in called_url

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self, ctx):
        ctx.run_curl = AsyncMock(return_value="not json")
        fn = _capture_tools(ctx)["get_code_owner_status"]
        with pytest.raises(ValueError, match="Could not parse"):
            await fn(change_id="999", gerrit_base_url=BASE_URL)


# ---------------------------------------------------------------------------
# get_code_owners_for_path
# ---------------------------------------------------------------------------


class TestGetCodeOwnersForPath:
    def _make_owners_response(self, owners=None, owned_by_all=False):
        data = {"code_owners": owners or []}
        if owned_by_all:
            data["owned_by_all_users"] = True
        return json.dumps(data)

    @pytest.mark.asyncio
    async def test_returns_owners(self, ctx):
        ctx.run_curl = AsyncMock(
            return_value=self._make_owners_response(
                owners=[
                    {
                        "account": {
                            "_account_id": 42,
                            "name": "Alice",
                            "email": "alice@example.com",
                        },
                        "scorings": {"IS_REVIEWER": 1},
                    }
                ]
            )
        )
        fn = _capture_tools(ctx)["get_code_owners_for_path"]
        data = await fn(
            change_id="100",
            path="src/foo.py",
            gerrit_base_url=BASE_URL,
        )
        assert data["change_id"] == "100"
        assert data["path"] == "src/foo.py"
        assert data["revision_id"] == "current"
        assert len(data["code_owners"]) == 1
        owner = data["code_owners"][0]
        assert owner["account"]["account_id"] == 42
        assert owner["account"]["name"] == "Alice"
        assert owner["scorings"] == {"IS_REVIEWER": 1}

    @pytest.mark.asyncio
    async def test_owned_by_all_users(self, ctx):
        ctx.run_curl = AsyncMock(
            return_value=self._make_owners_response(owned_by_all=True)
        )
        fn = _capture_tools(ctx)["get_code_owners_for_path"]
        data = await fn(
            change_id="100",
            path="OWNERS",
            gerrit_base_url=BASE_URL,
        )
        assert data.get("owned_by_all_users") is True

    @pytest.mark.asyncio
    async def test_owned_by_all_users_absent_when_false(self, ctx):
        ctx.run_curl = AsyncMock(return_value=self._make_owners_response())
        fn = _capture_tools(ctx)["get_code_owners_for_path"]
        data = await fn(
            change_id="100",
            path="src/foo.py",
            gerrit_base_url=BASE_URL,
        )
        assert "owned_by_all_users" not in data

    @pytest.mark.asyncio
    async def test_url_contains_path(self, ctx):
        ctx.run_curl = AsyncMock(return_value=self._make_owners_response())
        fn = _capture_tools(ctx)["get_code_owners_for_path"]
        await fn(
            change_id="100",
            path="src/my file.py",
            revision_id="abc123",
            gerrit_base_url=BASE_URL,
        )
        called_url = ctx.run_curl.call_args[0][0][0]
        assert "abc123" in called_url
        assert "src/my%20file.py" in called_url

    @pytest.mark.asyncio
    async def test_leading_slash_stripped_from_path(self, ctx):
        ctx.run_curl = AsyncMock(return_value=self._make_owners_response())
        fn = _capture_tools(ctx)["get_code_owners_for_path"]
        await fn(
            change_id="100",
            path="/src/foo.py",
            gerrit_base_url=BASE_URL,
        )
        called_url = ctx.run_curl.call_args[0][0][0]
        assert "//src" not in called_url

    @pytest.mark.asyncio
    async def test_limit_in_url(self, ctx):
        ctx.run_curl = AsyncMock(return_value=self._make_owners_response())
        fn = _capture_tools(ctx)["get_code_owners_for_path"]
        await fn(
            change_id="100",
            path="src/foo.py",
            limit=5,
            gerrit_base_url=BASE_URL,
        )
        called_url = ctx.run_curl.call_args[0][0][0]
        assert "-n=5" in called_url

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self, ctx):
        ctx.run_curl = AsyncMock(return_value="not json")
        fn = _capture_tools(ctx)["get_code_owners_for_path"]
        with pytest.raises(ValueError, match="Could not parse"):
            await fn(change_id="100", path="src/foo.py", gerrit_base_url=BASE_URL)


# ---------------------------------------------------------------------------
# check_code_owner
# ---------------------------------------------------------------------------


class TestCheckCodeOwner:
    def _make_check_response(self, is_code_owner=True, is_resolvable=True, **kwargs):
        data = {
            "is_code_owner": is_code_owner,
            "is_resolvable": is_resolvable,
        }
        data.update(kwargs)
        return json.dumps(data)

    @pytest.mark.asyncio
    async def test_is_code_owner(self, ctx):
        ctx.run_curl = AsyncMock(
            return_value=self._make_check_response(
                is_code_owner=True,
                is_resolvable=True,
                can_read_ref=True,
                can_approve_change=True,
            )
        )
        fn = _capture_tools(ctx)["check_code_owner"]
        data = await fn(
            project="my/project",
            branch="main",
            path="src/foo.py",
            email="alice@example.com",
            gerrit_base_url=BASE_URL,
        )
        assert data["project"] == "my/project"
        assert data["branch"] == "main"
        assert data["path"] == "src/foo.py"
        assert data["email"] == "alice@example.com"
        assert data["is_code_owner"] is True
        assert data["is_resolvable"] is True
        assert data["can_read_ref"] is True
        assert data["can_approve_change"] is True

    @pytest.mark.asyncio
    async def test_not_code_owner(self, ctx):
        ctx.run_curl = AsyncMock(
            return_value=self._make_check_response(
                is_code_owner=False,
                is_resolvable=True,
            )
        )
        fn = _capture_tools(ctx)["check_code_owner"]
        data = await fn(
            project="my/project",
            branch="main",
            path="src/bar.py",
            email="bob@example.com",
            gerrit_base_url=BASE_URL,
        )
        assert data["is_code_owner"] is False

    @pytest.mark.asyncio
    async def test_fallback_owner_fields(self, ctx):
        ctx.run_curl = AsyncMock(
            return_value=self._make_check_response(
                is_fallback_code_owner=True,
                is_global_code_owner=False,
                is_default_code_owner=False,
                annotations=["FALLBACK_CODE_OWNER"],
            )
        )
        fn = _capture_tools(ctx)["check_code_owner"]
        data = await fn(
            project="my/project",
            branch="main",
            path="src/baz.py",
            email="charlie@example.com",
            gerrit_base_url=BASE_URL,
        )
        assert data["is_fallback_code_owner"] is True
        assert data["annotations"] == ["FALLBACK_CODE_OWNER"]

    @pytest.mark.asyncio
    async def test_url_contains_email_and_path(self, ctx):
        ctx.run_curl = AsyncMock(return_value=self._make_check_response())
        fn = _capture_tools(ctx)["check_code_owner"]
        await fn(
            project="my/project",
            branch="main",
            path="src/foo.py",
            email="alice@example.com",
            gerrit_base_url=BASE_URL,
        )
        called_url = ctx.run_curl.call_args[0][0][0]
        assert quote("alice@example.com") in called_url
        assert quote("src/foo.py") in called_url
        assert "code_owners.check" in called_url

    @pytest.mark.asyncio
    async def test_change_id_appended_to_url(self, ctx):
        ctx.run_curl = AsyncMock(return_value=self._make_check_response())
        fn = _capture_tools(ctx)["check_code_owner"]
        await fn(
            project="my/project",
            branch="main",
            path="src/foo.py",
            email="alice@example.com",
            change_id="123",
            gerrit_base_url=BASE_URL,
        )
        called_url = ctx.run_curl.call_args[0][0][0]
        assert "--change=123" in called_url

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self, ctx):
        ctx.run_curl = AsyncMock(return_value="not json")
        fn = _capture_tools(ctx)["check_code_owner"]
        with pytest.raises(ValueError, match="Could not parse"):
            await fn(
                project="p",
                branch="b",
                path="f",
                email="e@x.com",
                gerrit_base_url=BASE_URL,
            )
