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

import unittest
from unittest.mock import patch, AsyncMock
import asyncio
import json

from gerrit_mcp_server import main


class TestListChangeComments(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_list_change_comments_unresolved(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "11223"
            mock_response = {
                "src/main.py": [
                    {
                        "line": 10,
                        "author": {"name": "user1@example.com"},
                        "message": "This is a comment.",
                        "unresolved": True,
                        "updated": "2025-07-15T10:00:00Z",
                    },
                    {
                        "line": 15,
                        "author": {"name": "user2@example.com"},
                        "message": "This is resolved.",
                        "unresolved": False,
                        "updated": "2025-07-15T10:05:00Z",
                    },
                ],
                "README.md": [
                    {
                        "author": {"name": "user1@example.com"},
                        "message": "Another unresolved comment.",
                        "unresolved": True,
                        "updated": "2025-07-15T10:10:00Z",
                    }
                ],
            }
            mock_run_curl.return_value = json.dumps(mock_response)
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.list_change_comments(
                change_id, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn("Comments for CL 11223", result[0]["text"])
            self.assertIn("File: src/main.py", result[0]["text"])
            self.assertIn(
                "L10: [user1@example.com] (2025-07-15T10:00:00Z) - UNRESOLVED",
                result[0]["text"],
            )
            self.assertIn("This is a comment.", result[0]["text"])
            self.assertIn(
                "L15: [user2@example.com] (2025-07-15T10:05:00Z) - RESOLVED",
                result[0]["text"],
            )
            self.assertIn("This is resolved.", result[0]["text"])
            self.assertIn("File: README.md", result[0]["text"])
            self.assertIn(
                "LFile: [user1@example.com] (2025-07-15T10:10:00Z) - UNRESOLVED",
                result[0]["text"],
            )
            self.assertIn("Another unresolved comment.", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_list_change_comments_none_unresolved(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "11223"
            mock_response = {
                "src/main.py": [
                    {
                        "line": 15,
                        "author": {"name": "user2@example.com"},
                        "message": "This is resolved.",
                        "unresolved": False,
                        "updated": "2025-07-15T10:05:00Z",
                    }
                ]
            }
            mock_run_curl.return_value = json.dumps(mock_response)
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.list_change_comments(
                change_id, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn("Comments for CL 11223", result[0]["text"])
            self.assertIn(
                "L15: [user2@example.com] (2025-07-15T10:05:00Z) - RESOLVED",
                result[0]["text"],
            )

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
