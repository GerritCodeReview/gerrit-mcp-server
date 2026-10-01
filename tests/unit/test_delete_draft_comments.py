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
                    {"id": "draft-001"},
                    {"id": "draft-002"},
                ],
                "README.md": [
                    {"id": "draft-003"},
                ],
            }
            # First call returns the list, subsequent calls are deletes
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
            self.assertEqual(mock_run_curl.call_count, 4)  # 1 list + 3 deletes

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

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_all_drafts_partial_failure(self, mock_run_curl):
        async def run_test():
            drafts_response = {
                "file.py": [
                    {"id": "draft-001"},
                    {"id": "draft-002"},
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

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_all_drafts_skips_missing_ids(self, mock_run_curl):
        async def run_test():
            drafts_response = {
                "file.py": [
                    {"id": "draft-001"},
                    {"message": "no id field"},  # missing id
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
            # 1 list + 1 delete (skipped the one without id)
            self.assertEqual(mock_run_curl.call_count, 2)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_all_drafts_on_every_patch_set(self, mock_run_curl):
        async def run_test():
            drafts_response = {
                "a.py": [
                    {"id": "old-draft", "patch_set": 1},
                    {"id": "new-draft", "patch_set": 2},
                ],
            }
            mock_run_curl.side_effect = [json.dumps(drafts_response), "", ""]

            result = await main.delete_draft_comments(
                change_id="123", gerrit_base_url=BASE_URL
            )

            self.assertIn("Deleted 2 draft comment(s)", result[0]["text"])
            urls = [call.args[0][-1] for call in mock_run_curl.call_args_list]
            self.assertEqual(
                urls,
                [
                    f"{BASE_URL}/changes/123/drafts",
                    f"{BASE_URL}/changes/123/revisions/1/drafts/old-draft",
                    f"{BASE_URL}/changes/123/revisions/2/drafts/new-draft",
                ],
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_delete_all_drafts_reports_gerrit_error_body(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = [
                json.dumps({"a.py": [{"id": "draft-001", "patch_set": 1}]}),
                "Not found: draft-001",
            ]

            result = await main.delete_draft_comments(
                change_id="123", gerrit_base_url=BASE_URL
            )

            text = result[0]["text"]
            self.assertIn("Deleted 0 draft comment(s)", text)
            self.assertIn("Not found: draft-001", text)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
