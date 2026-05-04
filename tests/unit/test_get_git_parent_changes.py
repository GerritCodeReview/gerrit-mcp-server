import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server import main

GERRIT_BASE_URL = "https://gerrit.example.com"

CHANGE_PARENT = {
    "_number": 1001,
    "subject": "parent: some work",
    "work_in_progress": False,
}

CHANGE_PARENT_WIP = {
    "_number": 1002,
    "subject": "parent: draft work",
    "work_in_progress": True,
}


class TestGetGitParentChanges(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_returns_structured_result(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps([CHANGE_PARENT])

            result = await main.get_git_parent_changes(
                "2000", gerrit_base_url=GERRIT_BASE_URL
            )

            self.assertEqual(result["change_id"], "2000")
            self.assertEqual(len(result["parent_changes"]), 1)
            self.assertEqual(result["parent_changes"][0]["change_number"], 1001)
            self.assertEqual(
                result["parent_changes"][0]["subject"], "parent: some work"
            )
            self.assertFalse(result["parent_changes"][0]["work_in_progress"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_wip_flag_preserved(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps([CHANGE_PARENT_WIP])

            result = await main.get_git_parent_changes(
                "2000", gerrit_base_url=GERRIT_BASE_URL
            )

            self.assertTrue(result["parent_changes"][0]["work_in_progress"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_multiple_parents(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps([CHANGE_PARENT, CHANGE_PARENT_WIP])

            result = await main.get_git_parent_changes(
                "2000", gerrit_base_url=GERRIT_BASE_URL
            )

            self.assertEqual(len(result["parent_changes"]), 2)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_empty_returns_structured_response(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps([])

            result = await main.get_git_parent_changes(
                "2000", gerrit_base_url=GERRIT_BASE_URL
            )

            self.assertEqual(result["change_id"], "2000")
            self.assertEqual(result["parent_changes"], [])
            self.assertIn("note", result)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_json_decode_error_raises(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "not valid json"

            with self.assertRaises(Exception) as ctx:
                await main.get_git_parent_changes(
                    "2000", gerrit_base_url=GERRIT_BASE_URL
                )

            self.assertIn("Failed to parse", str(ctx.exception))

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_curl_exception_raises(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = Exception("connection refused")

            with self.assertRaises(Exception) as ctx:
                await main.get_git_parent_changes(
                    "2000", gerrit_base_url=GERRIT_BASE_URL
                )

            self.assertIn("connection refused", str(ctx.exception))

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
