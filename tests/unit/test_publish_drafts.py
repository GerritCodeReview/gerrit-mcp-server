import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server import main

GERRIT_BASE_URL = "https://gerrit-review.googlesource.com"


def _sent_payload(mock_run_curl):
    curl_args = mock_run_curl.call_args.args[0]
    return json.loads(curl_args[curl_args.index("--data") + 1])


class TestPublishDrafts(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_publish_drafts_success(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "{}"

            result = await main.publish_drafts("456", gerrit_base_url=GERRIT_BASE_URL)

            mock_run_curl.assert_called_once()
            self.assertEqual(
                mock_run_curl.call_args.args[0][-1],
                f"{GERRIT_BASE_URL}/changes/456/revisions/current/review",
            )
            payload = _sent_payload(mock_run_curl)
            self.assertEqual(payload["drafts"], "PUBLISH_ALL_REVISIONS")
            self.assertNotIn("message", payload)
            self.assertNotIn("labels", payload)
            self.assertEqual(
                result,
                {"change_id": "456", "message": None, "labels": None, "note": None},
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_publish_drafts_with_message_and_labels(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = '{"labels": {"Code-Review": 1}}'

            result = await main.publish_drafts(
                "789",
                message="Addressed all comments",
                labels={"Code-Review": 1},
                gerrit_base_url=GERRIT_BASE_URL,
            )

            payload = _sent_payload(mock_run_curl)
            self.assertEqual(payload["drafts"], "PUBLISH_ALL_REVISIONS")
            self.assertEqual(payload["message"], "Addressed all comments")
            self.assertEqual(payload["labels"], {"Code-Review": 1})
            self.assertEqual(result["message"], "Addressed all comments")
            self.assertEqual(result["labels"], {"Code-Review": 1})
            self.assertIsNone(result["note"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_publish_drafts_reports_vote_gerrit_did_not_apply(self, mock_run_curl):
        async def run_test():
            # Gerrit ignores a vote outside the label's range but publishes.
            mock_run_curl.return_value = '{"labels": {}}'

            result = await main.publish_drafts(
                "789", labels={"Code-Review": 5}, gerrit_base_url=GERRIT_BASE_URL
            )

            self.assertEqual(result["labels"], {})
            self.assertEqual(
                result["note"],
                "Gerrit posted the drafts but did not apply these votes: Code-Review 5",
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_publish_drafts_gerrit_refusal_raises_with_its_text(self, mock_run_curl):
        async def run_test():
            for response in ["change is closed", '{"error": "Invalid label"}']:
                mock_run_curl.return_value = response
                with self.assertRaises(ValueError) as context:
                    await main.publish_drafts("789", gerrit_base_url=GERRIT_BASE_URL)
                self.assertIn("Failed to post drafts", str(context.exception))
                self.assertIn(response, str(context.exception))

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_publish_drafts_exception(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = Exception("Network error")

            with self.assertRaises(Exception):
                await main.publish_drafts("456", gerrit_base_url=GERRIT_BASE_URL)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
