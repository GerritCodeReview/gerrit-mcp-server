import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server import main


class TestPublishDrafts(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_publish_drafts_success(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = ""
            change_id = "456"
            gerrit_base_url = "https://gerrit-review.googlesource.com"

            result = await main.publish_drafts(change_id, gerrit_base_url=gerrit_base_url)

            mock_run_curl.assert_called_once()
            args, _ = mock_run_curl.call_args
            curl_args = args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["drafts"], "PUBLISH_ALL_REVISIONS")
            self.assertNotIn("message", payload)
            self.assertNotIn("labels", payload)
            self.assertIn("Successfully published", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_publish_drafts_with_message_and_labels(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = ""
            change_id = "789"
            gerrit_base_url = "https://gerrit-review.googlesource.com"

            result = await main.publish_drafts(
                change_id,
                message="Addressed all comments",
                labels={"Code-Review": 1},
                gerrit_base_url=gerrit_base_url,
            )

            args, _ = mock_run_curl.call_args
            curl_args = args[0]
            payload = json.loads(curl_args[curl_args.index("--data") + 1])
            self.assertEqual(payload["drafts"], "PUBLISH_ALL_REVISIONS")
            self.assertEqual(payload["message"], "Addressed all comments")
            self.assertEqual(payload["labels"], {"Code-Review": 1})
            self.assertIn("Successfully published", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_publish_drafts_exception(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = Exception("Network error")

            with self.assertRaises(Exception):
                await main.publish_drafts(
                    "456", gerrit_base_url="https://gerrit-review.googlesource.com"
                )

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
