import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server import main

GERRIT_BASE_URL = "https://gerrit.example.com"

GERRIT_COMMIT_RESPONSE = {
    "commit": "c0ffee1234567890",
    "parents": [{"commit": "1a2bdef", "subject": "base: refactor shell init"}],
    "author": {
        "name": "Alice",
        "email": "alice@example.com",
        "date": "2026-05-18 10:50:00.000000000",
    },
    "committer": {
        "name": "Bob",
        "email": "bob@example.com",
        "date": "2026-05-18 11:00:00.000000000",
    },
    "subject": "feature: add new thing",
    "message": "feature: add new thing\n\nChange-Id: I9031abc\n",
}


class TestGetRevisionCommit(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_returns_mapped_fields(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps(GERRIT_COMMIT_RESPONSE)

            result = await main.get_revision_commit(
                "6871423", gerrit_base_url=GERRIT_BASE_URL
            )

            data = result
            self.assertEqual(data["change_id"], "6871423")
            self.assertEqual(data["revision_id"], "current")

            commit = data["commit"]
            self.assertEqual(commit["commit_sha"], "c0ffee1234567890")
            self.assertEqual(len(commit["parents"]), 1)
            self.assertEqual(commit["parents"][0]["commit_sha"], "1a2bdef")
            self.assertEqual(
                commit["parents"][0]["subject"], "base: refactor shell init"
            )
            self.assertEqual(commit["author"]["name"], "Alice")
            self.assertEqual(commit["author"]["email"], "alice@example.com")
            self.assertEqual(commit["author"]["date"], "2026-05-18 10:50:00.000000000")
            self.assertEqual(commit["committer"]["name"], "Bob")
            self.assertEqual(commit["subject"], "feature: add new thing")
            self.assertEqual(
                commit["message"], "feature: add new thing\n\nChange-Id: I9031abc\n"
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_default_revision_id(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps(GERRIT_COMMIT_RESPONSE)

            result = await main.get_revision_commit(
                "6871423", gerrit_base_url=GERRIT_BASE_URL
            )

            data = result
            self.assertEqual(data["revision_id"], "current")
            call_url = mock_run_curl.call_args[0][0][0]
            self.assertIn("current", call_url)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_custom_revision_id(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps(GERRIT_COMMIT_RESPONSE)

            result = await main.get_revision_commit(
                "6871423",
                revision_id="abc123sha",
                gerrit_base_url=GERRIT_BASE_URL,
            )

            data = result
            self.assertEqual(data["revision_id"], "abc123sha")
            call_url = mock_run_curl.call_args[0][0][0]
            self.assertIn("abc123sha", call_url)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_empty_parents_root_commit(self, mock_run_curl):
        async def run_test():
            response = dict(GERRIT_COMMIT_RESPONSE)
            response["parents"] = []
            mock_run_curl.return_value = json.dumps(response)

            result = await main.get_revision_commit(
                "6871423", gerrit_base_url=GERRIT_BASE_URL
            )

            data = result
            self.assertEqual(data["commit"]["parents"], [])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_multiple_parents_merge_commit(self, mock_run_curl):
        async def run_test():
            response = dict(GERRIT_COMMIT_RESPONSE)
            response["parents"] = [
                {"commit": "parent1sha", "subject": "first parent"},
                {"commit": "parent2sha", "subject": "second parent"},
            ]
            mock_run_curl.return_value = json.dumps(response)

            result = await main.get_revision_commit(
                "6871423", gerrit_base_url=GERRIT_BASE_URL
            )

            data = result
            parents = data["commit"]["parents"]
            self.assertEqual(len(parents), 2)
            self.assertEqual(parents[0]["commit_sha"], "parent1sha")
            self.assertEqual(parents[0]["subject"], "first parent")
            self.assertEqual(parents[1]["commit_sha"], "parent2sha")
            self.assertEqual(parents[1]["subject"], "second parent")

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_verbatim_message(self, mock_run_curl):
        async def run_test():
            verbatim = "some subject\n\nBug: b/12345\nChange-Id: Iabc\nCRs-Fixed: 999\n"
            response = dict(GERRIT_COMMIT_RESPONSE)
            response["message"] = verbatim
            mock_run_curl.return_value = json.dumps(response)

            result = await main.get_revision_commit(
                "6871423", gerrit_base_url=GERRIT_BASE_URL
            )

            data = result
            self.assertEqual(data["commit"]["message"], verbatim)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_json_decode_error(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "not valid json"

            with self.assertRaises(ValueError) as ctx:
                await main.get_revision_commit(
                    "6871423", gerrit_base_url=GERRIT_BASE_URL
                )

            self.assertIn("Failed to parse", str(ctx.exception))

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_curl_exception_404(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = Exception("404 Not Found")

            with self.assertRaises(Exception) as ctx:
                await main.get_revision_commit(
                    "6871423", gerrit_base_url=GERRIT_BASE_URL
                )

            self.assertIn("6871423", str(ctx.exception))
            self.assertIn("404 Not Found", str(ctx.exception))

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
