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

import json
import unittest
from unittest.mock import patch, AsyncMock
import asyncio

from gerrit_mcp_server import main


class TestGetFileDiff(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_diff_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "54321"
            file_path = "src/main.py"
            diff_json = {
                "meta_a": {"name": "src/main.py", "content_type": "text/x-python", "lines": 3},
                "meta_b": {"name": "src/main.py", "content_type": "text/x-python", "lines": 3},
                "change_type": "MODIFIED",
                "content": [
                    {"ab": ["import os", ""]},
                    {"a": ["old line"], "b": ["new line"]},
                ],
            }
            mock_run_curl.return_value = json.dumps(diff_json)
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.get_file_diff(
                change_id, file_path, gerrit_base_url=gerrit_base_url
            )

            # Assert
            text = result[0]["text"]
            self.assertIn("src/main.py (MODIFIED)", text)
            # Unchanged lines should have new-file line numbers
            self.assertIn("     1:  import os", text)
            self.assertIn("     2:  ", text)
            # Deleted line has no new-file line number
            self.assertIn("      : -old line", text)
            # Added line has new-file line number
            self.assertIn("     3: +new line", text)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_diff_new_file(self, mock_run_curl):
        async def run_test():
            change_id = "99999"
            file_path = "new_file.py"
            diff_json = {
                "meta_b": {"name": "new_file.py", "content_type": "text/x-python", "lines": 3},
                "change_type": "ADDED",
                "content": [
                    {"b": ["line one", "line two", "line three"]},
                ],
            }
            mock_run_curl.return_value = json.dumps(diff_json)

            result = await main.get_file_diff(
                change_id, file_path, gerrit_base_url="https://my-gerrit.com"
            )

            text = result[0]["text"]
            self.assertIn("new_file.py (ADDED)", text)
            self.assertIn("     1: +line one", text)
            self.assertIn("     2: +line two", text)
            self.assertIn("     3: +line three", text)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_diff_with_skip(self, mock_run_curl):
        async def run_test():
            change_id = "11111"
            file_path = "big_file.py"
            diff_json = {
                "meta_a": {"name": "big_file.py", "content_type": "text/x-python", "lines": 200},
                "meta_b": {"name": "big_file.py", "content_type": "text/x-python", "lines": 201},
                "change_type": "MODIFIED",
                "content": [
                    {"ab": ["first line"]},
                    {"skip": 95},
                    {"a": ["old middle"], "b": ["new middle 1", "new middle 2"]},
                    {"skip": 100},
                    {"ab": ["last line"]},
                ],
            }
            mock_run_curl.return_value = json.dumps(diff_json)

            result = await main.get_file_diff(
                change_id, file_path, gerrit_base_url="https://my-gerrit.com"
            )

            text = result[0]["text"]
            self.assertIn("     1:  first line", text)
            self.assertIn("(95 unchanged lines omitted)", text)
            self.assertIn("      : -old middle", text)
            self.assertIn("    97: +new middle 1", text)
            self.assertIn("    98: +new middle 2", text)
            self.assertIn("(100 unchanged lines omitted)", text)
            self.assertIn("   199:  last line", text)

        asyncio.run(run_test())


class TestFormatStructuredDiffContext(unittest.TestCase):
    """Tests for client-side context trimming in _format_structured_diff."""

    def test_large_ab_chunk_is_trimmed(self):
        """A large unchanged block should show only 3 context lines around changes."""
        ab_before = [f"line {i}" for i in range(1, 201)]  # 200 lines
        ab_after = [f"line {i}" for i in range(202, 302)]  # 100 lines
        diff_json = {
            "meta_a": {"name": "big.py", "lines": 301},
            "meta_b": {"name": "big.py", "lines": 301},
            "change_type": "MODIFIED",
            "content": [
                {"ab": ab_before},
                {"a": ["old"], "b": ["new"]},
                {"ab": ab_after},
            ],
        }

        text = main._format_structured_diff("big.py", diff_json)

        # First ab chunk: no prev change, next has change -> show last 3
        self.assertNotIn("     1:  line 1\n", text)
        self.assertIn("(197 unchanged lines omitted)", text)
        self.assertIn("  198:  line 198", text)
        self.assertIn("  199:  line 199", text)
        self.assertIn("  200:  line 200", text)
        # The change itself
        self.assertIn("      : -old", text)
        self.assertIn("  201: +new", text)
        # Second ab chunk: prev has change, no next -> show first 3
        self.assertIn("  202:  line 202", text)
        self.assertIn("  203:  line 203", text)
        self.assertIn("  204:  line 204", text)
        self.assertNotIn("line 301", text)
        self.assertIn("(97 unchanged lines omitted)", text)

    def test_small_ab_chunk_between_changes_not_trimmed(self):
        """An ab chunk smaller than 2x context lines between changes shows all lines."""
        diff_json = {
            "meta_a": {"name": "small.py", "lines": 10},
            "meta_b": {"name": "small.py", "lines": 10},
            "change_type": "MODIFIED",
            "content": [
                {"a": ["old1"], "b": ["new1"]},
                {"ab": ["mid1", "mid2", "mid3"]},
                {"a": ["old2"], "b": ["new2"]},
            ],
        }

        text = main._format_structured_diff("small.py", diff_json)

        # All 3 middle lines should be present, no skip marker
        self.assertIn("     2:  mid1", text)
        self.assertIn("     3:  mid2", text)
        self.assertIn("     4:  mid3", text)
        self.assertNotIn("omitted", text)

    def test_context_preserves_line_numbers(self):
        """Line numbers must be correct after trimming large ab chunks."""
        ab_lines = [f"unchanged {i}" for i in range(1, 1001)]  # 1000 lines
        diff_json = {
            "meta_a": {"name": "f.py", "lines": 1002},
            "meta_b": {"name": "f.py", "lines": 1002},
            "change_type": "MODIFIED",
            "content": [
                {"ab": ab_lines},
                {"a": ["old"], "b": ["new"]},
                {"ab": ["final line"]},
            ],
        }

        text = main._format_structured_diff("f.py", diff_json)

        # After 1000 unchanged lines, the change is at line 1001
        self.assertIn("  1001: +new", text)
        # Context before the change: lines 998, 999, 1000
        self.assertIn("   998:  unchanged 998", text)
        self.assertIn("  1000:  unchanged 1000", text)
        # Final line after the change
        self.assertIn("  1002:  final line", text)


    def test_small_file_not_trimmed(self):
        """Files under the small file threshold should show all lines."""
        ab_before = [f"line {i}" for i in range(1, 51)]  # 50 lines
        ab_after = [f"line {i}" for i in range(52, 101)]  # 49 lines
        diff_json = {
            "meta_a": {"name": "small.py", "lines": 100},
            "meta_b": {"name": "small.py", "lines": 100},
            "change_type": "MODIFIED",
            "content": [
                {"ab": ab_before},
                {"a": ["old"], "b": ["new"]},
                {"ab": ab_after},
            ],
        }

        text = main._format_structured_diff("small.py", diff_json)

        # All lines should be present, no skip markers
        self.assertNotIn("omitted", text)
        self.assertIn("     1:  line 1\n", text)
        self.assertIn("    50:  line 50", text)
        self.assertIn("      : -old", text)
        self.assertIn("    51: +new", text)
        self.assertIn("   100:  line 100", text)

    def test_file_at_threshold_not_trimmed(self):
        """A file exactly at the threshold (200 lines) should not be trimmed."""
        ab_lines = [f"line {i}" for i in range(1, 200)]  # 199 lines
        diff_json = {
            "meta_a": {"name": "border.py", "lines": 200},
            "meta_b": {"name": "border.py", "lines": 200},
            "change_type": "MODIFIED",
            "content": [
                {"ab": ab_lines},
                {"a": ["old"], "b": ["new"]},
            ],
        }

        text = main._format_structured_diff("border.py", diff_json)

        self.assertNotIn("omitted", text)
        self.assertIn("     1:  line 1\n", text)

    def test_file_above_threshold_is_trimmed(self):
        """A file above the threshold (201 lines) should be trimmed."""
        ab_lines = [f"line {i}" for i in range(1, 201)]  # 200 lines
        diff_json = {
            "meta_a": {"name": "big.py", "lines": 201},
            "meta_b": {"name": "big.py", "lines": 201},
            "change_type": "MODIFIED",
            "content": [
                {"ab": ab_lines},
                {"a": ["old"], "b": ["new"]},
            ],
        }

        text = main._format_structured_diff("big.py", diff_json)

        self.assertIn("omitted", text)
        self.assertNotIn("     1:  line 1\n", text)


if __name__ == "__main__":
    unittest.main()
