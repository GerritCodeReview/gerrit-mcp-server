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
            # First call: list to find patch_set; second call: DELETE.
            list_response = {
                "src/foo.py": [
                    {"id": "draft-abc", "patch_set": 4, "line": 7, "message": "hi"},
                ],
            }
            mock_run_curl.side_effect = [json.dumps(list_response), ""]

            result = await main.delete_draft_comment(
                change_id="123",
                draft_id="draft-abc",
                gerrit_base_url=BASE_URL,
            )

            self.assertIn(
                "Deleted draft comment draft-abc (PS4) on CL 123", result[0]["text"]
            )
            self.assertEqual(mock_run_curl.call_count, 2)
            # Verify DELETE used the draft's actual patchset, not /current/.
            delete_args = mock_run_curl.call_args_list[1][0][0]
            self.assertIn("-X", delete_args)
            self.assertIn("DELETE", delete_args)
            self.assertIn(
                f"{BASE_URL}/changes/123/revisions/4/drafts/draft-abc",
                delete_args,
            )
            self.assertNotIn("revisions/current", " ".join(delete_args))

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_single_draft_not_found(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({})  # no drafts

            result = await main.delete_draft_comment(
                change_id="123",
                draft_id="draft-xyz",
                gerrit_base_url=BASE_URL,
            )

            self.assertIn("not found on CL 123", result[0]["text"])
            # Only the list call — no DELETE attempt.
            self.assertEqual(mock_run_curl.call_count, 1)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_single_draft_exception(self, mock_run_curl):
        async def run_test():
            list_response = {
                "f.py": [{"id": "draft-abc", "patch_set": 6}],
            }
            mock_run_curl.side_effect = [
                json.dumps(list_response),
                Exception("Server error"),
            ]

            with self.assertRaises(Exception):
                await main.delete_draft_comment(
                    change_id="123",
                    draft_id="draft-abc",
                    gerrit_base_url=BASE_URL,
                )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_single_draft_refused_by_gerrit(self, mock_run_curl):
        """Gerrit answers a delete with an empty body; any text is a refusal."""

        async def run_test():
            list_response = {"f.py": [{"id": "draft-abc", "patch_set": 6}]}
            mock_run_curl.side_effect = [
                json.dumps(list_response),
                "Not found: draft-abc",
            ]

            with self.assertRaises(ValueError) as context:
                await main.delete_draft_comment(
                    change_id="123",
                    draft_id="draft-abc",
                    gerrit_base_url=BASE_URL,
                )

            self.assertIn("Not found: draft-abc", str(context.exception))

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
