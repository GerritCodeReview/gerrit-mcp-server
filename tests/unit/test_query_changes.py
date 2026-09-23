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
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server import main


def _change(number, updated, **fields):
    return {
        "_number": number,
        "change_id": f"I{number:040d}",
        "project": "my/project",
        "branch": "master",
        "subject": f"Change {number}",
        "status": "NEW",
        "updated": updated,
        **fields,
    }


class TestQueryChanges(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_query_changes_success(self, mock_run_curl):
        async def run_test():
            # Arrange
            mock_run_curl.return_value = json.dumps(
                [
                    _change(456, "2023-01-01T00:00:00.000000000Z"),
                    _change(
                        123,
                        "2023-01-03T00:00:00.000000000Z",
                        branch="stable-3.12",
                        work_in_progress=True,
                    ),
                ]
            )

            # Act
            result = await main.query_changes(
                "status:open", gerrit_base_url="https://my-gerrit.com", limit=5
            )

            # Assert
            self.assertEqual(
                result,
                {
                    "query": "status:open",
                    "changes": [
                        {
                            "number": 123,
                            "change_id": f"I{123:040d}",
                            "project": "my/project",
                            "branch": "stable-3.12",
                            "subject": "Change 123",
                            "status": "NEW",
                            "work_in_progress": True,
                            "updated": "2023-01-03T00:00:00.000000000Z",
                        },
                        {
                            "number": 456,
                            "change_id": f"I{456:040d}",
                            "project": "my/project",
                            "branch": "master",
                            "subject": "Change 456",
                            "status": "NEW",
                            "work_in_progress": False,
                            "updated": "2023-01-01T00:00:00.000000000Z",
                        },
                    ],
                },
            )
            self.assertIn("&n=5", mock_run_curl.call_args[0][0][0])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_query_changes_no_results(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "[]"

            result = await main.query_changes(
                "status:merged", gerrit_base_url="https://my-gerrit.com"
            )

            self.assertEqual(result, {"query": "status:merged", "changes": []})

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_query_changes_malformed_json(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "not json"

            with self.assertRaisesRegex(ValueError, "Raw response: 'not json'"):
                await main.query_changes("status:open")

        asyncio.run(run_test())


class TestQueryChangesByDateAndFilters(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_returns_query_changes_result(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps(
                [_change(123, "2025-08-18T10:00:00.000000000Z")]
            )

            result = await main.query_changes_by_date_and_filters(
                "2025-08-18", "2025-08-19", project="my/project"
            )

            self.assertEqual(
                result["query"],
                "status:merged after:2025-08-18 before:2025-08-20 project:my/project",
            )
            self.assertEqual(
                [(c["number"], c["project"], c["branch"]) for c in result["changes"]],
                [(123, "my/project", "master")],
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_invalid_date_raises(self, mock_run_curl):
        async def run_test():
            with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
                await main.query_changes_by_date_and_filters("18.08.2025", "2025-08-19")
            mock_run_curl.assert_not_called()

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
