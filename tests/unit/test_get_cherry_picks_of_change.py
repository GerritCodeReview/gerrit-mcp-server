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


class TestGetCherryPicksOfChange(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_cherry_picks_found(self, mock_run_curl):
        async def run_test():
            detail_response = {
                "_number": 12345,
                "current_revision": "abc123",
                "revisions": {
                    "abc123": {
                        "commit": {
                            "message": (
                                "Fix the bug\n\n"
                                "Change-Id: I1234567890abcdef1234567890abcdef12345678\n"
                            )
                        }
                    }
                },
            }
            query_response = [
                {
                    "_number": 12345,
                    "branch": "master",
                    "project": "myproject",
                    "status": "MERGED",
                    "subject": "Fix the bug",
                },
                {
                    "_number": 12400,
                    "branch": "release-1.0",
                    "project": "myproject",
                    "status": "NEW",
                    "subject": "Fix the bug",
                },
                {
                    "_number": 12500,
                    "branch": "release-2.0",
                    "project": "myproject",
                    "status": "MERGED",
                    "subject": "Fix the bug",
                },
            ]

            mock_run_curl.side_effect = [
                json.dumps(detail_response),
                json.dumps(query_response),
            ]
            gerrit_base_url = "https://my-gerrit.com"

            result = await main.get_cherry_picks_of_change(
                "12345", gerrit_base_url=gerrit_base_url
            )

            self.assertIn("Found 2 cherry-pick(s)", result[0]["text"])
            self.assertIn("CL 12400", result[0]["text"])
            self.assertIn("release-1.0", result[0]["text"])
            self.assertIn("CL 12500", result[0]["text"])
            self.assertIn("release-2.0", result[0]["text"])
            # Original should not appear
            self.assertNotIn("CL 12345", result[0]["text"].split(":\n", 1)[1])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_no_cherry_picks(self, mock_run_curl):
        async def run_test():
            detail_response = {
                "_number": 12345,
                "current_revision": "abc123",
                "revisions": {
                    "abc123": {
                        "commit": {
                            "message": (
                                "Fix the bug\n\n"
                                "Change-Id: I1234567890abcdef1234567890abcdef12345678\n"
                            )
                        }
                    }
                },
            }
            query_response = [
                {
                    "_number": 12345,
                    "branch": "master",
                    "project": "myproject",
                    "status": "MERGED",
                    "subject": "Fix the bug",
                },
            ]

            mock_run_curl.side_effect = [
                json.dumps(detail_response),
                json.dumps(query_response),
            ]
            gerrit_base_url = "https://my-gerrit.com"

            result = await main.get_cherry_picks_of_change(
                "12345", gerrit_base_url=gerrit_base_url
            )

            self.assertIn("No cherry-picks found", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_no_change_id_in_commit(self, mock_run_curl):
        async def run_test():
            detail_response = {
                "_number": 12345,
                "current_revision": "abc123",
                "revisions": {
                    "abc123": {
                        "commit": {
                            "message": "Fix the bug without Change-Id footer"
                        }
                    }
                },
            }

            mock_run_curl.return_value = json.dumps(detail_response)
            gerrit_base_url = "https://my-gerrit.com"

            result = await main.get_cherry_picks_of_change(
                "12345", gerrit_base_url=gerrit_base_url
            )

            self.assertIn("Could not find Change-Id", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_fetch_details_failure(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = Exception("Connection refused")
            gerrit_base_url = "https://my-gerrit.com"

            result = await main.get_cherry_picks_of_change(
                "12345", gerrit_base_url=gerrit_base_url
            )

            self.assertIn("Failed to fetch details", result[0]["text"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
