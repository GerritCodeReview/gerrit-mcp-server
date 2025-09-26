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
import base64

from gerrit_mcp_server import main


class TestGetFileDiff(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_diff_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            change_id = "54321"
            file_path = "src/main.py"
            diff_content = "diff --git a/src/main.py b/src/main.py\n--- a/src/main.py\n+++ b/src/main.py\n@@ -1,1 +1,1 @@\n-old line\n+new line"
            encoded_diff = base64.b64encode(diff_content.encode("utf-8")).decode(
                "utf-8"
            )
            mock_run_curl.return_value = encoded_diff
            gerrit_base_url = "https://my-gerrit.com"

            # Act
            result = await main.get_file_diff(
                change_id, file_path, gerrit_base_url=gerrit_base_url
            )

            # Assert
            self.assertEqual(result[0]["text"], diff_content)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
