import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

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
    def test_post_draft_comment_patchset_level(self, mock_run_curl):
        """Without line_number the draft goes to the whole file or patch set."""

        async def run_test():
            mock_run_curl.return_value = json.dumps({"id": "draft-abc123"})

            result = await main.post_draft_comment(
                change_id="456",
                file_path="/PATCHSET_LEVEL",
                message="The Dockerfile outside the diff needs the same fix.",
            )

            self.assertEqual(
                result[0]["text"],
                "Draft comment created on CL 456, file /PATCHSET_LEVEL.",
            )
            curl_args = mock_run_curl.call_args[0][0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["path"], "/PATCHSET_LEVEL")
            self.assertNotIn("line", payload)

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
            self.assertIn("src/main.py at line 12", result[0]["text"])

            args, _ = mock_run_curl.call_args
            curl_args = args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["range"]["start_line"], 8)
            self.assertEqual(payload["range"]["end_line"], 12)
            # line should equal end_line when range is provided
            self.assertEqual(payload["line"], 12)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_draft_comment_range_without_line_number(self, mock_run_curl):
        """A range alone puts the draft on its end_line, not on the whole file."""

        async def run_test():
            mock_run_curl.return_value = json.dumps({"id": "draft-abc123"})

            result = await main.post_draft_comment(
                change_id="456",
                file_path="src/main.py",
                message="Multi-line comment",
                start_line=8,
                start_character=0,
                end_line=12,
                end_character=5,
            )

            self.assertIn("src/main.py at line 12", result[0]["text"])
            curl_args = mock_run_curl.call_args[0][0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["line"], 12)
            self.assertEqual(
                payload["range"],
                {
                    "start_line": 8,
                    "start_character": 0,
                    "end_line": 12,
                    "end_character": 5,
                },
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_draft_comment_partial_range_rejected(self, mock_run_curl):
        """A range missing a field fails instead of becoming a file comment."""

        async def run_test():
            mock_run_curl.return_value = json.dumps({"id": "draft-abc123"})

            result = await main.post_draft_comment(
                change_id="456",
                file_path="src/main.py",
                message="Multi-line comment",
                start_line=8,
                end_line=12,
            )

            self.assertIn("Failed to create draft comment", result[0]["text"])
            self.assertIn("start_character, end_character", result[0]["text"])
            mock_run_curl.assert_not_called()

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_draft_comment_with_in_reply_to(self, mock_run_curl):
        async def run_test():
            parent_comments = {
                "src/main.py": [{"id": "comment-abc123", "patch_set": 2, "line": 10}]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                json.dumps({"id": "draft-reply-1"}),
            ]

            result = await main.post_draft_comment(
                change_id="456",
                file_path="src/main.py",
                line_number=10,
                message="Good point, fixed.",
                in_reply_to="comment-abc123",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertIn("Draft comment created", result[0]["text"])

            args, _ = mock_run_curl.call_args
            curl_args = args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["in_reply_to"], "comment-abc123")
            self.assertEqual(
                curl_args[-1],
                "https://gerrit-review.googlesource.com/changes/456/revisions/2/drafts",
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_posts_on_parent_patch_set(self, mock_run_curl):
        """Gerrit takes a reply only on the patch set of its parent comment."""

        async def run_test():
            parent_comments = {
                "src/main.py": [{"id": "parent-ps3", "patch_set": 3, "line": 42}]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                json.dumps({"id": "draft-ps3"}),
            ]

            await main.post_draft_comment(
                change_id="456",
                message="Done.",
                in_reply_to="parent-ps3",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            curl_args = mock_run_curl.call_args_list[1].args[0]
            self.assertEqual(
                curl_args[-1],
                "https://gerrit-review.googlesource.com/changes/456/revisions/3/drafts",
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_inherits_side_from_parent(self, mock_run_curl):
        """A reply to a comment on the base side stays on the same base."""

        async def run_test():
            parent_comments = {
                "src/main.py": [
                    {
                        "id": "parent-base",
                        "patch_set": 1,
                        "line": 5,
                        "side": "PARENT",
                        "parent": 2,
                    }
                ]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                json.dumps({"id": "draft-base"}),
            ]

            await main.post_draft_comment(
                change_id="456", message="Done.", in_reply_to="parent-base"
            )

            curl_args = mock_run_curl.call_args_list[1].args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["side"], "PARENT")
            self.assertEqual(payload["parent"], 2)
            self.assertEqual(payload["line"], 5)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_on_another_file_takes_no_location(self, mock_run_curl):
        """A reply moved to the patch set level keeps no line of its parent."""

        async def run_test():
            parent_comments = {
                "src/main.py": [
                    {
                        "id": "parent-line",
                        "patch_set": 4,
                        "line": 42,
                        "range": {
                            "start_line": 42,
                            "start_character": 4,
                            "end_line": 42,
                            "end_character": 18,
                        },
                    }
                ]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                json.dumps({"id": "draft-ps-level"}),
            ]

            await main.post_draft_comment(
                change_id="456",
                message="Answered in the commit message.",
                file_path="/PATCHSET_LEVEL",
                in_reply_to="parent-line",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            curl_args = mock_run_curl.call_args_list[1].args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["path"], "/PATCHSET_LEVEL")
            for key in ("line", "range", "side"):
                self.assertNotIn(key, payload)
            self.assertEqual(
                curl_args[-1],
                "https://gerrit-review.googlesource.com/changes/456/revisions/4/drafts",
            )

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

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_inherits_path_line_and_range_from_parent(self, mock_run_curl):
        async def run_test():
            parent_comments = {
                "src/main.py": [
                    {
                        "id": "parent-1",
                        "line": 42,
                        "range": {
                            "start_line": 42,
                            "start_character": 4,
                            "end_line": 42,
                            "end_character": 18,
                        },
                        "message": "private?",
                    }
                ]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                json.dumps({"id": "draft-abc"}),
            ]

            result = await main.post_draft_comment(
                change_id="456",
                message="Done.",
                in_reply_to="parent-1",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertIn("Draft comment created", result[0]["text"])
            self.assertIn("src/main.py", result[0]["text"])
            self.assertIn("line 42", result[0]["text"])

            put_call = mock_run_curl.call_args_list[1]
            curl_args = put_call.args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["path"], "src/main.py")
            self.assertEqual(payload["line"], 42)
            self.assertEqual(payload["in_reply_to"], "parent-1")
            self.assertEqual(payload["range"]["start_character"], 4)
            self.assertEqual(payload["range"]["end_character"], 18)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_to_line_only_parent_inherits_line_no_range(self, mock_run_curl):
        async def run_test():
            parent_comments = {
                "src/main.py": [
                    {
                        "id": "parent-2",
                        "line": 7,
                        "message": "nit",
                    }
                ]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                json.dumps({"id": "draft-xyz"}),
            ]

            await main.post_draft_comment(
                change_id="456",
                message="Done.",
                in_reply_to="parent-2",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            put_call = mock_run_curl.call_args_list[1]
            curl_args = put_call.args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["path"], "src/main.py")
            self.assertEqual(payload["line"], 7)
            self.assertNotIn("range", payload)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_to_patchset_level_parent(self, mock_run_curl):
        """A reply to a patch-set-level comment stays patch-set-level."""

        async def run_test():
            parent_comments = {
                "/PATCHSET_LEVEL": [{"id": "parent-ps", "message": "Rebase?"}]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                json.dumps({"id": "draft-ps"}),
            ]

            result = await main.post_draft_comment(
                change_id="456", message="Done.", in_reply_to="parent-ps"
            )

            self.assertEqual(
                result[0]["text"],
                "Draft comment created on CL 456, file /PATCHSET_LEVEL.",
            )
            curl_args = mock_run_curl.call_args_list[1].args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["path"], "/PATCHSET_LEVEL")
            self.assertNotIn("line", payload)
            self.assertEqual(payload["in_reply_to"], "parent-ps")

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_explicit_range_overrides_parent_range(self, mock_run_curl):
        async def run_test():
            parent_comments = {
                "src/main.py": [
                    {
                        "id": "parent-3",
                        "line": 42,
                        "range": {
                            "start_line": 42,
                            "start_character": 4,
                            "end_line": 42,
                            "end_character": 18,
                        },
                        "message": "...",
                    }
                ]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                json.dumps({"id": "draft-ovr"}),
            ]

            await main.post_draft_comment(
                change_id="456",
                message="Done.",
                in_reply_to="parent-3",
                start_line=100,
                start_character=0,
                end_line=105,
                end_character=10,
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            put_call = mock_run_curl.call_args_list[1]
            curl_args = put_call.args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["range"]["start_line"], 100)
            self.assertEqual(payload["range"]["end_line"], 105)
            self.assertEqual(payload["line"], 105)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_parent_not_found_returns_error(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({"src/main.py": [{"id": "other"}]})

            result = await main.post_draft_comment(
                change_id="456",
                message="Done.",
                in_reply_to="missing-id",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertIn(
                "parent comment 'missing-id' was not found", result[0]["text"]
            )
            self.assertEqual(mock_run_curl.call_count, 1)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_missing_file_path_without_reply_returns_error(self, mock_run_curl):
        async def run_test():
            result = await main.post_draft_comment(
                change_id="456",
                message="hi",
                line_number=10,
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertIn("file_path is required", result[0]["text"])
            mock_run_curl.assert_not_called()

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
