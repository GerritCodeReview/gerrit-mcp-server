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


class TestRevertSubmission(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_revert_submission_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            mock_response = {
                "revert_changes": [
                    {"_number": 54321, "subject": 'Revert "Change 1"'},
                    {"_number": 54322, "subject": 'Revert "Change 2"'},
                ]
            }
            mock_run_curl.return_value = json.dumps(mock_response)
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.revert_submission(
                change_id, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(
                f"Successfully reverted submission for CL {change_id}",
                result[0]["text"],
            )
            self.assertIn("Created revert changes:", result[0]["text"])
            self.assertIn('- 54321: Revert "Change 1"', result[0]["text"])
            self.assertIn('- 54322: Revert "Change 2"', result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_revert_submission_failure(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            error_message = "submission cannot be reverted"
            mock_run_curl.return_value = error_message
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.revert_submission(
                change_id, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(
                f"Failed to revert submission for CL {change_id}", result[0]["text"]
            )
            self.assertIn(error_message, result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_revert_submission_exception(self, mock_run_curl):
        async def run_test():
            change_id = "12345"
            gerrit_base_url = "https://gerrit-review.googlesource.com"
            error_message = "Network failure"
            mock_run_curl.side_effect = Exception(error_message)

            with self.assertRaisesRegex(Exception, error_message):
                await main.revert_submission(change_id, gerrit_base_url=gerrit_base_url)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
