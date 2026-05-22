from unittest.mock import AsyncMock, patch

import pytest

from gerrit_mcp_server import url_utilities


@pytest.fixture
def mock_exec():
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as m:
        yield m


@pytest.mark.asyncio
async def test_is_public_url_sends_ua(mock_exec):
    """is_public_url includes a User-Agent header in the curl command."""
    mock_exec.return_value.communicate.return_value = (b"HTTP/2 200 OK", b"")
    mock_exec.return_value.returncode = 0

    await url_utilities.is_public_url("https://example.com")

    cmd = mock_exec.call_args.args
    assert "-A" in cmd
    ua = cmd[cmd.index("-A") + 1]
    assert ua.startswith("gerrit-mcp-server/")
    assert "mcp-python-sdk/" in ua
    # No client token when obs=None
    assert "claude-code" not in ua
