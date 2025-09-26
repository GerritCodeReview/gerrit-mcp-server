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


class TestChangesSubmittedTogether(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_submitted_together_with_non_visible(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            mock_response = {
                "changes": [
                    {"_number": 12345, "subject": "Main change"},
                    {"_number": 12344, "subject": "Dependent change"},
                ],
                "non_visible_changes": 1,
            }
            mock_run_curl.return_value = json.dumps(mock_response)
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.changes_submitted_together(
                change_id,
                gerrit_base_url=gerrit_base_url,
                options=["NON_VISIBLE_CHANGES"],
            )

            # Assert
            self.assertIn(
                "The following 2 changes would be submitted together:",
                result[0]["text"],
            )
            self.assertIn("- 12345: Main change", result[0]["text"])
            self.assertIn("- 12344: Dependent change", result[0]["text"])
            self.assertIn(
                "Plus 1 other changes that are not visible to you.", result[0]["text"]
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_submitted_together_list_response(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            mock_response = [
                {"_number": 12345, "subject": "Main change"},
                {"_number": 12344, "subject": "Dependent change"},
            ]
            mock_run_curl.return_value = json.dumps(mock_response)
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.changes_submitted_together(
                change_id, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(
                "The following 2 changes would be submitted together:",
                result[0]["text"],
            )
            self.assertNotIn("non_visible_changes", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_submitted_alone(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            mock_run_curl.return_value = ""  # Empty response
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.changes_submitted_together(
                change_id, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertEqual(
                result,
                [{"type": "text", "text": "This change would be submitted by itself."}],
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_submitted_together_exception(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            error_message = "Forbidden"
            mock_run_curl.side_effect = Exception(error_message)
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.changes_submitted_together(
                change_id, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(
                f"An error occurred while getting submitted together info for CL {change_id}",
                result[0]["text"],
            )
            self.assertIn(error_message, result[0]["text"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
