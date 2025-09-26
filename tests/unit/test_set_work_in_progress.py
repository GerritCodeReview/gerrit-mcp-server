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


class TestSetWorkInProgress(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_set_wip_success_no_message(self, mock_run_curl):
        async def run_test():
            # Arrange
            mock_run_curl.return_value = ""
            change_id = "12345"
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.set_work_in_progress(
                change_id, gerrit_base_url=gerrit_base_url
            )

            # Assert
            expected_url = "https://my-gerrit.com/changes/12345/wip"
            expected_args = ["-X", "POST", expected_url]
            mock_run_curl.assert_called_once_with(expected_args, gerrit_base_url)
            self.assertEqual(
                result,
                [
                    {
                        "type": "text",
                        "text": f"CL {change_id} is now a work-in-progress.",
                    }
                ],
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_set_wip_success_with_message(self, mock_run_curl):
        async def run_test():
            # Arrange
            mock_run_curl.return_value = ""
            change_id = "12345"
            message = "This is a test message"
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.set_work_in_progress(
                change_id, message=message, gerrit_base_url=gerrit_base_url
            )

            # Assert
            expected_url = "https://my-gerrit.com/changes/12345/wip"
            expected_payload = json.dumps({"message": message})
            expected_args = [
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "--data",
                expected_payload,
                expected_url,
            ]
            mock_run_curl.assert_called_once_with(expected_args, gerrit_base_url)
            self.assertEqual(
                result,
                [
                    {
                        "type": "text",
                        "text": f"CL {change_id} is now a work-in-progress.",
                    }
                ],
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_set_wip_failure(self, mock_run_curl):
        async def run_test():
            # Arrange
            error_message = "Permission denied"
            mock_run_curl.return_value = f'{{"error": "{error_message}"}}'
            change_id = "12345"
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.set_work_in_progress(
                change_id, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn("Failed to set CL", result[0]["text"])
            self.assertIn(error_message, result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_set_wip_exception(self, mock_run_curl):
        async def run_test():
            change_id = "12345"
            gerrit_base_url = "https://gerrit-review.googlesource.com"
            error_message = "Connection timed out"
            mock_run_curl.side_effect = Exception(error_message)

            with self.assertRaisesRegex(Exception, error_message):
                await main.set_work_in_progress(
                    change_id, gerrit_base_url=gerrit_base_url
                )

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
