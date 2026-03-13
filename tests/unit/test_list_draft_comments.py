import asyncio
import json
import unittest
from unittest.mock import patch, AsyncMock

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
                        "message": "This needs fixing.",
                    },
                    {
                        "id": "draft-002",
                        "line": 25,
                        "message": "Consider refactoring this block.",
                    },
                ],
                "README.md": [
                    {
                        "id": "draft-003",
                        "line": 3,
                        "message": "Typo here.",
                    }
                ],
            }
            mock_run_curl.return_value = json.dumps(mock_response)

            result = await main.list_draft_comments(
                change_id="789",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            text = result[0]["text"]
            self.assertIn("Draft comments on CL 789", text)
            self.assertIn("File: src/main.py", text)
            self.assertIn("[draft-001] L10", text)
            self.assertIn("This needs fixing.", text)
            self.assertIn("[draft-002] L25", text)
            self.assertIn("File: README.md", text)
            self.assertIn("[draft-003] L3", text)
            self.assertIn("Total: 3 draft(s)", text)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_list_draft_comments_empty(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({})

            result = await main.list_draft_comments(
                change_id="789",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertIn("No draft comments on CL 789", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_list_draft_comments_parse_error(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "not valid json"

            result = await main.list_draft_comments(
                change_id="789",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertIn("Failed to parse drafts response", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_list_draft_comments_truncates_long_messages(self, mock_run_curl):
        async def run_test():
            long_message = "x" * 200
            mock_response = {
                "file.py": [
                    {"id": "d1", "line": 1, "message": long_message},
                ],
            }
            mock_run_curl.return_value = json.dumps(mock_response)

            result = await main.list_draft_comments(
                change_id="789",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            text = result[0]["text"]
            # Preview is truncated to 120 chars
            self.assertNotIn("x" * 200, text)
            self.assertIn("x" * 120, text)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
