import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server import main

BASE_URL = "https://gerrit-review.googlesource.com"


class TestDeleteDraftComment(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_single_draft_success(self, mock_run_curl):
        async def run_test():
            drafts_response = {
                "file.py": [{"id": "draft-abc", "patch_set": 1, "line": 3}],
            }
            mock_run_curl.side_effect = [json.dumps(drafts_response), ""]

            result = await main.delete_draft_comment(
                change_id="123",
                draft_id="draft-abc",
                gerrit_base_url=BASE_URL,
            )

            self.assertIn(
                "Deleted draft comment draft-abc on CL 123", result[0]["text"]
            )
            self.assertEqual(mock_run_curl.call_count, 2)
            list_args, _ = mock_run_curl.call_args_list[0]
            self.assertEqual(list_args[0], [f"{BASE_URL}/changes/123/drafts"])
            delete_args, _ = mock_run_curl.call_args_list[1]
            curl_args = delete_args[0]
            self.assertIn("DELETE", curl_args)
            # Deleted on the patch set the draft belongs to, not "current".
            self.assertIn(
                f"{BASE_URL}/changes/123/revisions/1/drafts/draft-abc",
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

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_single_draft_not_found(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps(
                {"file.py": [{"id": "other-draft", "patch_set": 1}]}
            )

            result = await main.delete_draft_comment(
                change_id="123",
                draft_id="draft-abc",
                gerrit_base_url=BASE_URL,
            )

            self.assertIn(
                "Draft comment draft-abc not found on CL 123", result[0]["text"]
            )
            mock_run_curl.assert_called_once()  # no DELETE was sent

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_single_draft_error_body_raises(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = [
                json.dumps({"file.py": [{"id": "draft-abc", "patch_set": 1}]}),
                "Not found: draft-abc",
            ]

            with self.assertRaises(RuntimeError):
                await main.delete_draft_comment(
                    change_id="123",
                    draft_id="draft-abc",
                    gerrit_base_url=BASE_URL,
                )

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
