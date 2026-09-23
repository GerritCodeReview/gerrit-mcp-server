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

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_line_range(self, mock_run_curl):
        """start_line and end_line return only those lines, both included."""

        async def run_test():
            mock_run_curl.return_value = _encoded(b"one\ntwo\nthree\nfour\n")

            result = await main.get_file_content(
                "123", "src/main.py", start_line=2, end_line=3
            )

            self.assertEqual(result[0]["text"], "two\nthree\n")

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_range_with_one_end(self, mock_run_curl):
        """An omitted end of the range is the first or the last line."""

        async def run_test():
            mock_run_curl.return_value = _encoded(b"one\ntwo\nthree\nfour\n")

            from_line_3 = await main.get_file_content(
                "123", "src/main.py", start_line=3
            )
            up_to_line_2 = await main.get_file_content("123", "src/main.py", end_line=2)

            self.assertEqual(from_line_3[0]["text"], "three\nfour\n")
            self.assertEqual(up_to_line_2[0]["text"], "one\ntwo\n")

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_range_outside_file(self, mock_run_curl):
        """A range with no line in the file reports the line count instead."""

        async def run_test():
            mock_run_curl.return_value = _encoded(b"one\ntwo\nthree\nfour\n")

            past_end = await main.get_file_content(
                "123", "src/main.py", start_line=10, end_line=12
            )
            from_line_0 = await main.get_file_content(
                "123", "src/main.py", start_line=0, end_line=2
            )

            self.assertIn("line count: 4", past_end[0]["text"])
            self.assertIn("line count: 4", from_line_0[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_range_counts_newlines_only(self, mock_run_curl):
        """Lines are numbered as in Gerrit: a form feed does not end a line."""

        async def run_test():
            mock_run_curl.return_value = _encoded(b"one\x0ctwo\nthree\n")

            result = await main.get_file_content("123", "src/main.py", start_line=2)

            self.assertEqual(result[0]["text"], "three\n")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
