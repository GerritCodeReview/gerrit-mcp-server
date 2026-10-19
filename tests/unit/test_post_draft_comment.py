import asyncio
import base64
import json
import unittest
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server import main


def _base64(text):
    """A file's content as Gerrit's /content endpoint returns it."""
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


_NO_DRAFTS = json.dumps({})


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

            self.assertEqual(
                result,
                {
                    "change_id": "456",
                    "draft_id": "draft-abc123",
                    "revision": "current",
                    "file_path": "src/main.py",
                    "line": 10,
                    "in_reply_to": None,
                },
            )

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

            self.assertEqual(result["file_path"], "/PATCHSET_LEVEL")
            self.assertIsNone(result["line"])
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

            self.assertEqual(result["draft_id"], "draft-abc123")

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

            self.assertEqual(result["line"], 12)

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

            self.assertEqual(result["line"], 12)
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
        """One character offset without the other fails instead of guessing."""

        async def run_test():
            mock_run_curl.return_value = json.dumps({"id": "draft-abc123"})

            with self.assertRaises(ValueError) as context:
                await main.post_draft_comment(
                    change_id="456",
                    file_path="src/main.py",
                    message="Multi-line comment",
                    start_line=8,
                    start_character=2,
                    end_line=12,
                )

            self.assertIn("end_character", str(context.exception))
            mock_run_curl.assert_not_called()

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_line_numbers_alone_select_whole_lines(self, mock_run_curl):
        """The range ends at the end of end_line, where the comment sits."""

        async def run_test():
            content = "line one\nline two\nthird line here\nlast\n"
            mock_run_curl.side_effect = [
                _base64(content),
                json.dumps({"id": "draft-lines"}),
            ]

            result = await main.post_draft_comment(
                change_id="456",
                file_path="src/main.py",
                message="Use a loop here.",
                start_line=2,
                end_line=3,
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertEqual(result["line"], 3)
            content_url = mock_run_curl.call_args_list[0].args[0][-1]
            self.assertEqual(
                content_url,
                "https://gerrit-review.googlesource.com/changes/456/revisions/"
                "current/files/src%2Fmain.py/content",
            )
            curl_args = mock_run_curl.call_args_list[1].args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(
                payload["range"],
                {
                    "start_line": 2,
                    "start_character": 0,
                    "end_line": 3,
                    "end_character": 15,
                },
            )
            self.assertEqual(payload["line"], 3)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_whole_line_range_counts_utf16_code_units(self, mock_run_curl):
        """Gerrit counts characters as Java does: an emoji takes two."""

        async def run_test():
            mock_run_curl.side_effect = [
                _base64("a\U0001f600b\n"),
                json.dumps({"id": "draft-emoji"}),
            ]

            await main.post_draft_comment(
                change_id="456",
                file_path="README.md",
                message="Spell it out.",
                start_line=1,
                end_line=1,
            )

            curl_args = mock_run_curl.call_args_list[1].args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["range"]["end_character"], 4)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_whole_line_range_past_the_end_refused(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = [
                _base64("one\ntwo\nthree\n"),
                json.dumps({"id": "draft-past-end"}),
            ]

            with self.assertRaises(ValueError) as context:
                await main.post_draft_comment(
                    change_id="456",
                    file_path="src/main.py",
                    message="Done.",
                    start_line=2,
                    end_line=5,
                )

            self.assertIn("src/main.py", str(context.exception))
            self.assertIn("3", str(context.exception))
            self.assertEqual(mock_run_curl.call_count, 1)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_whole_lines_on_commit_message_refused(self, mock_run_curl):
        """Gerrit numbers /COMMIT_MSG after a header that its content lacks."""

        async def run_test():
            with self.assertRaises(ValueError) as context:
                await main.post_draft_comment(
                    change_id="456",
                    file_path="/COMMIT_MSG",
                    message="Wrap this paragraph.",
                    start_line=9,
                    end_line=11,
                )

            self.assertIn("start_character", str(context.exception))
            mock_run_curl.assert_not_called()

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_given_parent_lines_keeps_parent_range(self, mock_run_curl):
        """A reply on part of a line on the base side does not read the file."""

        async def run_test():
            parent_range = {
                "start_line": 2,
                "start_character": 4,
                "end_line": 3,
                "end_character": 9,
            }
            parent_comments = {
                "src/main.py": [
                    {
                        "id": "parent",
                        "patch_set": 3,
                        "line": 3,
                        "range": parent_range,
                        "side": "PARENT",
                    }
                ]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                _NO_DRAFTS,
                json.dumps({"id": "draft-reply-lines"}),
            ]

            await main.post_draft_comment(
                change_id="456",
                message="Done.",
                start_line=2,
                end_line=3,
                in_reply_to="parent",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            for call in mock_run_curl.call_args_list:
                self.assertFalse(call.args[0][-1].endswith("/content"))
            curl_args = mock_run_curl.call_args.args[0]
            self.assertTrue(curl_args[-1].endswith("/revisions/3/drafts"))
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["range"], parent_range)
            self.assertEqual(payload["line"], 3)
            self.assertEqual(payload["side"], "PARENT")

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_given_other_lines_refused(self, mock_run_curl):
        async def run_test():
            parent_range = {
                "start_line": 2,
                "start_character": 0,
                "end_line": 3,
                "end_character": 15,
            }
            parent_comments = {
                "src/main.py": [{"id": "parent", "line": 3, "range": parent_range}]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                json.dumps({"id": "draft-other-lines"}),
            ]

            with self.assertRaises(ValueError) as context:
                await main.post_draft_comment(
                    change_id="456",
                    message="Done.",
                    start_line=1,
                    end_line=3,
                    in_reply_to="parent",
                )

            self.assertIn("'start_line': 1", str(context.exception))
            self.assertEqual(mock_run_curl.call_count, 1)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_given_lines_to_parent_without_range_refused(self, mock_run_curl):
        async def run_test():
            parent_comments = {"src/main.py": [{"id": "parent", "line": 7}]}
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                json.dumps({"id": "draft-range"}),
            ]

            with self.assertRaises(ValueError) as context:
                await main.post_draft_comment(
                    change_id="456",
                    message="Done.",
                    start_line=7,
                    end_line=7,
                    in_reply_to="parent",
                )

            self.assertIn("range", str(context.exception))
            self.assertEqual(mock_run_curl.call_count, 1)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_draft_comment_with_in_reply_to(self, mock_run_curl):
        async def run_test():
            parent_comments = {
                "src/main.py": [{"id": "comment-abc123", "patch_set": 2, "line": 10}]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                _NO_DRAFTS,
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

            self.assertEqual(result["revision"], "2")
            self.assertEqual(result["in_reply_to"], "comment-abc123")

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
                _NO_DRAFTS,
                json.dumps({"id": "draft-ps3"}),
            ]

            await main.post_draft_comment(
                change_id="456",
                message="Done.",
                in_reply_to="parent-ps3",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            curl_args = mock_run_curl.call_args.args[0]
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
                _NO_DRAFTS,
                json.dumps({"id": "draft-base"}),
            ]

            await main.post_draft_comment(
                change_id="456", message="Done.", in_reply_to="parent-base"
            )

            curl_args = mock_run_curl.call_args.args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["side"], "PARENT")
            self.assertEqual(payload["parent"], 2)
            self.assertEqual(payload["line"], 5)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_on_another_file_refused(self, mock_run_curl):
        """A reply goes on the file of its parent comment."""

        async def run_test():
            parent_comments = {
                "src/main.py": [{"id": "parent-line", "patch_set": 4, "line": 42}]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                json.dumps({"id": "draft-ps-level"}),
            ]

            with self.assertRaises(ValueError) as context:
                await main.post_draft_comment(
                    change_id="456",
                    message="Answered in the commit message.",
                    file_path="/PATCHSET_LEVEL",
                    in_reply_to="parent-line",
                    gerrit_base_url="https://gerrit-review.googlesource.com",
                )

            self.assertIn("'/PATCHSET_LEVEL'", str(context.exception))
            self.assertIn("'src/main.py'", str(context.exception))
            self.assertEqual(mock_run_curl.call_count, 1)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_on_another_line_refused(self, mock_run_curl):
        """A reply goes on the line of its parent comment."""

        async def run_test():
            parent_comments = {
                "src/main.py": [{"id": "parent-line", "patch_set": 4, "line": 42}]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                json.dumps({"id": "draft-other-line"}),
            ]

            with self.assertRaises(ValueError) as context:
                await main.post_draft_comment(
                    change_id="456",
                    message="Done.",
                    line_number=10,
                    in_reply_to="parent-line",
                )

            self.assertIn("10", str(context.exception))
            self.assertIn("42", str(context.exception))
            self.assertEqual(mock_run_curl.call_count, 1)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_given_parent_line_stays_on_parent_side(self, mock_run_curl):
        """The parent's line, given for a reply, keeps the parent's side."""

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
                _NO_DRAFTS,
                json.dumps({"id": "draft-base"}),
            ]

            await main.post_draft_comment(
                change_id="456",
                message="Done.",
                file_path="src/main.py",
                line_number=5,
                in_reply_to="parent-base",
            )

            curl_args = mock_run_curl.call_args.args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["line"], 5)
            self.assertEqual(payload.get("side"), "PARENT")
            self.assertEqual(payload.get("parent"), 2)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_draft_comment_no_id_in_response(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({"error": "something"})

            with self.assertRaises(ValueError) as context:
                await main.post_draft_comment(
                    change_id="456",
                    file_path="src/main.py",
                    line_number=10,
                    message="test",
                    gerrit_base_url="https://gerrit-review.googlesource.com",
                )

            self.assertIn("something", str(context.exception))

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_draft_comment_gerrit_refusal_keeps_text(self, mock_run_curl):
        """Gerrit refuses in plain text; the error carries that text."""

        async def run_test():
            mock_run_curl.return_value = "Invalid comment in_reply_to."

            with self.assertRaises(ValueError) as context:
                await main.post_draft_comment(
                    change_id="456",
                    file_path="src/main.py",
                    line_number=10,
                    message="test",
                    gerrit_base_url="https://gerrit-review.googlesource.com",
                )

            self.assertIn("Invalid comment in_reply_to.", str(context.exception))

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
                _NO_DRAFTS,
                json.dumps({"id": "draft-abc"}),
            ]

            result = await main.post_draft_comment(
                change_id="456",
                message="Done.",
                in_reply_to="parent-1",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            self.assertEqual(result["file_path"], "src/main.py")
            self.assertEqual(result["line"], 42)

            put_call = mock_run_curl.call_args
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
                _NO_DRAFTS,
                json.dumps({"id": "draft-xyz"}),
            ]

            await main.post_draft_comment(
                change_id="456",
                message="Done.",
                in_reply_to="parent-2",
                gerrit_base_url="https://gerrit-review.googlesource.com",
            )

            put_call = mock_run_curl.call_args
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
                _NO_DRAFTS,
                json.dumps({"id": "draft-ps"}),
            ]

            result = await main.post_draft_comment(
                change_id="456", message="Done.", in_reply_to="parent-ps"
            )

            self.assertEqual(result["file_path"], "/PATCHSET_LEVEL")
            self.assertIsNone(result["line"])
            curl_args = mock_run_curl.call_args.args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["path"], "/PATCHSET_LEVEL")
            self.assertNotIn("line", payload)
            self.assertEqual(payload["in_reply_to"], "parent-ps")

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_with_another_range_refused(self, mock_run_curl):
        """A reply goes on the range of its parent comment."""

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

            with self.assertRaises(ValueError) as context:
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

            self.assertIn("range", str(context.exception))
            self.assertEqual(mock_run_curl.call_count, 1)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_given_parent_range_is_saved_there(self, mock_run_curl):
        async def run_test():
            parent_range = {
                "start_line": 42,
                "start_character": 4,
                "end_line": 42,
                "end_character": 18,
            }
            parent_comments = {
                "src/main.py": [{"id": "parent-3", "line": 42, "range": parent_range}]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                _NO_DRAFTS,
                json.dumps({"id": "draft-same-range"}),
            ]

            await main.post_draft_comment(
                change_id="456",
                message="Done.",
                in_reply_to="parent-3",
                start_line=42,
                start_character=4,
                end_line=42,
                end_character=18,
            )

            curl_args = mock_run_curl.call_args.args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["range"], parent_range)
            self.assertEqual(payload["line"], 42)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_second_own_draft_in_a_thread_refused(self, mock_run_curl):
        """Gerrit would publish both drafts as two replies in one thread."""

        async def run_test():
            published = {
                "src/main.py": [
                    {"id": "root", "patch_set": 2, "line": 5},
                    {"id": "answer", "patch_set": 2, "line": 5, "in_reply_to": "root"},
                ]
            }
            drafts = {
                "src/main.py": [
                    {
                        "id": "my-draft",
                        "patch_set": 2,
                        "line": 5,
                        "in_reply_to": "root",
                        "message": "Will fix.",
                    }
                ]
            }
            mock_run_curl.side_effect = [
                json.dumps(published),
                json.dumps(drafts),
                json.dumps({"id": "second-draft"}),
            ]

            with self.assertRaises(ValueError) as context:
                await main.post_draft_comment(
                    change_id="456", message="Done.", in_reply_to="answer"
                )

            self.assertIn("my-draft", str(context.exception))
            self.assertIn("Will fix.", str(context.exception))
            for call in mock_run_curl.call_args_list:
                self.assertNotIn("PUT", call.args[0])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_own_draft_in_another_thread_allows_the_reply(self, mock_run_curl):
        async def run_test():
            published = {
                "src/main.py": [
                    {"id": "root", "patch_set": 2, "line": 5},
                    {"id": "other-root", "patch_set": 2, "line": 9},
                ]
            }
            drafts = {
                "src/main.py": [
                    {
                        "id": "my-draft",
                        "patch_set": 2,
                        "line": 9,
                        "in_reply_to": "other-root",
                        "message": "Will fix.",
                    }
                ]
            }
            mock_run_curl.side_effect = [
                json.dumps(published),
                json.dumps(drafts),
                json.dumps({"id": "reply-draft"}),
            ]

            result = await main.post_draft_comment(
                change_id="456", message="Done.", in_reply_to="root"
            )

            self.assertEqual(result["draft_id"], "reply-draft")

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_own_draft_that_answers_nothing_allows_the_reply(self, mock_run_curl):
        """A draft on the parent's line without in_reply_to is a thread of its own."""

        async def run_test():
            published = {"src/main.py": [{"id": "root", "patch_set": 2, "line": 5}]}
            drafts = {
                "src/main.py": [
                    {"id": "my-note", "patch_set": 2, "line": 5, "message": "Rename."}
                ]
            }
            mock_run_curl.side_effect = [
                json.dumps(published),
                json.dumps(drafts),
                json.dumps({"id": "reply-draft"}),
            ]

            result = await main.post_draft_comment(
                change_id="456", message="Done.", in_reply_to="root"
            )

            self.assertEqual(result["draft_id"], "reply-draft")

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_parent_not_found_returns_error(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({"src/main.py": [{"id": "other"}]})

            with self.assertRaises(ValueError) as context:
                await main.post_draft_comment(
                    change_id="456",
                    message="Done.",
                    in_reply_to="missing-id",
                    gerrit_base_url="https://gerrit-review.googlesource.com",
                )

            self.assertIn(
                "parent comment 'missing-id' was not found", str(context.exception)
            )
            self.assertEqual(mock_run_curl.call_count, 1)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_missing_file_path_without_reply_returns_error(self, mock_run_curl):
        async def run_test():
            with self.assertRaises(ValueError) as context:
                await main.post_draft_comment(
                    change_id="456",
                    message="hi",
                    line_number=10,
                    gerrit_base_url="https://gerrit-review.googlesource.com",
                )

            self.assertIn("file_path is required", str(context.exception))
            mock_run_curl.assert_not_called()

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
