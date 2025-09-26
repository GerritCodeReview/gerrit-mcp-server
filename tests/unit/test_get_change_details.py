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


class TestGetChangeDetails(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_change_details_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            mock_response = {
                "_number": 12345,
                "subject": "Test Subject",
                "owner": {"email": "owner@example.com"},
                "status": "NEW",
                "current_revision": "abc",
                "revisions": {
                    "abc": {"commit": {"message": "Test commit message\n\nBug: 123"}}
                },
                "reviewers": {
                    "REVIEWER": [{"email": "reviewer@example.com", "_account_id": 1}]
                },
                "labels": {"Code-Review": {"all": [{"value": 2, "_account_id": 1}]}},
                "messages": [
                    {"_revision_number": 1, "message": "Uploaded patch set 1."}
                ],
            }
            mock_run_curl.return_value = json.dumps(mock_response)
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.get_change_details(
                change_id, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn("Summary for CL 12345", result[0]["text"])
            self.assertIn("Subject: Test Subject", result[0]["text"])
            self.assertIn("Owner: owner@example.com", result[0]["text"])
            self.assertIn("Status: NEW", result[0]["text"])
            self.assertIn("Bugs: 123", result[0]["text"])
            self.assertIn("Reviewers:", result[0]["text"])
            self.assertIn("- reviewer@example.com (Code-Review: +2)", result[0]["text"])
            self.assertIn("Recent Messages:", result[0]["text"])
            self.assertIn(
                "- (Patch Set 1) [No date] (Gerrit): Uploaded patch set 1.",
                result[0]["text"],
            )

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
