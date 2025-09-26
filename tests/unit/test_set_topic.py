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


class TestSetTopic(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_set_topic_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            topic = "new-topic"
            mock_run_curl.return_value = json.dumps(topic)
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.set_topic(
                change_id, topic, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(
                f"Successfully set topic for CL {change_id} to: {topic}",
                result[0]["text"],
            )
            payload = json.dumps({"topic": topic})
            expected_args = [
                "-X",
                "PUT",
                "-H",
                "Content-Type: application/json",
                "--data",
                payload,
                f"{gerrit_base_url}/changes/{change_id}/topic",
            ]
            mock_run_curl.assert_called_once_with(expected_args, gerrit_base_url)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_topic_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            mock_run_curl.return_value = ""  # Simulate 204 No Content
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.set_topic(
                change_id, "", gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertEqual(
                result,
                [
                    {
                        "type": "text",
                        "text": f"Topic successfully deleted from CL {change_id}.",
                    }
                ],
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_set_topic_failure(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            error_message = "topic not found"
            # First call raises the error, second call returns the raw text for the error message
            mock_run_curl.side_effect = [json.JSONDecodeError("", "", 0), error_message]
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.set_topic(
                change_id, "bad-topic", gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(f"Failed to set topic for CL {change_id}", result[0]["text"])
            self.assertIn(error_message, result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_set_topic_exception(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "12345"
            error_message = "500 Internal Server Error"
            mock_run_curl.side_effect = Exception(error_message)
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.set_topic(
                change_id, "any-topic", gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(
                f"An error occurred while setting the topic for CL {change_id}",
                result[0]["text"],
            )
            self.assertIn(error_message, result[0]["text"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
