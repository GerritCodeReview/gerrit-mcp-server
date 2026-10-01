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

BASE_URL = "https://gerrit-review.googlesource.com"
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

    assert "Successfully posted 3 comment(s) across 2 file(s)" in result[0]["text"]
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

    assert "Successfully posted 1 comment(s)" in result[0]["text"]
    payload = _sent_payload(mock_run_curl)
    assert payload["message"] == "Please address the nits."
    assert payload["labels"] == {"Code-Review": -1}


@pytest.mark.asyncio
async def test_post_review_comments_empty_list_sends_nothing(mock_run_curl):
    result = await main.post_review_comments("123", [], gerrit_base_url=BASE_URL)

    assert "No comments provided" in result[0]["text"]
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

    result = await main.post_review_comments("123", comments, gerrit_base_url=BASE_URL)

    text = result[0]["text"]
    assert "nothing was posted" in text
    assert "Comment 1:" in text
    assert expected_error in text
    mock_run_curl.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        "file not found: missing.py",
        '{"error": "Invalid label"}',
    ],
)
async def test_post_review_comments_gerrit_error(mock_run_curl, response):
    mock_run_curl.return_value = response

    result = await main.post_review_comments(
        "123",
        [{"file_path": "missing.py", "line_number": 1, "message": "m"}],
        gerrit_base_url=BASE_URL,
    )

    assert "Failed to post comments" in result[0]["text"]
    assert response in result[0]["text"]


@pytest.mark.asyncio
async def test_post_review_comments_curl_exception_is_raised(mock_run_curl):
    mock_run_curl.side_effect = Exception("curl failed")

    with pytest.raises(Exception, match="curl failed"):
        await main.post_review_comments(
            "123",
            [{"file_path": "a.py", "line_number": 1, "message": "m"}],
            gerrit_base_url=BASE_URL,
        )
