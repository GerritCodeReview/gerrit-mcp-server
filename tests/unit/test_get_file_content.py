import asyncio
import base64
import unittest
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server import main


def _encoded(content: bytes) -> str:
    """Returns the content base64-encoded, the way Gerrit sends a file."""
    return base64.b64encode(content).decode("ascii")


class TestGetFileContent(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_success(self, mock_run_curl):
        """The file comes back decoded, read from the current revision."""

        async def run_test():
            mock_run_curl.return_value = _encoded(b"line 1\nline 2\n")

            result = await main.get_file_content("123", "src/main.py")

            self.assertEqual(result[0]["text"], "line 1\nline 2\n")
            url = mock_run_curl.call_args[0][0][0]
            self.assertTrue(
                url.endswith(
                    "/changes/123/revisions/current/files/src%2Fmain.py/content"
                )
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_older_revision(self, mock_run_curl):
        """revision_id selects the patch set the file is read from."""

        async def run_test():
            mock_run_curl.return_value = _encoded(b"old\n")

            await main.get_file_content("123", "src/main.py", revision_id="2")

            url = mock_run_curl.call_args[0][0][0]
            self.assertIn("/changes/123/revisions/2/files/", url)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_not_found(self, mock_run_curl):
        """A plain-text error from Gerrit is reported, not decoded as base64."""

        async def run_test():
            mock_run_curl.return_value = "Not Found"

            result = await main.get_file_content("123", "no/such.py")

            self.assertEqual(
                result[0]["text"], "Failed to fetch no/such.py.\nNot Found"
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_binary(self, mock_run_curl):
        """A file that is not UTF-8 text is described instead of returned."""

        async def run_test():
            mock_run_curl.return_value = _encoded(b"\xff\xfe\x00")

            result = await main.get_file_content("123", "logo.png")

            self.assertEqual(result[0]["text"], "logo.png is not UTF-8 text (3 bytes).")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
