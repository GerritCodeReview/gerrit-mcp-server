import asyncio
import json
import unittest
from unittest.mock import patch, AsyncMock

from gerrit_mcp_server import main


class TestPostDraftComment(unittest.TestCase):

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_draft_comment_success(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({"id": "draft-abc123"})

            result = await main.post_draft_comment(
                change_id="456",
                file_path="src/main.py",
                line_number=10,
                message="This needs a fix.",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertIn("Draft comment created on CL 456", result[0]["text"])
            self.assertIn("src/main.py", result[0]["text"])

            mock_run_curl.assert_called_once()
            args, kwargs = mock_run_curl.call_args
            curl_args = args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["path"], "src/main.py")
            self.assertEqual(payload["line"], 10)
            self.assertEqual(payload["message"], "This needs a fix.")
            self.assertTrue(payload["unresolved"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_draft_comment_with_suggestion(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({"id": "draft-abc123"})

            result = await main.post_draft_comment(
                change_id="456",
                file_path="src/main.py",
                line_number=10,
                message="Consider this instead:",
                suggestion="new_code_here()",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertIn("Draft comment created", result[0]["text"])

            args, _ = mock_run_curl.call_args
            curl_args = args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertIn("```suggestion", payload["message"])
            self.assertIn("new_code_here()", payload["message"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_draft_comment_with_range(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({"id": "draft-abc123"})

            result = await main.post_draft_comment(
                change_id="456",
                file_path="src/main.py",
                line_number=10,
                message="Multi-line comment",
                start_line=8,
                start_character=0,
                end_line=12,
                end_character=5,
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertIn("Draft comment created", result[0]["text"])

            args, _ = mock_run_curl.call_args
            curl_args = args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["range"]["start_line"], 8)
            self.assertEqual(payload["range"]["end_line"], 12)
            # line should equal end_line when range is provided
            self.assertEqual(payload["line"], 12)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_draft_comment_no_id_in_response(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({"error": "something"})

            result = await main.post_draft_comment(
                change_id="456",
                file_path="src/main.py",
                line_number=10,
                message="test",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertIn("Failed to create draft comment", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_draft_comment_exception(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = Exception("Network error")

            with self.assertRaises(Exception):
                await main.post_draft_comment(
                    change_id="456",
                    file_path="src/main.py",
                    line_number=10,
                    message="test",
                    gerrit_base_url="https://gerrit-review.googlesource.com",
                )

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
