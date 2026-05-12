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


GERRIT_BASE_URL = "https://my-gerrit.com"


def _related_response(changes):
    """Build a related changes API response."""
    return json.dumps({"changes": changes})


def _cherry_pick_response(change_number, subject):
    """Build a cherry-pick API success response (no current_revision)."""
    return json.dumps(
        {
            "id": f"myProject~release~I{change_number}",
            "_number": change_number,
            "subject": subject,
        }
    )


def _detail_response(change_number, current_revision):
    """Build a change detail response with CURRENT_REVISION."""
    return json.dumps(
        {
            "_number": change_number,
            "current_revision": current_revision,
        }
    )


class TestCherryPickChain(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_chain_success(self, mock_run_curl):
        async def run_test():
            # Arrange — 3 related changes in child-first order (as Gerrit returns)
            # The tool should reverse them and cherry-pick 100 -> 200 -> 300
            related = [
                {"_change_number": 300, "_revision_number": 3},
                {"_change_number": 200, "_revision_number": 2},
                {"_change_number": 100, "_revision_number": 1},
            ]
            mock_run_curl.side_effect = [
                _related_response(related),
                _cherry_pick_response(1001, "CP of 100"),
                _detail_response(1001, "sha_a"),
                _cherry_pick_response(1002, "CP of 200"),
                _detail_response(1002, "sha_b"),
                _cherry_pick_response(1003, "CP of 300"),
                _detail_response(1003, "sha_c"),
            ]

            # Act
            result = await main.cherry_pick_chain(
                "300", "release-branch", gerrit_base_url=GERRIT_BASE_URL
            )

            # Assert
            text = result[0]["text"]
            self.assertIn("Successfully cherry-picked chain of 3 changes", text)
            self.assertIn("CL 100 -> new CL 1001", text)
            self.assertIn("CL 200 -> new CL 1002", text)
            self.assertIn("CL 300 -> new CL 1003", text)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_chain_reverses_related_order(self, mock_run_curl):
        async def run_test():
            # Arrange — /related returns child-first: 200, 100
            # Tool must reverse to cherry-pick 100 first, then 200
            related = [
                {"_change_number": 200, "_revision_number": 2},
                {"_change_number": 100, "_revision_number": 1},
            ]
            mock_run_curl.side_effect = [
                _related_response(related),
                _cherry_pick_response(1001, "CP of 100"),
                _detail_response(1001, "sha_first"),
                _cherry_pick_response(1002, "CP of 200"),
                _detail_response(1002, "sha_second"),
            ]

            # Act
            await main.cherry_pick_chain(
                "200", "release-branch", gerrit_base_url=GERRIT_BASE_URL
            )

            # Assert — verify cherry-pick order via curl call URLs
            calls = mock_run_curl.call_args_list
            # Call 0: GET related
            # Call 1: POST cherry-pick CL 100 (parent first)
            first_cp_url = calls[1][0][0][-1]
            self.assertIn("/changes/100/", first_cp_url)
            # Call 3: POST cherry-pick CL 200 (child second)
            second_cp_url = calls[3][0][0][-1]
            self.assertIn("/changes/200/", second_cp_url)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_chain_passes_base_commit(self, mock_run_curl):
        async def run_test():
            # Arrange — child-first from API
            related = [
                {"_change_number": 200, "_revision_number": 2},
                {"_change_number": 100, "_revision_number": 1},
            ]
            mock_run_curl.side_effect = [
                _related_response(related),
                # CL 100 (parent): cherry-pick + detail
                _cherry_pick_response(1001, "CP of 100"),
                _detail_response(1001, "sha_first"),
                # CL 200 (child): cherry-pick + detail
                _cherry_pick_response(1002, "CP of 200"),
                _detail_response(1002, "sha_second"),
            ]

            # Act
            await main.cherry_pick_chain(
                "200", "release-branch", gerrit_base_url=GERRIT_BASE_URL
            )

            # Assert — first cherry-pick should NOT have base,
            # second should have base=sha_first
            calls = mock_run_curl.call_args_list

            # Call 1: POST cherry-pick CL 100
            first_cp_args = calls[1][0][0]
            first_payload = json.loads(
                first_cp_args[first_cp_args.index("--data") + 1]
            )
            self.assertNotIn("base", first_payload)

            # Call 2: GET detail for new CL 1001
            detail_url = calls[2][0][0][0]
            self.assertIn("/changes/1001", detail_url)
            self.assertIn("o=CURRENT_REVISION", detail_url)

            # Call 3: POST cherry-pick CL 200
            second_cp_args = calls[3][0][0]
            second_payload = json.loads(
                second_cp_args[second_cp_args.index("--data") + 1]
            )
            self.assertEqual(second_payload["base"], "sha_first")

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_chain_no_related_changes(self, mock_run_curl):
        async def run_test():
            # Arrange — empty relation chain
            mock_run_curl.return_value = json.dumps({"changes": []})

            # Act
            result = await main.cherry_pick_chain(
                "12345", "release-branch", gerrit_base_url=GERRIT_BASE_URL
            )

            # Assert
            text = result[0]["text"]
            self.assertIn("No related changes found", text)
            self.assertIn("cherry_pick_change", text)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_chain_failure_mid_chain_with_partial_success(self, mock_run_curl):
        async def run_test():
            # Arrange — 3 changes (child-first), second cherry-pick fails
            related = [
                {"_change_number": 300, "_revision_number": 3},
                {"_change_number": 200, "_revision_number": 2},
                {"_change_number": 100, "_revision_number": 1},
            ]
            # After reversing: 100, 200, 300. CL 100 succeeds, CL 200 fails.
            mock_run_curl.side_effect = [
                _related_response(related),
                _cherry_pick_response(1001, "CP of 100"),
                _detail_response(1001, "sha_a"),
                Exception("merge conflict"),  # CL 200 cherry-pick fails
            ]

            # Act
            result = await main.cherry_pick_chain(
                "300", "release-branch", gerrit_base_url=GERRIT_BASE_URL
            )

            # Assert
            text = result[0]["text"]
            self.assertIn("Cherry-pick chain failed at CL 200", text)
            self.assertIn("(2/3)", text)
            self.assertIn("Successfully cherry-picked before failure", text)
            self.assertIn("CL 100 -> new CL 1001", text)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_chain_failure_first_change(self, mock_run_curl):
        async def run_test():
            # Arrange — first cherry-pick fails (after reversing, CL 100 is first)
            related = [
                {"_change_number": 200, "_revision_number": 2},
                {"_change_number": 100, "_revision_number": 1},
            ]
            mock_run_curl.side_effect = [
                _related_response(related),
                Exception("permission denied"),
            ]

            # Act
            result = await main.cherry_pick_chain(
                "200", "release-branch", gerrit_base_url=GERRIT_BASE_URL
            )

            # Assert
            text = result[0]["text"]
            self.assertIn("Cherry-pick chain failed at CL 100", text)
            self.assertIn("(1/2)", text)
            self.assertNotIn("Successfully cherry-picked before failure", text)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_chain_bad_response_mid_chain(self, mock_run_curl):
        async def run_test():
            # Arrange — second cherry-pick returns invalid response (no _number)
            related = [
                {"_change_number": 200, "_revision_number": 2},
                {"_change_number": 100, "_revision_number": 1},
            ]
            # After reversing: 100, 200. CL 100 succeeds, CL 200 bad response.
            mock_run_curl.side_effect = [
                _related_response(related),
                _cherry_pick_response(1001, "CP of 100"),
                _detail_response(1001, "sha_a"),
                json.dumps({"status": "error"}),  # CL 200 bad response
            ]

            # Act
            result = await main.cherry_pick_chain(
                "200", "release-branch", gerrit_base_url=GERRIT_BASE_URL
            )

            # Assert
            text = result[0]["text"]
            self.assertIn("Cherry-pick chain failed at CL 200", text)
            self.assertIn("Successfully cherry-picked before failure", text)
            self.assertIn("CL 100 -> new CL 1001", text)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_chain_fetch_related_fails(self, mock_run_curl):
        async def run_test():
            # Arrange — fetching related changes itself fails
            mock_run_curl.side_effect = Exception("network error")

            # Act
            result = await main.cherry_pick_chain(
                "12345", "release-branch", gerrit_base_url=GERRIT_BASE_URL
            )

            # Assert
            text = result[0]["text"]
            self.assertIn("Failed to fetch related changes", text)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_chain_allow_conflicts_default_true(self, mock_run_curl):
        async def run_test():
            # Arrange
            related = [{"_change_number": 100, "_revision_number": 1}]
            mock_run_curl.side_effect = [
                _related_response(related),
                _cherry_pick_response(1001, "CP of 100"),
                _detail_response(1001, "sha_a"),
            ]

            # Act
            await main.cherry_pick_chain(
                "100", "release-branch", gerrit_base_url=GERRIT_BASE_URL
            )

            # Assert — allow_conflicts should be in the payload by default
            cp_call_args = mock_run_curl.call_args_list[1][0][0]
            payload = json.loads(
                cp_call_args[cp_call_args.index("--data") + 1]
            )
            self.assertTrue(payload.get("allow_conflicts"))

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
