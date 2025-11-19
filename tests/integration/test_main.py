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
import pytest
from unittest.mock import patch, AsyncMock
from gerrit_mcp_server import main

# --- Fixtures ---

@pytest.fixture(autouse=True)
def mock_env():
    """Sets up the environment variables for all tests in this module."""
    with patch.dict(os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}):
        yield

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

@pytest.fixture
def mock_load_config():
    """Provides a mocked load_gerrit_config."""
    with patch("gerrit_mcp_server.main.load_gerrit_config") as m:
        yield m

# --- Tests ---

@pytest.mark.asyncio
async def test_query_changes(mock_run_curl):
    """Tests querying changes from Gerrit."""
    mock_run_curl.return_value = json.dumps([
        {
            "_number": 1,
            "subject": "Test Change 1",
            "work_in_progress": False,
            "updated": "2025-07-02T12:00:00Z",
        },
        {
            "_number": 2,
            "subject": "Test Change 2",
            "work_in_progress": True,
            "updated": "2025-07-01T10:00:00Z",
        },
    ])

    result = await main.query_changes(
        gerrit_base_url="https://fuchsia-review.googlesource.com",
        query="status:open",
    )
    assert "Found 2 changes" in result[0]["text"]
    assert "1: Test Change 1" in result[0]["text"]
    assert "2: [WIP] Test Change 2" in result[0]["text"]

@pytest.mark.asyncio
async def test_query_changes_no_results(mock_run_curl):
    """Tests querying changes when no results are returned."""
    mock_run_curl.return_value = json.dumps([])
    result = await main.query_changes(
        gerrit_base_url="https://fuchsia-review.googlesource.com",
        query="status:open",
    )
    assert "No changes found" in result[0]["text"]

@pytest.mark.asyncio
async def test_get_change_details(mock_run_curl):
    """Tests retrieving details for a specific change."""
    mock_run_curl.return_value = json.dumps({
        "_number": 123,
        "subject": "Test Subject",
        "owner": {"email": "owner@example.com"},
        "status": "NEW",
        "reviewers": {
            "REVIEWER": [{"email": "reviewer@example.com", "_account_id": 1}]
        },
        "labels": {"Code-Review": {"all": [{"value": 1, "_account_id": 1}]}},
        "messages": [
            {"_revision_number": 1, "message": "First message"},
            {"_revision_number": 2, "message": "Second message"},
        ],
    })

    result = await main.get_change_details(
        gerrit_base_url="https://fuchsia-review.googlesource.com", change_id="123"
    )
    text = result[0]["text"]
    assert "Summary for CL 123" in text
    assert "Subject: Test Subject" in text
    assert "owner@example.com" in text
    assert "reviewer@example.com (Code-Review: +1)" in text
    assert "- (Patch Set 2) [No date] (Gerrit): Second message" in text

@pytest.mark.asyncio
async def test_get_change_details_missing_fields(mock_run_curl):
    """Tests retrieving change details when optional fields are missing."""
    mock_run_curl.return_value = json.dumps({
        "_number": 123,
        "subject": "Test Subject",
        "owner": {"email": "owner@example.com"},
        "status": "NEW",
    })
    result = await main.get_change_details(
        gerrit_base_url="https://fuchsia-review.googlesource.com", change_id="123"
    )
    text = result[0]["text"]
    assert "Summary for CL 123" in text
    assert "Reviewers:" not in text
    assert "Recent Messages:" not in text

@pytest.mark.asyncio
async def test_list_change_files(mock_run_curl):
    """Tests listing files in a change."""
    mock_run_curl.side_effect = [
        json.dumps({
            "/COMMIT_MSG": {},
            "file1.txt": {"status": "ADDED", "lines_inserted": 10, "lines_deleted": 0},
            "file2.txt": {"status": "MODIFIED", "lines_inserted": 5, "lines_deleted": 2},
        }),
        json.dumps({"current_revision_number": 3}),
    ]

    result = await main.list_change_files(
        gerrit_base_url="https://fuchsia-review.googlesource.com", change_id="123"
    )
    text = result[0]["text"]
    assert "Files in CL 123 (Patch Set 3)" in text
    assert "[A] file1.txt (+10, -0)" in text
    assert "[M] file2.txt (+5, -2)" in text
    assert "/COMMIT_MSG" not in text

@pytest.mark.asyncio
async def test_list_change_files_no_files(mock_run_curl):
    """Tests listing files when only COMMIT_MSG is present."""
    mock_run_curl.side_effect = [
        json.dumps({"/COMMIT_MSG": {}}),
        json.dumps({"current_revision_number": 1}),
    ]
    result = await main.list_change_files(
        gerrit_base_url="https://fuchsia-review.googlesource.com", change_id="123"
    )
    assert "Files in CL 123 (Patch Set 1)" in result[0]["text"]
    assert "[" not in result[0]["text"]

@pytest.mark.asyncio
async def test_get_file_diff(mock_run_curl):
    """Tests retrieving the diff of a file."""
    diff_text = "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1,1 +1,1 @@\n-hello\n+world"
    import base64
    encoded_diff = base64.b64encode(diff_text.encode("utf-8")).decode("utf-8")
    mock_run_curl.return_value = encoded_diff

    result = await main.get_file_diff(
        gerrit_base_url="https://fuchsia-review.googlesource.com",
        change_id="123",
        file_path="file.txt",
    )
    assert result[0]["text"] == diff_text

@pytest.mark.asyncio
async def test_list_change_comments(mock_run_curl):
    """Tests listing comments on a change."""
    mock_run_curl.return_value = json.dumps({
        "file1.txt": [
            {
                "line": 10,
                "author": {"name": "user1@example.com"},
                "message": "Comment 1",
                "unresolved": True,
                "updated": "2025-07-15T11:00:00Z",
            },
            {
                "line": 12,
                "author": {"name": "user2@example.com"},
                "message": "Comment 2",
                "unresolved": False,
                "updated": "2025-07-15T11:05:00Z",
            },
        ],
        "file2.txt": [
            {
                "line": 5,
                "author": {"name": "user1@example.com"},
                "message": "Comment 3",
                "unresolved": True,
                "updated": "2025-07-15T11:10:00Z",
            },
        ],
    })

    result = await main.list_change_comments(
        gerrit_base_url="https://fuchsia-review.googlesource.com", change_id="123"
    )
    text = result[0]["text"]
    assert "Comments for CL 123" in text
    assert "File: file1.txt" in text
    assert "L10: [user1@example.com] (2025-07-15T11:00:00Z) - UNRESOLVED" in text
    assert "Comment 1" in text
    assert "L12: [user2@example.com] (2025-07-15T11:05:00Z) - RESOLVED" in text
    assert "Comment 2" in text
    assert "File: file2.txt" in text
    assert "L5: [user1@example.com] (2025-07-15T11:10:00Z) - UNRESOLVED" in text
    assert "Comment 3" in text

@pytest.mark.asyncio
async def test_list_change_comments_no_unresolved(mock_run_curl):
    """Tests listing comments when all are resolved."""
    mock_run_curl.return_value = json.dumps({
        "file1.txt": [
            {
                "line": 12,
                "author": {"name": "user2@example.com"},
                "message": "Comment 2",
                "unresolved": False,
                "updated": "2025-07-15T11:05:00Z",
            },
        ]
    })
    result = await main.list_change_comments(
        gerrit_base_url="https://fuchsia-review.googlesource.com", change_id="123"
    )
    text = result[0]["text"]
    assert "Comments for CL 123" in text
    assert "L12: [user2@example.com] (2025-07-15T11:05:00Z) - RESOLVED" in text

@pytest.mark.asyncio
async def test_list_change_comments_json_decode_error(mock_run_curl):
    """Tests handling of invalid JSON response when listing comments."""
    mock_run_curl.return_value = "this is not json"
    result = await main.list_change_comments(
        gerrit_base_url="https://fuchsia-review.googlesource.com", change_id="123"
    )
    assert "Failed to parse JSON" in result[0]["text"]

@pytest.mark.asyncio
async def test_add_reviewer(mock_run_curl):
    """Tests adding a reviewer to a change."""
    mock_run_curl.return_value = json.dumps({})  # Empty object for success

    result = await main.add_reviewer(
        gerrit_base_url="https://fuchsia-review.googlesource.com",
        change_id="123",
        reviewer="reviewer@example.com",
    )
    assert "Successfully added reviewer@example.com as a REVIEWER to CL 123" in result[0]["text"]

@pytest.mark.asyncio
async def test_add_reviewer_failure(mock_run_curl):
    """Tests handling of failure when adding a reviewer."""
    mock_run_curl.return_value = '{"error": "Reviewer not found"}'
    result = await main.add_reviewer(
        gerrit_base_url="https://fuchsia-review.googlesource.com",
        change_id="123",
        reviewer="nonexistent@example.com",
    )
    assert "Failed to add" in result[0]["text"]
    assert "Reviewer not found" in result[0]["text"]

@pytest.mark.asyncio
async def test_get_most_recent_cl(mock_run_curl):
    """Tests retrieving the most recent CL for a user."""
    mock_run_curl.return_value = json.dumps([
        {
            "_number": 456,
            "subject": "Most Recent",
            "work_in_progress": False,
            "updated": "2025-07-02T13:00:00Z",
        },
    ])

    result = await main.get_most_recent_cl(
        gerrit_base_url="https://fuchsia-review.googlesource.com",
        user="owner@example.com",
    )
    assert "Most recent CL for owner@example.com" in result[0]["text"]
    assert "456: Most Recent" in result[0]["text"]

@pytest.mark.asyncio
async def test_add_reviewer_invalid_state(mock_run_curl):
    """Tests that adding a reviewer with an invalid state fails locally."""
    result = await main.add_reviewer(
        gerrit_base_url="https://fuchsia-review.googlesource.com",
        change_id="123",
        reviewer="reviewer@example.com",
        state="INVALID_STATE",
    )
    assert "Failed to add" in result[0]["text"]
    assert "Invalid state" in result[0]["text"]
    mock_run_curl.assert_not_called()

@pytest.mark.asyncio
async def test_get_most_recent_cl_no_results(mock_run_curl):
    """Tests retrieving the most recent CL when none exist."""
    mock_run_curl.return_value = json.dumps([])
    result = await main.get_most_recent_cl(
        gerrit_base_url="https://fuchsia-review.googlesource.com",
        user="owner@example.com",
    )
    assert "No changes found for user" in result[0]["text"]

@pytest.mark.asyncio
async def test_gerrit_base_url_override(mock_run_curl):
    """Tests that the environment variable overrides the default base URL."""
    mock_run_curl.return_value = json.dumps([])
    
    # We need to override the fixture's env var for this specific test
    with patch.dict(os.environ, {"GERRIT_BASE_URL": "https://another-gerrit.com"}):
        await main.query_changes(query="status:open")
        mock_run_curl.assert_called_once()
        assert "https://another-gerrit.com/changes" in mock_run_curl.call_args[0][0][0]

@pytest.mark.asyncio
async def test_run_curl_auth_error(mock_exec, mock_load_config):
    """Tests handling of authentication errors from curl."""
    mock_load_config.return_value = {
        "gerrit_hosts": [
            {
                "name": "Corporate",
                "external_url": "https://gerrit.private.corp.corporation.com/",
                "authentication": {"type": "gob_curl"},
            }
        ]
    }
    mock_exec.return_value.communicate.return_value = (
        b"",
        b"bad request: no valid session id provided",
    )
    mock_exec.return_value.returncode = 1

    with pytest.raises(Exception, match="curl command failed with exit code 1"):
        await main.run_curl(
            ["https://gerrit.private.corp.corporation.com/changes/123"],
            "https://gerrit.private.corp.corporation.com",
        )

@pytest.mark.asyncio
async def test_run_curl_generic_error(mock_exec, mock_load_config):
    """Tests handling of generic curl errors."""
    mock_load_config.return_value = {
        "gerrit_hosts": [
            {
                "name": "Fake",
                "external_url": "https://fakegerrit.com/",
                "authentication": {
                    "type": "git_cookies",
                    "gitcookies_path": "~/.gitcookies",
                },
            }
        ]
    }
    mock_exec.return_value.communicate.return_value = (
        b"",
        b"curl: (6) Could not resolve host: fakegerrit.com",
    )
    mock_exec.return_value.returncode = 6

    with pytest.raises(Exception, match="curl command failed with exit code 6"):
        await main.run_curl(["https://fakegerrit.com"], "https://fakegerrit.com")

@pytest.mark.asyncio
async def test_tool_functions_with_invalid_change_id(mock_run_curl):
    """Tests that tool functions handle invalid change IDs gracefully."""
    mock_run_curl.side_effect = Exception(
        "curl command failed with exit code 1.\nSTDERR:\nNot Found"
    )

    with pytest.raises(Exception, match="Not Found"):
        await main.get_change_details(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            change_id="invalid",
        )

    with pytest.raises(Exception, match="Not Found"):
        await main.list_change_files(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            change_id="invalid",
        )

    with pytest.raises(Exception, match="Not Found"):
        await main.get_file_diff(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            change_id="invalid",
            file_path="file.txt",
        )

    with pytest.raises(Exception, match="Not Found"):
        await main.list_change_comments(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            change_id="invalid",
        )

    with pytest.raises(Exception, match="Not Found"):
        await main.add_reviewer(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            change_id="invalid",
            reviewer="reviewer@example.com",
        )

@pytest.mark.asyncio
async def test_tool_functions_with_malformed_json(mock_run_curl):
    """Tests that tool functions handle malformed JSON responses."""
    mock_run_curl.return_value = "this is not json"

    result = await main.query_changes(
        gerrit_base_url="https://fuchsia-review.googlesource.com",
        query="status:open",
    )
    assert "Failed to parse JSON" in result[0]["text"]

@pytest.mark.asyncio
async def test_tool_functions_with_unexpected_json(mock_run_curl):
    """Tests that tool functions handle unexpected JSON structures."""
    mock_run_curl.return_value = json.dumps(
        {"unexpected_field": "unexpected_value"}
    )

    with pytest.raises(KeyError):
        await main.get_change_details(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            change_id="123",
        )

@pytest.mark.asyncio
async def test_concurrent_requests(mock_run_curl):
    """Tests that multiple requests can be handled concurrently."""
    mock_run_curl.return_value = json.dumps([])

    tasks = [
        main.query_changes(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            query="status:open",
        ),
        main.query_changes(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            query="status:merged",
        ),
    ]
    results = await asyncio.gather(*tasks)

    assert len(results) == 2
    assert mock_run_curl.call_count == 2

@pytest.mark.asyncio
async def test_command_injection(mock_exec):
    """Tests that the server is not vulnerable to command injection."""
    mock_exec.return_value.communicate.return_value = (b"[]", b"")
    mock_exec.return_value.returncode = 0

    await main.query_changes(
        gerrit_base_url="https://fuchsia-review.googlesource.com",
        query="status:open; rm -rf /",
    )

    # Check that the malicious command was not executed
    command_list = mock_exec.call_args[0][0]
    command_str = " ".join(command_list)
    assert ";" not in command_str
    assert "rm" not in command_str

@pytest.mark.asyncio
async def test_post_review_comment_with_labels(mock_run_curl):
    """Tests posting a review comment with labels."""
    mock_run_curl.return_value = ')]}\'\\n{"done": true}'

    result = await main.post_review_comment(
        gerrit_base_url="https://fuchsia-review.googlesource.com",
        change_id="123",
        file_path="/COMMIT_MSG",
        line_number=1,
        message="Setting Verified to +1",
        labels={"Verified": 1}
    )
    assert "Successfully posted comment" in result[0]["text"]
    
    # Verify the JSON payload sent to Gerrit
    expected_payload = {
        "comments": {
            "/COMMIT_MSG": [{
                "line": 1,
                "message": "Setting Verified to +1",
                "unresolved": True
            }]
        },
        "labels": {"Verified": 1}
    }    
    # The payload is passed as the argument after '--data'
    curl_args = mock_run_curl.call_args[0][0]
    data_index = curl_args.index("--data")
    actual_payload_str = curl_args[data_index + 1]
    actual_payload = json.loads(actual_payload_str)
    
    assert actual_payload == expected_payload

