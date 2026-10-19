import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server.main import post_review_comment

GERRIT_BASE_URL = "https://gerrit-review.googlesource.com"

PARENT_RANGE = {
    "start_line": 42,
    "start_character": 4,
    "end_line": 42,
    "end_character": 18,
}

PARENT_ON_PS3 = {
    "src/main.py": [
        {
            "id": "parent-1",
            "patch_set": 3,
            "line": 42,
            "range": PARENT_RANGE,
            "message": "private?",
        }
    ]
}


def _sent_payload(curl_args):
    return json.loads(curl_args[curl_args.index("--data") + 1])


def _change_with_current_patch_set(number):
    """A ChangeInfo with CURRENT_REVISION, as Gerrit 3.9 and older return it."""
    return {"current_revision": "c0ffee", "revisions": {"c0ffee": {"_number": number}}}


class TestPostReviewComment(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_review_comment_with_labels(self, mock_run_curl):
        mock_run_curl.return_value = '{"labels": {"Verified": 1}}'
        result = asyncio.run(
            post_review_comment(
                change_id="123",
                file_path="test.py",
                line_number=1,
                message="test comment",
                labels={"Verified": 1},
                gerrit_base_url=GERRIT_BASE_URL,
            )
        )
        self.assertEqual(
            result,
            {
                "change_id": "123",
                "revision": "current",
                "file_path": "test.py",
                "line": 1,
                "in_reply_to": None,
            },
        )
        expected_payload_str = (
            '{"comments": {"test.py": [{"line": 1, "message": "test comment",'
            ' "unresolved": true}]}, "labels": {"Verified": 1}}'
        )
        mock_run_curl.assert_called_with(
            [
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "--data",
                expected_payload_str,
                "https://gerrit-review.googlesource.com/changes/123/revisions/current/review",
            ],
            "https://gerrit-review.googlesource.com",
        )

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_posts_on_parent_patch_set_and_location(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = [json.dumps(PARENT_ON_PS3), '{"comments": {}}']

            result = await post_review_comment(
                change_id="123",
                message="Done.",
                in_reply_to="parent-1",
                unresolved=False,
                gerrit_base_url=GERRIT_BASE_URL,
            )

            self.assertEqual(
                result,
                {
                    "change_id": "123",
                    "revision": "3",
                    "file_path": "src/main.py",
                    "line": 42,
                    "in_reply_to": "parent-1",
                },
            )
            curl_args = mock_run_curl.call_args_list[1].args[0]
            self.assertEqual(
                curl_args[-1], f"{GERRIT_BASE_URL}/changes/123/revisions/3/review"
            )
            self.assertEqual(
                _sent_payload(curl_args),
                {
                    "comments": {
                        "src/main.py": [
                            {
                                "line": 42,
                                "message": "Done.",
                                "unresolved": False,
                                "range": PARENT_RANGE,
                                "in_reply_to": "parent-1",
                            }
                        ]
                    }
                },
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_to_patchset_level_parent(self, mock_run_curl):
        async def run_test():
            parent_comments = {
                "/PATCHSET_LEVEL": [
                    {"id": "parent-ps", "patch_set": 2, "message": "Rebase?"}
                ]
            }
            mock_run_curl.side_effect = [
                json.dumps(parent_comments),
                '{"comments": {}}',
            ]

            await post_review_comment(
                change_id="123",
                message="Done.",
                in_reply_to="parent-ps",
                gerrit_base_url=GERRIT_BASE_URL,
            )

            curl_args = mock_run_curl.call_args_list[1].args[0]
            self.assertEqual(
                curl_args[-1], f"{GERRIT_BASE_URL}/changes/123/revisions/2/review"
            )
            self.assertEqual(
                _sent_payload(curl_args)["comments"],
                {
                    "/PATCHSET_LEVEL": [
                        {
                            "message": "Done.",
                            "unresolved": True,
                            "in_reply_to": "parent-ps",
                        }
                    ]
                },
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_parent_not_found_returns_error(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({"src/main.py": [{"id": "other"}]})

            with self.assertRaises(ValueError) as context:
                await post_review_comment(
                    change_id="123",
                    message="Done.",
                    in_reply_to="missing-id",
                    gerrit_base_url=GERRIT_BASE_URL,
                )

            self.assertIn(
                "parent comment 'missing-id' was not found", str(context.exception)
            )
            self.assertEqual(mock_run_curl.call_count, 2)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_to_own_unpublished_draft_explained(self, mock_run_curl):
        """Gerrit takes a reply only to a published comment."""

        async def run_test():
            drafts = {
                "src/main.py": [
                    {"id": "my-draft", "patch_set": 3, "line": 42, "message": "nit"}
                ]
            }
            mock_run_curl.side_effect = [
                json.dumps({}),
                json.dumps(drafts),
                '{"comments": {}}',
            ]

            with self.assertRaises(ValueError) as context:
                await post_review_comment(
                    change_id="123",
                    message="Also here.",
                    in_reply_to="my-draft",
                    gerrit_base_url=GERRIT_BASE_URL,
                )

            self.assertIn("unpublished draft", str(context.exception))
            self.assertIn("src/main.py", str(context.exception))
            self.assertIn("'nit'", str(context.exception))
            for call in mock_run_curl.call_args_list:
                self.assertNotIn("POST", call.args[0])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_on_another_file_refused(self, mock_run_curl):
        """A reply goes on the file of its parent comment."""

        async def run_test():
            mock_run_curl.side_effect = [json.dumps(PARENT_ON_PS3), '{"comments": {}}']

            with self.assertRaises(ValueError) as context:
                await post_review_comment(
                    change_id="123",
                    message="Answered in the commit message.",
                    file_path="/PATCHSET_LEVEL",
                    in_reply_to="parent-1",
                    gerrit_base_url=GERRIT_BASE_URL,
                )

            self.assertIn("'/PATCHSET_LEVEL'", str(context.exception))
            self.assertIn("'src/main.py'", str(context.exception))
            self.assertEqual(mock_run_curl.call_count, 1)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_on_another_line_refused(self, mock_run_curl):
        """A reply goes on the line of its parent comment."""

        async def run_test():
            mock_run_curl.side_effect = [json.dumps(PARENT_ON_PS3), '{"comments": {}}']

            with self.assertRaises(ValueError) as context:
                await post_review_comment(
                    change_id="123",
                    message="Done.",
                    line_number=10,
                    in_reply_to="parent-1",
                    gerrit_base_url=GERRIT_BASE_URL,
                )

            self.assertIn("10", str(context.exception))
            self.assertIn("42", str(context.exception))
            self.assertEqual(mock_run_curl.call_count, 1)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_given_parent_line_keeps_parent_range(self, mock_run_curl):
        """The parent's file and line, given for a reply, keep the parent's range."""

        async def run_test():
            mock_run_curl.side_effect = [json.dumps(PARENT_ON_PS3), '{"comments": {}}']

            await post_review_comment(
                change_id="123",
                message="Done.",
                file_path="src/main.py",
                line_number=42,
                in_reply_to="parent-1",
                gerrit_base_url=GERRIT_BASE_URL,
            )

            curl_args = mock_run_curl.call_args_list[1].args[0]
            comment = _sent_payload(curl_args)["comments"]["src/main.py"][0]
            self.assertEqual(comment["line"], 42)
            self.assertEqual(comment.get("range"), PARENT_RANGE)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_reply_parent_lookup_keeps_gerrit_error_text(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "Not found: 123"

            with self.assertRaises(ValueError) as context:
                await post_review_comment(
                    change_id="123",
                    message="Done.",
                    in_reply_to="parent-1",
                    gerrit_base_url=GERRIT_BASE_URL,
                )

            self.assertIn("Not found: 123", str(context.exception))
            self.assertEqual(mock_run_curl.call_count, 1)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_labels_with_reply_on_older_patch_set_refused(self, mock_run_curl):
        """Gerrit would keep the vote on the outdated patch set."""

        async def run_test():
            mock_run_curl.side_effect = [
                json.dumps(PARENT_ON_PS3),
                json.dumps(_change_with_current_patch_set(5)),
            ]

            with self.assertRaises(ValueError) as context:
                await post_review_comment(
                    change_id="123",
                    message="Done.",
                    in_reply_to="parent-1",
                    labels={"Code-Review": 1},
                    gerrit_base_url=GERRIT_BASE_URL,
                )

            self.assertIn("patch set 3", str(context.exception))
            self.assertIn("current patch set is 5", str(context.exception))
            self.assertEqual(mock_run_curl.call_count, 2)
            for call in mock_run_curl.call_args_list:
                self.assertNotIn("POST", call.args[0])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_current_patch_set_lookup_keeps_gerrit_error_text(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = [json.dumps(PARENT_ON_PS3), "Too many requests"]

            with self.assertRaises(ValueError) as context:
                await post_review_comment(
                    change_id="123",
                    message="Done.",
                    in_reply_to="parent-1",
                    labels={"Code-Review": 1},
                    gerrit_base_url=GERRIT_BASE_URL,
                )

            self.assertIn("Too many requests", str(context.exception))
            self.assertEqual(mock_run_curl.call_count, 2)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_labels_with_reply_on_current_patch_set_allowed(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = [
                json.dumps(PARENT_ON_PS3),
                json.dumps(_change_with_current_patch_set(3)),
                '{"labels": {"Code-Review": 1}}',
            ]

            result = await post_review_comment(
                change_id="123",
                message="Done.",
                in_reply_to="parent-1",
                labels={"Code-Review": 1},
                gerrit_base_url=GERRIT_BASE_URL,
            )

            self.assertEqual(result["revision"], "3")
            curl_args = mock_run_curl.call_args_list[2].args[0]
            self.assertEqual(
                curl_args[-1], f"{GERRIT_BASE_URL}/changes/123/revisions/3/review"
            )
            self.assertEqual(_sent_payload(curl_args)["labels"], {"Code-Review": 1})

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_missing_file_path_without_reply_returns_error(self, mock_run_curl):
        async def run_test():
            with self.assertRaises(ValueError) as context:
                await post_review_comment(
                    change_id="123",
                    message="hi",
                    line_number=10,
                    gerrit_base_url=GERRIT_BASE_URL,
                )

            self.assertIn("file_path is required", str(context.exception))
            mock_run_curl.assert_not_called()

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_gerrit_refusal_raises_with_its_text(self, mock_run_curl):
        """A plain-text answer from Gerrit is a refusal, raised with its text."""

        async def run_test():
            mock_run_curl.return_value = "Invalid comment in_reply_to."

            with self.assertRaises(ValueError) as context:
                await post_review_comment(
                    change_id="123",
                    message="hi",
                    file_path="a.py",
                    line_number=10,
                    gerrit_base_url=GERRIT_BASE_URL,
                )

            self.assertIn("Invalid comment in_reply_to.", str(context.exception))

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_empty_json_answer_is_success(self, mock_run_curl):
        """Gerrit 3.9 and older answer a comments-only review with {}."""

        async def run_test():
            mock_run_curl.return_value = "{}"

            result = await post_review_comment(
                change_id="123",
                message="hi",
                file_path="a.py",
                line_number=10,
                gerrit_base_url=GERRIT_BASE_URL,
            )

            self.assertEqual(result["line"], 10)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
