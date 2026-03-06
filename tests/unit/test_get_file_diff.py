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


if __name__ == "__main__":
    unittest.main()
