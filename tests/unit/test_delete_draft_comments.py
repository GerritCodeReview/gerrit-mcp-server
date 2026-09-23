import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server import main

BASE_URL = "https://gerrit-review.googlesource.com"


class TestDeleteDraftComments(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_all_drafts_success(self, mock_run_curl):
        async def run_test():
            drafts_response = {
                "src/main.py": [
                    {"id": "draft-001", "patch_set": 6},
                    {"id": "draft-002", "patch_set": 4},
                ],
                "README.md": [
                    {"id": "draft-003", "patch_set": 6},
                ],
            }
            mock_run_curl.side_effect = [
                json.dumps(drafts_response),
                "",  # delete draft-001
                "",  # delete draft-002
                "",  # delete draft-003
            ]

            result = await main.delete_draft_comments(
                change_id="123", gerrit_base_url=BASE_URL
            )

            self.assertIn("Deleted 3 draft comment(s)", result[0]["text"])
            self.assertEqual(mock_run_curl.call_count, 4)

            # Verify the list call hits the CL-level endpoint (not /current/).
            list_url = mock_run_curl.call_args_list[0][0][0][0]
            self.assertIn("/changes/123/drafts/", list_url)
            self.assertNotIn("revisions/current", list_url)

            # Verify each DELETE used the draft's own patchset.
            delete_urls = [" ".join(c[0][0]) for c in mock_run_curl.call_args_list[1:]]
            self.assertTrue(
                any("/revisions/4/drafts/draft-002" in u for u in delete_urls),
                f"Expected PS4 delete in {delete_urls}",
            )
            self.assertTrue(
                any("/revisions/6/drafts/draft-001" in u for u in delete_urls)
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_all_drafts_empty(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({})

            result = await main.delete_draft_comments(
                change_id="123", gerrit_base_url=BASE_URL
            )

            self.assertIn("No draft comments to delete", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_all_drafts_parse_error(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "not json"

            result = await main.delete_draft_comments(
                change_id="123", gerrit_base_url=BASE_URL
            )

            self.assertIn("Failed to parse drafts response", result[0]["text"])
            self.assertIn("not json", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_all_drafts_partial_failure(self, mock_run_curl):
        async def run_test():
            drafts_response = {
                "file.py": [
                    {"id": "draft-001", "patch_set": 6},
                    {"id": "draft-002", "patch_set": 6},
                ],
            }
            mock_run_curl.side_effect = [
                json.dumps(drafts_response),
                "",  # draft-001 succeeds
                Exception("Server error"),  # draft-002 fails
            ]

            result = await main.delete_draft_comments(
                change_id="123", gerrit_base_url=BASE_URL
            )

            text = result[0]["text"]
            self.assertIn("Deleted 1 draft comment(s)", text)
            self.assertIn("1 error(s)", text)
            self.assertIn("draft-002", text)
            self.assertIn("PS6", text)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_all_drafts_skips_missing_ids_or_patchset(self, mock_run_curl):
        async def run_test():
            drafts_response = {
                "file.py": [
                    {"id": "draft-001", "patch_set": 6},
                    {"message": "no id field", "patch_set": 6},  # missing id
                    {"id": "draft-002"},  # missing patch_set
                ],
            }
            mock_run_curl.side_effect = [
                json.dumps(drafts_response),
                "",  # delete draft-001
            ]

            result = await main.delete_draft_comments(
                change_id="123", gerrit_base_url=BASE_URL
            )

            self.assertIn("Deleted 1 draft comment(s)", result[0]["text"])
            # 1 list + 1 delete (skipped two malformed entries)
            self.assertEqual(mock_run_curl.call_count, 2)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
