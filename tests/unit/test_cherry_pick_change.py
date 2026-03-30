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


class TestCherryPickChange(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_cherry_pick_change_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            destination = "release-branch"
            new_cl_number = 67890
            new_subject = "Cherry-picked change"
            mock_run_curl.return_value = json.dumps(
                {
                    "id": f"myProject~{destination}~Iabc123",
                    "_number": new_cl_number,
                    "subject": new_subject,
                }
            )
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.cherry_pick_change(
                change_id, destination, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(
                f"Successfully cherry-picked CL {change_id} to branch {destination}",
                result[0]["text"],
            )
            self.assertIn(
                f"New CL created: {new_cl_number}", result[0]["text"]
            )
            self.assertIn(f"Subject: {new_subject}", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_cherry_pick_change_with_message(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            destination = "release-branch"
            custom_message = "Custom cherry-pick message"
            mock_run_curl.return_value = json.dumps(
                {
                    "id": "myProject~release-branch~Iabc123",
                    "_number": 67890,
                    "subject": custom_message,
                }
            )
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.cherry_pick_change(
                change_id,
                destination,
                message=custom_message,
                gerrit_base_url=gerrit_base_url,
            )

            # Assert
            self.assertIn("Successfully cherry-picked", result[0]["text"])
            # Verify the payload included the message
            call_args = mock_run_curl.call_args[0][0]
            payload = json.loads(call_args[call_args.index("--data") + 1])
            self.assertEqual(payload["message"], custom_message)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_cherry_pick_change_with_specific_revision(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            destination = "release-branch"
            revision_id = "3"
            mock_run_curl.return_value = json.dumps(
                {
                    "id": "myProject~release-branch~Iabc123",
                    "_number": 67890,
                    "subject": "Cherry-picked",
                }
            )
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.cherry_pick_change(
                change_id,
                destination,
                revision_id=revision_id,
                gerrit_base_url=gerrit_base_url,
            )

            # Assert
            self.assertIn("Successfully cherry-picked", result[0]["text"])
            call_args = mock_run_curl.call_args[0][0]
            url = call_args[-1]
            self.assertIn(f"/revisions/{revision_id}/cherrypick", url)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_cherry_pick_change_allow_conflicts_default_true(self, mock_run_curl):
        async def run_test():
            # Arrange
            mock_run_curl.return_value = json.dumps(
                {
                    "id": "myProject~main~Iabc",
                    "_number": 67890,
                    "subject": "Cherry-picked",
                }
            )
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            await main.cherry_pick_change(
                "12345", "main", gerrit_base_url=gerrit_base_url
            )

            # Assert — allow_conflicts should be in the payload by default
            call_args = mock_run_curl.call_args[0][0]
            payload = json.loads(call_args[call_args.index("--data") + 1])
            self.assertTrue(payload.get("allow_conflicts"))

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_cherry_pick_change_failure_response(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            error_message = "change is new"
            mock_run_curl.return_value = error_message
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.cherry_pick_change(
                change_id, "release-branch", gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(
                f"Failed to cherry-pick CL {change_id}", result[0]["text"]
            )
            self.assertIn(error_message, result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_cherry_pick_change_missing_fields(self, mock_run_curl):
        async def run_test():
            # Arrange — response lacks _number
            change_id = "12345"
            mock_run_curl.return_value = json.dumps({"status": "error"})
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.cherry_pick_change(
                change_id, "release-branch", gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(
                f"Failed to cherry-pick CL {change_id}", result[0]["text"]
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_cherry_pick_change_exception(self, mock_run_curl):
        async def run_test():
            change_id = "12345"
            gerrit_base_url = "https://my-gerrit.com"
            error_message = "Internal server error"
            mock_run_curl.side_effect = Exception(error_message)

            with self.assertRaisesRegex(Exception, error_message):
                await main.cherry_pick_change(
                    change_id, "release-branch", gerrit_base_url=gerrit_base_url
                )

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
