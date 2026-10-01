# Copyright 2026 Google LLC
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

import json
from unittest.mock import AsyncMock, patch

import pytest

from gerrit_mcp_server import main

BASE_URL = "https://gerrit.example.com"
REVIEW_URL = f"{BASE_URL}/changes/123/revisions/current/review"


@pytest.fixture
def mock_run_curl():
    with patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock) as m:
        yield m


def _sent_payload(mock_run_curl):
    curl_args = mock_run_curl.call_args[0][0]
    return json.loads(curl_args[curl_args.index("--data") + 1])


@pytest.mark.asyncio
async def test_post_review_comments_groups_by_file_in_one_request(mock_run_curl):
    mock_run_curl.return_value = "{}"
    comments = [
        {"file_path": "a.py", "line_number": 1, "message": "first"},
        {"file_path": "b.py", "line_number": 5, "message": "second"},
        {
            "file_path": "a.py",
            "line_number": 9,
            "message": "third",
            "unresolved": False,
        },
    ]

    result = await main.post_review_comments("123", comments, gerrit_base_url=BASE_URL)

    assert result == {
        "change_id": "123",
        "comment_count": 3,
        "file_count": 2,
        "message": None,
        "labels": None,
        "note": None,
    }
    mock_run_curl.assert_called_once()
    curl_args, base_url = mock_run_curl.call_args[0]
    assert curl_args[:2] == ["-X", "POST"]
    assert curl_args[-1] == REVIEW_URL
    assert base_url == BASE_URL
    assert _sent_payload(mock_run_curl) == {
        "comments": {
            "a.py": [
                {"line": 1, "message": "first", "unresolved": True},
                {"line": 9, "message": "third", "unresolved": False},
            ],
            "b.py": [{"line": 5, "message": "second", "unresolved": True}],
        }
    }


@pytest.mark.asyncio
async def test_post_review_comments_with_message_and_labels(mock_run_curl):
    mock_run_curl.return_value = '{"labels": {"Code-Review": -1}}'

    result = await main.post_review_comments(
        "123",
        [{"file_path": "a.py", "line_number": 3, "message": "nit"}],
        message="Please address the nits.",
        labels={"Code-Review": -1},
        gerrit_base_url=BASE_URL,
    )

    assert result["message"] == "Please address the nits."
    assert result["labels"] == {"Code-Review": -1}
    assert result["note"] is None
    mock_run_curl.assert_called_once()
    payload = _sent_payload(mock_run_curl)
    assert payload["message"] == "Please address the nits."
    assert payload["labels"] == {"Code-Review": -1}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "labels, response_labels, expected_note",
    [
        # Gerrit ignores a vote outside the label's range.
        ({"Code-Review": 5}, {}, "did not apply these votes: Code-Review 5"),
        # Only the votes Gerrit did not apply are reported.
        (
            {"Code-Review": -1, "Verified": 1},
            {"Code-Review": -1},
            "did not apply these votes: Verified 1",
        ),
    ],
)
async def test_post_review_comments_reports_votes_not_applied(
    mock_run_curl, labels, response_labels, expected_note
):
    mock_run_curl.return_value = json.dumps({"labels": response_labels})

    result = await main.post_review_comments(
        "123",
        [{"file_path": "a.py", "line_number": 3, "message": "nit"}],
        labels=labels,
        gerrit_base_url=BASE_URL,
    )

    assert result["comment_count"] == 1
    assert result["labels"] == response_labels
    assert result["note"].startswith("Comments were posted")
    assert expected_note in result["note"]
    mock_run_curl.assert_called_once()


@pytest.mark.asyncio
async def test_post_review_comments_empty_list_raises(mock_run_curl):
    with pytest.raises(ValueError, match="No comments provided"):
        await main.post_review_comments("123", [], gerrit_base_url=BASE_URL)
    mock_run_curl.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_comment, expected_error",
    [
        ({"line_number": 1, "message": "m"}, "'file_path'"),
        ({"file_path": "a.py", "message": "m"}, "'line_number'"),
        ({"file_path": "a.py", "line_number": 0, "message": "m"}, "'line_number'"),
        ({"file_path": "a.py", "line_number": True, "message": "m"}, "'line_number'"),
        ({"file_path": "a.py", "line_number": 1}, "'message'"),
        ({"file_path": "a.py", "line_number": 1, "message": ""}, "'message'"),
        (
            {
                "file_path": "a.py",
                "line_number": 1,
                "message": "m",
                "unresolved": "false",
            },
            "'unresolved'",
        ),
        (
            {"file_path": "a.py", "line_number": 1, "message": "m", "unresolved": 0},
            "'unresolved'",
        ),
        (
            {"file_path": "a.py", "line_number": 1, "message": "m", "unresolved": None},
            "'unresolved'",
        ),
        ("not a dict", "must be an object"),
    ],
)
async def test_post_review_comments_invalid_input_sends_nothing(
    mock_run_curl, bad_comment, expected_error
):
    comments = [
        {"file_path": "ok.py", "line_number": 1, "message": "valid"},
        bad_comment,
    ]

    with pytest.raises(ValueError) as excinfo:
        await main.post_review_comments("123", comments, gerrit_base_url=BASE_URL)

    assert "nothing was posted" in str(excinfo.value)
    assert "comment 1:" in str(excinfo.value)
    assert expected_error in str(excinfo.value)
    mock_run_curl.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response, expected_error",
    [
        ("file missing.py not found in revision 1,1", "file missing.py not found"),
        ('{"error": "Invalid label"}', "Invalid label"),
        ("[]", "Unexpected response"),
    ],
)
async def test_post_review_comments_gerrit_error_raises(
    mock_run_curl, response, expected_error
):
    mock_run_curl.return_value = response

    with pytest.raises(RuntimeError, match=expected_error):
        await main.post_review_comments(
            "123",
            [{"file_path": "missing.py", "line_number": 1, "message": "m"}],
            gerrit_base_url=BASE_URL,
        )


@pytest.mark.asyncio
async def test_post_review_comments_curl_exception_is_raised(mock_run_curl):
    mock_run_curl.side_effect = Exception("curl failed")

    with pytest.raises(Exception, match="curl failed"):
        await main.post_review_comments(
            "123",
            [{"file_path": "a.py", "line_number": 1, "message": "m"}],
            gerrit_base_url=BASE_URL,
        )


@pytest.mark.asyncio
async def test_post_review_comments_mcp_schemas():
    tools = {tool.name: tool for tool in await main.mcp.list_tools()}
    tool = tools["post_review_comments"]

    # Structured output, like the other TypedDict tools.
    assert tool.outputSchema is not None
    assert set(tool.outputSchema["properties"]) == {
        "change_id",
        "comment_count",
        "file_count",
        "message",
        "labels",
        "note",
    }

    # Each comment is a typed object, not an unconstrained dict.
    items_ref = tool.inputSchema["properties"]["comments"]["items"]["$ref"]
    comment_schema = tool.inputSchema["$defs"][items_ref.split("/")[-1]]
    assert set(comment_schema["required"]) == {"file_path", "line_number", "message"}
    assert comment_schema["properties"]["line_number"]["type"] == "integer"
    assert comment_schema["properties"]["unresolved"]["type"] == "boolean"
