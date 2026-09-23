import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server import main


class TestListDraftComments(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_list_draft_comments_success(self, mock_run_curl):
        async def run_test():
            mock_response = {
                "src/main.py": [
                    {
                        "id": "draft-001",
                        "line": 10,
                        "patch_set": 6,
                        "message": "This needs fixing.",
                        "unresolved": True,
                    },
                    {
                        "id": "draft-002",
                        "line": 25,
                        "patch_set": 4,
                        "message": "Done.",
                        "in_reply_to": "parent-1",
                        "unresolved": False,
                    },
                ],
                "README.md": [
                    {"id": "draft-003", "patch_set": 6, "message": "Typo here."}
                ],
            }
            mock_run_curl.return_value = json.dumps(mock_response)

            result = await main.list_draft_comments(
                change_id="789",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertEqual(
                result,
                {
                    "change_id": "789",
                    "drafts": [
                        {
                            "id": "draft-001",
                            "patch_set": 6,
                            "file_path": "src/main.py",
                            "line": 10,
                            "in_reply_to": None,
                            "unresolved": True,
                            "message": "This needs fixing.",
                        },
                        {
                            "id": "draft-002",
                            "patch_set": 4,
                            "file_path": "src/main.py",
                            "line": 25,
                            "in_reply_to": "parent-1",
                            "unresolved": False,
                            "message": "Done.",
                        },
                        {
                            "id": "draft-003",
                            "patch_set": 6,
                            "file_path": "README.md",
                            "line": None,
                            "in_reply_to": None,
                            "unresolved": None,
                            "message": "Typo here.",
                        },
                    ],
                },
            )

            # Verify CL-level endpoint (across all patch sets), not /revisions/current/
            called_url = mock_run_curl.call_args[0][0][0]
            self.assertIn("/changes/789/drafts/", called_url)
            self.assertNotIn("revisions/current", called_url)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_list_draft_comments_empty(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({})

            result = await main.list_draft_comments(
                change_id="789",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertEqual(result, {"change_id": "789", "drafts": []})

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_list_draft_comments_parse_error(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "not valid json"

            with self.assertRaises(ValueError) as context:
                await main.list_draft_comments(
                    change_id="789",
                    gerrit_base_url="https://gerrit-review.googlesource.com",
                )

            self.assertIn("Failed to parse drafts response", str(context.exception))
            self.assertIn("not valid json", str(context.exception))

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_list_draft_comments_keeps_long_messages_whole(self, mock_run_curl):
        async def run_test():
            long_message = "x" * 200
            mock_response = {
                "file.py": [
                    {"id": "d1", "line": 1, "patch_set": 1, "message": long_message},
                ],
            }
            mock_run_curl.return_value = json.dumps(mock_response)

            result = await main.list_draft_comments(
                change_id="789",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertEqual(result["drafts"][0]["message"], long_message)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
