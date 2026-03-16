import asyncio
import json
import unittest
from unittest.mock import patch, AsyncMock

from gerrit_mcp_server import main


BASE_URL = "https://gerrit-review.googlesource.com"


class TestDeleteDraftComment(unittest.TestCase):

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_single_draft_success(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = ""

            result = await main.delete_draft_comment(
                change_id="123",
                draft_id="draft-abc",
                gerrit_base_url=BASE_URL,
            )

            self.assertIn("Deleted draft comment draft-abc on CL 123", result[0]["text"])
            mock_run_curl.assert_called_once()
            args, _ = mock_run_curl.call_args
            curl_args = args[0]
            self.assertIn("-X", curl_args)
            self.assertIn("DELETE", curl_args)
            self.assertIn(
                f"{BASE_URL}/changes/123/revisions/current/drafts/draft-abc",
                curl_args,
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_single_draft_exception(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = Exception("Not found")

            with self.assertRaises(Exception):
                await main.delete_draft_comment(
                    change_id="123",
                    draft_id="draft-abc",
                    gerrit_base_url=BASE_URL,
                )

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
