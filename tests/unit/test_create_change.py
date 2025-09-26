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


class TestCreateChange(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_create_change_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            project = "myProject"
            subject = "New Feature"
            branch = "main"
            new_cl_number = 12345
            mock_response = {
                "id": f"{project}~{branch}~I{new_cl_number}",
                "_number": new_cl_number,
                "project": project,
                "branch": branch,
                "subject": subject,
            }
            mock_run_curl.return_value = json.dumps(mock_response)
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.create_change(
                project, subject, branch, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(
                f"Successfully created new change {new_cl_number}", result[0]["text"]
            )
            self.assertIn(f"Subject: {subject}", result[0]["text"])
            self.assertIn(f"Project: {project}, Branch: {branch}", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_create_change_bad_request(self, mock_run_curl):
        async def run_test():
            # Arrange
            error_message = "Invalid project"
            mock_run_curl.return_value = error_message
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.create_change(
                "invalid", "subject", "branch", gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn("Failed to create change", result[0]["text"])
            self.assertIn(error_message, result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_create_change_exception(self, mock_run_curl):
        async def run_test():
            # Arrange
            error_message = "Connection refused"
            mock_run_curl.side_effect = Exception(error_message)
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.create_change(
                "project", "subject", "branch", gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn(
                "An error occurred while creating the change", result[0]["text"]
            )
            self.assertIn(error_message, result[0]["text"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
