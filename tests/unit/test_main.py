# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import json
import os
from unittest.mock import AsyncMock, patch

import pytest

from gerrit_mcp_server import main

# --- Fixtures ---


@pytest.fixture
def mock_load_config():
    """Provides a mocked load_gerrit_config."""
    with patch("gerrit_mcp_server.main.load_gerrit_config") as m:
        yield m


@pytest.fixture
def mock_run_curl():
    """Provides a mocked run_curl."""
    with patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture
def mock_exec():
    """Provides a mocked asyncio.create_subprocess_exec."""
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as m:
        yield m


# --- Tests ---


def test_get_gerrit_base_url_with_env_var():
    """Tests that the base URL is retrieved from the environment variable."""
    with patch.dict(os.environ, {"GERRIT_BASE_URL": "https://another-gerrit.com"}):
        assert main._get_gerrit_base_url() == "https://another-gerrit.com"


def test_get_gerrit_base_url_with_parameter(mock_load_config):
    """Tests that the provided parameter overrides the configuration."""
    assert (
        main._get_gerrit_base_url("https://parameter-gerrit.com")
        == "https://parameter-gerrit.com"
    )
    mock_load_config.assert_not_called()


@pytest.mark.parametrize(
    "input_url, expected",
    [
        (
            "fuchsia-review.git.private.corporation.com",
            "https://fuchsia-review.googlesource.com",
        ),
        (
            "https://fuchsia-review.git.private.corporation.com",
            "https://fuchsia-review.googlesource.com",
        ),
        ("fuchsia-review.googlesource.com", "https://fuchsia-review.googlesource.com"),
        ("another-gerrit.com", "https://another-gerrit.com"),
        ("http://another-gerrit.com", "https://another-gerrit.com"),
        ("https://another-gerrit.com", "https://another-gerrit.com"),
    ],
)
def test_normalize_gerrit_url(mock_load_config, input_url, expected):
    """Tests that URLs are correctly normalized based on the configuration."""
    mock_load_config.return_value = {
        "gerrit_hosts": [
            {
                "name": "Fuchsia",
                "internal_url": "https://fuchsia-review.git.private.corporation.com/",
                "external_url": "https://fuchsia-review.googlesource.com/",
            }
        ]
    }
    gerrit_hosts = mock_load_config.return_value["gerrit_hosts"]
    assert main._normalize_gerrit_url(input_url, gerrit_hosts) == expected


def test_build_extension_context_get_base_url_applies_auth_prefix(mock_load_config):
    """The extension context's get_base_url must normalize and apply the /a auth
    prefix, mirroring the core tools, so extensions hit the authenticated endpoint."""
    mock_load_config.return_value = {
        "gerrit_hosts": [
            {
                "name": "ReviewAndroid",
                "external_url": "https://review-android.example.com/",
                "authentication": {"type": "http_basic"},
            }
        ]
    }

    ctx = main._build_extension_context()

    assert (
        ctx.get_base_url("https://review-android.example.com")
        == "https://review-android.example.com/a"
    )


def test_build_extension_context_get_base_url_no_prefix_for_anonymous(mock_load_config):
    """A host without http_basic/git_cookies auth gets no /a prefix."""
    mock_load_config.return_value = {
        "gerrit_hosts": [
            {
                "name": "Public",
                "external_url": "https://public-review.example.com/",
            }
        ]
    }

    ctx = main._build_extension_context()

    assert (
        ctx.get_base_url("https://public-review.example.com")
        == "https://public-review.example.com"
    )


@pytest.mark.parametrize(
    "exc,expected_code",
    [
        (FileNotFoundError("no config"), 1),
        (ValueError("bad default url"), 2),
        (json.JSONDecodeError("bad json", "doc", 0), 2),
    ],
)
def test_cli_main_exits_cleanly_on_config_error(exc, expected_code):
    """A config error while building the extension context must produce a
    clean message and exit code, not an unhandled traceback that aborts
    startup with a stack trace."""
    with (
        patch("gerrit_mcp_server.main._build_extension_context", side_effect=exc),
        patch("gerrit_mcp_server.main.ExtensionLoader") as mock_loader,
        patch("gerrit_mcp_server.main.mcp") as mock_mcp,
    ):
        with pytest.raises(SystemExit) as excinfo:
            main.cli_main(["gerrit-mcp-server", "stdio"])
    assert excinfo.value.code == expected_code
    mock_loader.assert_not_called()
    mock_mcp.run.assert_not_called()


def test_cli_main_starts_when_context_builds(mock_load_config):
    """When the context builds cleanly, extensions load and the transport runs."""
    mock_load_config.return_value = {"gerrit_hosts": []}
    with (
        patch("gerrit_mcp_server.main.ExtensionLoader") as mock_loader,
        patch("gerrit_mcp_server.main.mcp") as mock_mcp,
    ):
        main.cli_main(["gerrit-mcp-server", "stdio"])
    mock_loader.return_value.load.assert_called_once()
    mock_mcp.run.assert_called_once_with(transport="stdio")


def test_load_gerrit_config_not_found():
    """Tests that FileNotFoundError is raised when the config file is missing."""
    with patch("gerrit_mcp_server.main.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError):
            main.load_gerrit_config()


def test_load_gerrit_config_with_env_var():
    """Tests loading the configuration from a path specified
    in an environment variable."""
    with patch(
        "builtins.open", new_callable=AsyncMock
    ):  # using AsyncMock just for convenience of mocking, though it's sync open
        # Actually, builtins.open is sync. Let's use mock_open properly.
        from unittest.mock import mock_open as sync_mock_open

        m = sync_mock_open(read_data='{"key": "value"}')
        with (
            patch("builtins.open", m),
            patch("pathlib.Path.exists", return_value=True),
            patch.dict(
                os.environ, {"GERRIT_CONFIG_PATH": "/fake/path/gerrit_config.json"}
            ),
        ):
            config = main.load_gerrit_config()
            assert config == {"key": "value"}


def test_get_gerrit_base_url_with_no_env_var(mock_load_config):
    """Tests that the default base URL is used when no environment variable is set."""
    with patch.dict(os.environ, {}, clear=True):
        mock_load_config.return_value = {
            "default_gerrit_base_url": "https://fuchsia-review.googlesource.com",
            "gerrit_hosts": [
                {"external_url": "https://fuchsia-review.googlesource.com"}
            ],
        }
        assert main._get_gerrit_base_url() == "https://fuchsia-review.googlesource.com"


@pytest.mark.asyncio
async def test_run_curl_timeout(mock_exec, mock_load_config):
    """Tests that a TimeoutError is raised when the curl command times out."""
    mock_load_config.return_value = {
        "gerrit_hosts": [
            {
                "external_url": "https://example.com",
                "authentication": {"type": "gob_curl"},
            }
        ]
    }
    mock_exec.return_value.communicate.side_effect = asyncio.TimeoutError

    with pytest.raises(asyncio.TimeoutError):
        await main.run_curl(["https://example.com"], "https://example.com")


@pytest.mark.asyncio
async def test_run_curl_large_output(mock_exec, mock_load_config):
    """Tests handling of large output from the curl command."""
    mock_load_config.return_value = {
        "gerrit_hosts": [
            {
                "external_url": "https://example.com",
                "authentication": {"type": "gob_curl"},
            }
        ]
    }
    large_output = "a" * 10000
    mock_exec.return_value.communicate.return_value = (large_output.encode(), b"")
    mock_exec.return_value.returncode = 0

    result = await main.run_curl(["https://example.com"], "https://example.com")
    assert result == large_output


@pytest.mark.asyncio
async def test_run_curl_non_zero_exit(mock_exec, mock_load_config):
    """Tests that an exception is raised when the curl command exits
    with a non-zero code."""
    mock_load_config.return_value = {
        "gerrit_hosts": [
            {
                "external_url": "https://example.com",
                "authentication": {"type": "gob_curl"},
            }
        ]
    }
    mock_exec.return_value.communicate.return_value = (b"", b"error")
    mock_exec.return_value.returncode = 1

    with pytest.raises(Exception):
        await main.run_curl(["https://example.com"], "https://example.com")


@pytest.mark.asyncio
async def test_run_curl_removes_gerrit_prefix(mock_exec, mock_load_config):
    """Tests that the Gerrit JSON prefix is removed from the response."""
    mock_load_config.return_value = {
        "gerrit_hosts": [
            {
                "external_url": "https://example.com",
                "authentication": {"type": "gob_curl"},
            }
        ]
    }
    mock_exec.return_value.communicate.return_value = (b')]}\'\n{"key": "value"}', b"")
    mock_exec.return_value.returncode = 0

    result = await main.run_curl(["https://example.com"], "https://example.com")
    assert result == '{"key": "value"}'


@pytest.mark.asyncio
async def test_get_bugs_from_cl_with_one_bug(mock_run_curl):
    """Tests extracting a single bug ID from a CL message."""
    mock_run_curl.return_value = '{"message": "Fixes: b/12345"}'
    result = await main.get_bugs_from_cl("123")
    assert "Found bug(s): 12345" in result[0]["text"]


@pytest.mark.asyncio
async def test_get_bugs_from_cl_with_multiple_bugs(mock_run_curl):
    """Tests extracting multiple bug IDs from a CL message."""
    mock_run_curl.return_value = '{"message": "Fixes: b/12345, b/67890"}'
    result = await main.get_bugs_from_cl("123")
    assert "Found bug(s): 12345, 67890" in result[0]["text"]


@pytest.mark.asyncio
async def test_get_bugs_from_cl_no_bugs(mock_run_curl):
    """Tests that the correct message is returned when no bugs are found."""
    mock_run_curl.return_value = '{"message": "No bugs here"}'
    result = await main.get_bugs_from_cl("123")
    assert "No bug IDs found" in result[0]["text"]


@pytest.mark.asyncio
async def test_get_bugs_from_cl_no_commit_message(mock_run_curl):
    """Tests handling of a missing commit message."""
    mock_run_curl.return_value = "{}"
    result = await main.get_bugs_from_cl("123")
    assert "No commit message found" in result[0]["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unresolved_arg, expected_unresolved",
    [
        (None, True),  # Default
        (False, False),
        (True, True),
    ],
)
async def test_post_review_comment(mock_run_curl, unresolved_arg, expected_unresolved):
    """Tests posting a review comment with different 'unresolved' states."""
    mock_run_curl.return_value = '{"comments": {}}'

    kwargs = {}
    if unresolved_arg is not None:
        kwargs["unresolved"] = unresolved_arg

    result = await main.post_review_comment(
        "123", "file.py", 10, "test comment", **kwargs
    )

    assert "Successfully posted comment" in result[0]["text"]

    # Verify the payload
    args, _ = mock_run_curl.call_args
    curl_args = args[0]
    data_index = curl_args.index("--data")
    request_body = json.loads(curl_args[data_index + 1])
    assert request_body["comments"]["file.py"][0]["unresolved"] is expected_unresolved


@pytest.mark.asyncio
async def test_post_review_comment_failure(mock_run_curl):
    """Tests handling of a failure response when posting a comment."""
    mock_run_curl.return_value = '{"error": "failed"}'
    result = await main.post_review_comment("123", "file.py", 10, "test comment")
    assert "Failed to post comment" in result[0]["text"]


# --- Edge Case Tests ---


@pytest.mark.asyncio
async def test_get_change_details_handles_missing_reviewers(mock_run_curl):
    """Tests that get_change_details handles missing 'reviewers' field gracefully."""
    mock_run_curl.return_value = json.dumps(
        {
            "_number": 123,
            "subject": "Test",
            "owner": {"email": "a@b.com"},
            "status": "NEW",
        }
    )
    result = await main.get_change_details("123")
    assert "Reviewers:" not in result[0]["text"]


@pytest.mark.asyncio
async def test_get_change_details_handles_empty_reviewers_list(mock_run_curl):
    """Tests that get_change_details handles an empty reviewers list gracefully."""
    mock_run_curl.return_value = json.dumps(
        {
            "_number": 123,
            "subject": "Test",
            "owner": {"email": "a@b.com"},
            "status": "NEW",
            "reviewers": {"REVIEWER": []},
        }
    )
    result = await main.get_change_details("123")
    assert "Reviewers:" in result[0]["text"]


@pytest.mark.asyncio
async def test_run_curl_sends_static_ua_when_no_context(mock_exec, mock_load_config):
    """run_curl always includes a User-Agent even without MCP context."""
    mock_load_config.return_value = {
        "gerrit_hosts": [
            {
                "external_url": "https://example.com",
                "authentication": {"type": "gob_curl"},
            }
        ]
    }
    mock_exec.return_value.communicate.return_value = (b"ok", b"")
    mock_exec.return_value.returncode = 0

    await main.run_curl(["https://example.com"], "https://example.com")

    cmd = mock_exec.call_args.args
    assert "-A" in cmd
    ua = cmd[cmd.index("-A") + 1]
    assert ua.startswith("gerrit-mcp-server/")
    assert "mcp-python-sdk/" in ua


@pytest.mark.asyncio
async def test_run_curl_sends_x_mcp_tool_when_context_set(mock_exec, mock_load_config):
    """run_curl includes X-MCP-Tool header when _request_obs contextvar is set."""
    from gerrit_mcp_server.http_headers import RequestObservabilityContext, _request_obs

    mock_load_config.return_value = {
        "gerrit_hosts": [
            {
                "external_url": "https://example.com",
                "authentication": {"type": "gob_curl"},
            }
        ]
    }
    mock_exec.return_value.communicate.return_value = (b"ok", b"")
    mock_exec.return_value.returncode = 0

    obs = RequestObservabilityContext(
        tool_name="query_changes",
        client_name="test-client",
        client_version="1.0",
        protocol_version="2025-11-25",
    )
    token = _request_obs.set(obs)
    try:
        await main.run_curl(["https://example.com"], "https://example.com")
    finally:
        _request_obs.reset(token)

    cmd = mock_exec.call_args.args
    assert "-H" in cmd
    headers = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-H"]
    assert any(h == "X-MCP-Tool: query_changes" for h in headers)
    assert any(h == "X-MCP-Client: test-client" for h in headers)
    assert any(h == "X-MCP-Protocol-Version: 2025-11-25" for h in headers)


@pytest.mark.asyncio
async def test_list_change_files_handles_empty_response(mock_run_curl):
    """Tests that list_change_files handles an empty response gracefully."""
    mock_run_curl.side_effect = [
        json.dumps({}),
        json.dumps({"current_revision_number": 1}),
    ]
    result = await main.list_change_files("123")
    assert "Files in CL 123 (Patch Set 1)" in result[0]["text"]
    assert "[" not in result[0]["text"]
