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


class TestRevertChange(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_revert_change_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            revert_cl_number = 54321
            revert_subject = 'Revert "Original Change"'
            mock_run_curl.return_value = json.dumps(
                {
                    "id": f"myProject~main~I{change_id}",
                    "_number": revert_cl_number,
                    "subject": revert_subject,
                }
            )
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.revert_change(
                change_id, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(f"Successfully reverted CL {change_id}", result[0]["text"])
            self.assertIn(
                f"New revert CL created: {revert_cl_number}", result[0]["text"]
            )
            self.assertIn(f"Subject: {revert_subject}", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_revert_change_conflict(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            error_message = "change is new"
            mock_run_curl.return_value = error_message
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.revert_change(
                change_id, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(f"Failed to revert CL {change_id}", result[0]["text"])
            self.assertIn(error_message, result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_revert_change_exception(self, mock_run_curl):
        async def run_test():
            change_id = "12345"
            gerrit_base_url = "https://gerrit-review.googlesource.com"
            error_message = "Internal server error"
            mock_run_curl.side_effect = Exception(error_message)

            with self.assertRaisesRegex(Exception, error_message):
                await main.revert_change(change_id, gerrit_base_url=gerrit_base_url)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
