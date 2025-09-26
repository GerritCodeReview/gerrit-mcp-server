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

import unittest
from unittest.mock import patch, AsyncMock
import asyncio

from gerrit_mcp_server import main


class TestAddReviewer(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_add_reviewer_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "33445"
            reviewer = "another-user@example.com"
            mock_run_curl.return_value = "{}"  # Empty JSON object on success
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.add_reviewer(
                change_id, reviewer, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertEqual(
                result,
                [
                    {
                        "type": "text",
                        "text": f"Successfully added {reviewer} as a REVIEWER to CL {change_id}.",
                    }
                ],
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_add_cc_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "55667"
            reviewer = "my-team@example.com"
            state = "CC"
            mock_run_curl.return_value = "{}"
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.add_reviewer(
                change_id, reviewer, gerrit_base_url=gerrit_base_url, state=state
            )

            # Assert
            self.assertEqual(
                result,
                [
                    {
                        "type": "text",
                        "text": f"Successfully added {reviewer} as a {state} to CL {change_id}.",
                    }
                ],
            )

        asyncio.run(run_test())

    def test_add_reviewer_invalid_state(self):
        async def run_test():
            # Act
            result = await main.add_reviewer("123", "user", state="INVALID")

            # Assert
            self.assertIn("Invalid state 'INVALID'", result[0]["text"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()