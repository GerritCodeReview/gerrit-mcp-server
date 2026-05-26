import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server import main

GERRIT_BASE_URL = "https://gerrit.example.com"

FULL_MESSAGE = (
    "Add a thing\n\n"
    "Body paragraph explaining the thing.\n\n"
    "Bug: 12345\n"
    "Change-Id: I0123456789abcdef0123456789abcdef01234567\n"
)


class TestGetCommitMessage(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_returns_verbatim_message(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({"full_message": FULL_MESSAGE})

            result = await main.get_commit_message(
                "2000", gerrit_base_url=GERRIT_BASE_URL
            )

            self.assertEqual(result["change_id"], "2000")
            self.assertEqual(result["verbatim_commit_message"], FULL_MESSAGE)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_missing_full_message_falls_back(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({})

            result = await main.get_commit_message(
                "2000", gerrit_base_url=GERRIT_BASE_URL
            )

            self.assertEqual(result["verbatim_commit_message"], "Message not found.")

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_json_decode_error_raises(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "not valid json"

            with self.assertRaises(ValueError) as ctx:
                await main.get_commit_message("2000", gerrit_base_url=GERRIT_BASE_URL)

            self.assertIn("Failed to parse", str(ctx.exception))

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_curl_exception_raises(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = Exception("connection refused")

            with self.assertRaises(Exception) as ctx:
                await main.get_commit_message("2000", gerrit_base_url=GERRIT_BASE_URL)

            self.assertIn("connection refused", str(ctx.exception))

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
