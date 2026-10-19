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
import unittest
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server import main

GERRIT_BASE_URL = "https://gerrit.example.com"


def _comment(comment_id, updated, unresolved, in_reply_to=None, **location):
    comment = {
        "id": comment_id,
        "author": {"name": "Reviewer"},
        "message": f"message of {comment_id}",
        "unresolved": unresolved,
        "updated": updated,
        **location,
    }
    if in_reply_to is not None:
        comment["in_reply_to"] = in_reply_to
    return comment


def _listed(comment_id, updated, unresolved, in_reply_to=None):
    return {
        "id": comment_id,
        "author": "Reviewer",
        "updated": updated,
        "message": f"message of {comment_id}",
        "in_reply_to": in_reply_to,
        "unresolved": unresolved,
    }


class TestListChangeComments(unittest.TestCase):
    def _list(self, mock_run_curl, comments_by_file):
        mock_run_curl.return_value = json.dumps(comments_by_file)
        return asyncio.run(
            main.list_change_comments("11223", gerrit_base_url=GERRIT_BASE_URL)
        )

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_joins_the_thread_of_its_parent(self, mock_run_curl):
        result = self._list(
            mock_run_curl,
            {
                "src/main.py": [
                    _comment("root", "2026-10-01 10:00:00", True, line=10, patch_set=3),
                    _comment("reply", "2026-10-02 10:00:00", False, "root", line=10),
                ]
            },
        )

        self.assertEqual(
            result,
            {
                "change_id": "11223",
                "threads": [
                    {
                        "file_path": "src/main.py",
                        "line": 10,
                        "patch_set": 3,
                        "unresolved": False,
                        "comments": [
                            _listed("root", "2026-10-01 10:00:00", True),
                            _listed("reply", "2026-10-02 10:00:00", False, "root"),
                        ],
                    }
                ],
            },
        )

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_to_a_reply_joins_the_first_comment_thread(self, mock_run_curl):
        result = self._list(
            mock_run_curl,
            {
                "src/main.py": [
                    _comment("second", "2026-10-02 10:00:00", True, "first", line=7),
                    _comment("first", "2026-10-01 10:00:00", True, line=7),
                    _comment("third", "2026-10-03 10:00:00", True, "second", line=7),
                ]
            },
        )

        self.assertEqual(len(result["threads"]), 1)
        self.assertEqual(
            [c["id"] for c in result["threads"][0]["comments"]],
            ["first", "second", "third"],
        )

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_thread_state_is_the_state_of_its_latest_comment(self, mock_run_curl):
        result = self._list(
            mock_run_curl,
            {
                "src/main.py": [
                    _comment("root", "2026-10-01 10:00:00", True, line=4),
                    _comment("done", "2026-10-02 10:00:00", False, "root", line=4),
                    _comment("reopen", "2026-10-03 10:00:00", True, "done", line=4),
                ]
            },
        )

        self.assertTrue(result["threads"][0]["unresolved"])

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_comments_on_one_line_without_replies_are_separate_threads(
        self, mock_run_curl
    ):
        result = self._list(
            mock_run_curl,
            {
                "src/main.py": [
                    _comment("one", "2026-10-01 10:00:00", True, line=5),
                    _comment("two", "2026-10-01 11:00:00", False, line=5),
                ]
            },
        )

        self.assertEqual(
            [
                (t["comments"][0]["id"], t["unresolved"], len(t["comments"]))
                for t in result["threads"]
            ],
            [("one", True, 1), ("two", False, 1)],
        )

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_file_and_patch_set_level_threads_have_no_line(self, mock_run_curl):
        result = self._list(
            mock_run_curl,
            {
                "README.md": [_comment("file", "2026-10-01 10:00:00", True)],
                "/PATCHSET_LEVEL": [_comment("ps", "2026-10-01 09:00:00", True)],
            },
        )

        self.assertEqual(
            [(t["file_path"], t["line"]) for t in result["threads"]],
            [("/PATCHSET_LEVEL", None), ("README.md", None)],
        )

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_no_comments_gives_no_threads(self, mock_run_curl):
        result = self._list(mock_run_curl, {})

        self.assertEqual(result, {"change_id": "11223", "threads": []})

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_non_json_answer_raises_with_its_text(self, mock_run_curl):
        mock_run_curl.return_value = "Not found: 11223"

        with self.assertRaises(ValueError) as context:
            asyncio.run(
                main.list_change_comments("11223", gerrit_base_url=GERRIT_BASE_URL)
            )

        self.assertIn("Not found: 11223", str(context.exception))


if __name__ == "__main__":
    unittest.main()
