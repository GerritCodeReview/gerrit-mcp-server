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


class TestSubmitChange(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_submit_change_success(self, mock_run_curl):
        async def run_test():
            mock_response = {
                "id": "myproject~master~I1234",
                "_number": 12345,
                "subject": "Fix the bug",
                "status": "MERGED",
            }
            mock_run_curl.return_value = json.dumps(mock_response)
            gerrit_base_url = "https://my-gerrit.com"

            result = await main.submit_change(
                "12345", gerrit_base_url=gerrit_base_url
            )

            self.assertIn("Successfully submitted CL 12345", result[0]["text"])
            self.assertIn("Fix the bug", result[0]["text"])
            self.assertIn("MERGED", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_submit_change_not_submittable(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "change is new"
            gerrit_base_url = "https://my-gerrit.com"

            result = await main.submit_change(
                "12345", gerrit_base_url=gerrit_base_url
            )

            self.assertIn("Failed to submit CL 12345", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_submit_change_with_wait_for_merge(self, mock_run_curl):
        async def run_test():
            mock_response = {
                "id": "myproject~master~I1234",
                "_number": 12345,
                "subject": "Fix the bug",
                "status": "MERGED",
            }
            mock_run_curl.return_value = json.dumps(mock_response)
            gerrit_base_url = "https://my-gerrit.com"

            result = await main.submit_change(
                "12345",
                wait_for_merge=True,
                gerrit_base_url=gerrit_base_url,
            )

            self.assertIn("Successfully submitted CL 12345", result[0]["text"])
            # Verify the payload included wait_for_merge
            call_args = mock_run_curl.call_args[0][0]
            self.assertIn("wait_for_merge", str(call_args))

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_submit_change_exception(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = Exception("Connection refused")
            gerrit_base_url = "https://my-gerrit.com"

            with self.assertRaises(Exception) as ctx:
                await main.submit_change(
                    "12345", gerrit_base_url=gerrit_base_url
                )
            self.assertIn("Connection refused", str(ctx.exception))

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
