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


def _unchanged(line, text):
    return {"kind": "unchanged", "line": line, "text": text}


def _added(line, text):
    return {"kind": "added", "line": line, "text": text}


def _deleted(text):
    return {"kind": "deleted", "line": None, "text": text}


def _omitted(count):
    return {"kind": "omitted", "line": None, "text": f"{count} unchanged lines"}


class TestGetFileDiff(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_diff_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            diff_json = {
                "meta_a": {
                    "name": "src/main.py",
                    "content_type": "text/x-python",
                    "lines": 3,
                },
                "meta_b": {
                    "name": "src/main.py",
                    "content_type": "text/x-python",
                    "lines": 3,
                },
                "change_type": "MODIFIED",
                "content": [
                    {"ab": ["import os", ""]},
                    {"a": ["old line"], "b": ["new line"]},
                ],
            }
            mock_run_curl.return_value = json.dumps(diff_json)

            # Act
            result = await main.get_file_diff(
                "54321", "src/main.py", gerrit_base_url=GERRIT_BASE_URL
            )

            # Assert
            self.assertEqual(
                result,
                {
                    "change_id": "54321",
                    "change_type": "MODIFIED",
                    "old_path": "src/main.py",
                    "new_path": "src/main.py",
                    "old_line_count": 3,
                    "new_line_count": 3,
                    "binary": False,
                    "lines": [
                        _unchanged(1, "import os"),
                        _unchanged(2, ""),
                        _deleted("old line"),
                        _added(3, "new line"),
                    ],
                },
            )
            call_url = mock_run_curl.call_args[0][0][0]
            self.assertTrue(
                call_url.endswith(
                    "/changes/54321/revisions/current/files/src%2Fmain.py/diff"
                )
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_diff_new_file(self, mock_run_curl):
        async def run_test():
            diff_json = {
                "meta_b": {
                    "name": "new_file.py",
                    "content_type": "text/x-python",
                    "lines": 3,
                },
                "change_type": "ADDED",
                "content": [
                    {"b": ["line one", "line two", "line three"]},
                ],
            }
            mock_run_curl.return_value = json.dumps(diff_json)

            result = await main.get_file_diff(
                "99999", "new_file.py", gerrit_base_url=GERRIT_BASE_URL
            )

            self.assertEqual(result["change_type"], "ADDED")
            self.assertIsNone(result["old_path"])
            self.assertIsNone(result["old_line_count"])
            self.assertEqual(result["new_path"], "new_file.py")
            self.assertEqual(
                result["lines"],
                [
                    _added(1, "line one"),
                    _added(2, "line two"),
                    _added(3, "line three"),
                ],
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_diff_deleted_file(self, mock_run_curl):
        async def run_test():
            diff_json = {
                "meta_a": {
                    "name": "old_file.py",
                    "content_type": "text/x-python",
                    "lines": 2,
                },
                "change_type": "DELETED",
                "content": [
                    {"a": ["line one", "line two"]},
                ],
            }
            mock_run_curl.return_value = json.dumps(diff_json)

            result = await main.get_file_diff(
                "77777", "old_file.py", gerrit_base_url=GERRIT_BASE_URL
            )

            self.assertEqual(result["change_type"], "DELETED")
            self.assertEqual(result["old_path"], "old_file.py")
            self.assertIsNone(result["new_path"])
            self.assertIsNone(result["new_line_count"])
            self.assertEqual(
                result["lines"], [_deleted("line one"), _deleted("line two")]
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_diff_renamed_file(self, mock_run_curl):
        async def run_test():
            diff_json = {
                "meta_a": {
                    "name": "old_name.py",
                    "content_type": "text/x-python",
                    "lines": 2,
                },
                "meta_b": {
                    "name": "new_name.py",
                    "content_type": "text/x-python",
                    "lines": 2,
                },
                "change_type": "RENAMED",
                "content": [
                    {"ab": ["same"]},
                    {"a": ["old"], "b": ["new"]},
                ],
            }
            mock_run_curl.return_value = json.dumps(diff_json)

            result = await main.get_file_diff(
                "12121", "new_name.py", gerrit_base_url=GERRIT_BASE_URL
            )

            self.assertEqual(result["change_type"], "RENAMED")
            self.assertEqual(result["old_path"], "old_name.py")
            self.assertEqual(result["new_path"], "new_name.py")
            self.assertEqual(
                result["lines"],
                [_unchanged(1, "same"), _deleted("old"), _added(2, "new")],
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_diff_binary_file(self, mock_run_curl):
        async def run_test():
            diff_json = {
                "meta_b": {
                    "name": "logo.png",
                    "content_type": "image/png",
                    "lines": 75,
                },
                "change_type": "ADDED",
                "binary": True,
                "content": [],
            }
            mock_run_curl.return_value = json.dumps(diff_json)

            result = await main.get_file_diff(
                "13131", "logo.png", gerrit_base_url=GERRIT_BASE_URL
            )

            self.assertTrue(result["binary"])
            self.assertEqual(result["lines"], [])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_diff_invalid_json(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "not valid json"

            with self.assertRaises(ValueError) as context:
                await main.get_file_diff(
                    "88888", "file.py", gerrit_base_url=GERRIT_BASE_URL
                )

            self.assertIn("not valid json", str(context.exception))

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_diff_default_context(self, mock_run_curl):
        async def run_test():
            diff_json = {
                "change_type": "MODIFIED",
                "content": [
                    {"ab": [f"line {n}" for n in range(1, 51)]},
                    {"b": ["added"]},
                ],
            }
            mock_run_curl.return_value = json.dumps(diff_json)

            result = await main.get_file_diff(
                "33333", "file.py", gerrit_base_url=GERRIT_BASE_URL
            )

            self.assertEqual(
                result["lines"],
                [_omitted(40)]
                + [_unchanged(n, f"line {n}") for n in range(41, 51)]
                + [_added(51, "added")],
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_diff_whole_file_context(self, mock_run_curl):
        async def run_test():
            diff_json = {
                "change_type": "MODIFIED",
                "content": [
                    {"ab": [f"line {n}" for n in range(1, 51)]},
                    {"b": ["added"]},
                ],
            }
            mock_run_curl.return_value = json.dumps(diff_json)

            result = await main.get_file_diff(
                "44444", "file.py", gerrit_base_url=GERRIT_BASE_URL, context_lines=-1
            )

            self.assertEqual(
                result["lines"],
                [_unchanged(n, f"line {n}") for n in range(1, 51)]
                + [_added(51, "added")],
            )

        asyncio.run(run_test())


class TestDiffLineBuilder(unittest.TestCase):
    def test_skip_chunks_become_omitted_entries(self):
        lines = main._DiffLineBuilder(context_lines=-1).build(
            [
                {"ab": ["first line"]},
                {"skip": 95},
                {"a": ["old middle"], "b": ["new middle 1", "new middle 2"]},
                {"skip": 100},
                {"ab": ["last line"]},
            ]
        )

        self.assertEqual(
            lines,
            [
                _unchanged(1, "first line"),
                _omitted(95),
                _deleted("old middle"),
                _added(97, "new middle 1"),
                _added(98, "new middle 2"),
                _omitted(100),
                _unchanged(199, "last line"),
            ],
        )

    def test_unchanged_lines_beyond_context_are_folded(self):
        lines = main._DiffLineBuilder(context_lines=3).build(
            [
                {"ab": [f"before {n}" for n in range(1, 31)]},
                {"a": ["old"], "b": ["new"]},
                {"ab": [f"after {n}" for n in range(32, 62)]},
            ]
        )

        self.assertEqual(
            lines,
            [
                _omitted(27),
                _unchanged(28, "before 28"),
                _unchanged(29, "before 29"),
                _unchanged(30, "before 30"),
                _deleted("old"),
                _added(31, "new"),
                _unchanged(32, "after 32"),
                _unchanged(33, "after 33"),
                _unchanged(34, "after 34"),
                _omitted(27),
            ],
        )

    def test_negative_context_keeps_every_line(self):
        lines = main._DiffLineBuilder(context_lines=-1).build(
            [
                {"ab": [f"line {n}" for n in range(1, 51)]},
                {"b": ["added"]},
            ]
        )

        self.assertEqual(
            lines,
            [_unchanged(n, f"line {n}") for n in range(1, 51)] + [_added(51, "added")],
        )

    def test_short_gap_between_changes_is_kept(self):
        lines = main._DiffLineBuilder(context_lines=3).build(
            [
                {"b": ["first"]},
                {"ab": [f"gap {n}" for n in range(2, 8)]},
                {"b": ["second"]},
            ]
        )

        self.assertEqual(
            lines,
            [_added(1, "first")]
            + [_unchanged(n, f"gap {n}") for n in range(2, 8)]
            + [_added(8, "second")],
        )

    def test_single_omitted_line(self):
        lines = main._DiffLineBuilder(context_lines=3).build(
            [
                {"b": ["first"]},
                {"ab": [f"gap {n}" for n in range(2, 9)]},
                {"b": ["second"]},
            ]
        )

        self.assertEqual(
            lines,
            [
                _added(1, "first"),
                _unchanged(2, "gap 2"),
                _unchanged(3, "gap 3"),
                _unchanged(4, "gap 4"),
                {"kind": "omitted", "line": None, "text": "1 unchanged line"},
                _unchanged(6, "gap 6"),
                _unchanged(7, "gap 7"),
                _unchanged(8, "gap 8"),
                _added(9, "second"),
            ],
        )

    def test_fold_next_to_skip_is_one_entry(self):
        lines = main._DiffLineBuilder(context_lines=3).build(
            [
                {"b": ["added"]},
                {"ab": [f"line {n}" for n in range(2, 12)]},
                {"skip": 50},
            ]
        )

        self.assertEqual(
            lines,
            [
                _added(1, "added"),
                _unchanged(2, "line 2"),
                _unchanged(3, "line 3"),
                _unchanged(4, "line 4"),
                _omitted(57),
            ],
        )

    def test_content_without_changes_is_folded_whole(self):
        lines = main._DiffLineBuilder(context_lines=10).build(
            [{"ab": ["one", "two", "three"]}]
        )

        self.assertEqual(lines, [_omitted(3)])


if __name__ == "__main__":
    unittest.main()
