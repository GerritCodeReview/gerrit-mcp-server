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

import asyncio
import json
import unittest
from unittest.mock import patch, AsyncMock

from gerrit_mcp_server import main


class TestAbandonChange(unittest.TestCase):

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_abandon_change_success(self, mock_run_curl):
        async def run_test():
            """Tests that abandon_change successfully abandons a CL."""
            mock_run_curl.return_value = json.dumps(
                {
                    "id": "myProject~main~I8473b95934b5732ac55d26311a706c9c2bde9940",
                    "status": "ABANDONED",
                    "_number": 123,
                }
            )

            result = await main.abandon_change(change_id="123")
            self.assertIn("Successfully abandoned CL 123", result[0]["text"])
            self.assertIn("Status: ABANDONED", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_abandon_change_with_message_success(self, mock_run_curl):
        async def run_test():
            """Tests that abandon_change with a message successfully abandons a CL."""
            mock_run_curl.return_value = json.dumps(
                {
                    "id": "myProject~main~I8473b95934b5732ac55d26311a706c9c2bde9940",
                    "status": "ABANDONED",
                    "_number": 123,
                }
            )

            result = await main.abandon_change(
                change_id="123", message="No longer needed"
            )
            self.assertIn("Successfully abandoned CL 123", result[0]["text"])
            self.assertIn("Status: ABANDONED", result[0]["text"])

            # Verify that the message was included in the curl arguments
            mock_run_curl.assert_called_once()
            args, _ = mock_run_curl.call_args
            self.assertIn("--data", args[0])
            self.assertIn('{"message": "No longer needed"}', args[0])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_abandon_change_failure_409(self, mock_run_curl):
        async def run_test():
            """Tests that abandon_change handles a 409 Conflict error."""
            mock_run_curl.return_value = "change is merged"

            result = await main.abandon_change(change_id="123")
            self.assertIn("Failed to abandon CL 123", result[0]["text"])
            self.assertIn("change is merged", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_abandon_change_generic_error(self, mock_run_curl):
        async def run_test():
            """Tests that abandon_change handles a generic exception."""
            mock_run_curl.side_effect = Exception("Something went wrong")

            with self.assertRaises(Exception):
                await main.abandon_change(change_id="123")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
