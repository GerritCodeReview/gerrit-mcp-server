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


class TestSuggestReviewers(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_suggest_reviewers_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            query = "John"
            mock_response = [
                {"account": {"name": "John Doe", "email": "john.doe@example.com"}},
                {"group": {"name": "Johns-group"}},
            ]
            mock_run_curl.return_value = json.dumps(mock_response)
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.suggest_reviewers(
                change_id, query, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn("Suggested reviewers:", result[0]["text"])
            self.assertIn("Account: John Doe (john.doe@example.com)", result[0]["text"])
            self.assertIn("Group: Johns-group", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_suggest_reviewers_empty(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            query = "nonexistent"
            mock_run_curl.return_value = "[]"
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.suggest_reviewers(
                change_id, query, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertEqual(
                result,
                [{"type": "text", "text": "No reviewers found for the given query."}],
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_suggest_reviewers_exception(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            query = "a"
            error_message = "Internal Server Error"
            mock_run_curl.side_effect = Exception(error_message)
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.suggest_reviewers(
                change_id, query, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(
                f"An error occurred while suggesting reviewers for CL {change_id}",
                result[0]["text"],
            )
            self.assertIn(error_message, result[0]["text"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
