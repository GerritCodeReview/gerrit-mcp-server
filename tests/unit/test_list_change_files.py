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


class TestListChangeFiles(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_list_change_files_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "54321"
            # Mock response for files
            files_response = {
                "/COMMIT_MSG": {"lines_inserted": 10, "lines_deleted": 0},
                "src/main.py": {
                    "status": "MODIFIED",
                    "lines_inserted": 5,
                    "lines_deleted": 2,
                },
                "tests/test_main.py": {
                    "status": "ADDED",
                    "lines_inserted": 20,
                    "lines_deleted": 0,
                },
            }
            # Mock response for change details to get patch set number
            details_response = {"current_revision_number": 3}
            mock_run_curl.side_effect = [
                json.dumps(files_response),
                json.dumps(details_response),
            ]
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.list_change_files(
                change_id, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertIn("Files in CL 54321 (Patch Set 3):", result[0]["text"])
            self.assertIn("[M] src/main.py (+5, -2)", result[0]["text"])
            self.assertIn("[A] tests/test_main.py (+20, -0)", result[0]["text"])
            self.assertNotIn("/COMMIT_MSG", result[0]["text"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
