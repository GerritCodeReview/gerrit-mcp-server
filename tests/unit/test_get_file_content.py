import asyncio
import base64
import unittest
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server import main

FOUR_LINES = b"one\ntwo\nthree\nfour\n"


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

            self.assertEqual(
                result,
                {
                    "change_id": "123",
                    "file_path": "src/main.py",
                    "revision": "current",
                    "first_line": 1,
                    "last_line": 2,
                    "line_count": 2,
                    "content": "line 1\nline 2\n",
                },
            )
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

            result = await main.get_file_content("123", "src/main.py", revision_id="2")

            self.assertEqual(result["revision"], "2")
            url = mock_run_curl.call_args[0][0][0]
            self.assertIn("/changes/123/revisions/2/files/", url)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_not_found(self, mock_run_curl):
        """A plain-text error from Gerrit is raised, not decoded as base64."""

        async def run_test():
            mock_run_curl.return_value = "Not Found"

            with self.assertRaises(ValueError) as context:
                await main.get_file_content("123", "no/such.py")

            self.assertIn("Failed to fetch no/such.py", str(context.exception))
            self.assertIn("Not Found", str(context.exception))

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_binary(self, mock_run_curl):
        """A file that is not UTF-8 text raises instead of being returned."""

        async def run_test():
            mock_run_curl.return_value = _encoded(b"\xff\xfe\x00")

            with self.assertRaises(ValueError) as context:
                await main.get_file_content("123", "logo.png")

            self.assertEqual(
                str(context.exception), "logo.png is not UTF-8 text (3 bytes)."
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_empty_file(self, mock_run_curl):
        """An empty file has no lines, so it has no first or last line."""

        async def run_test():
            mock_run_curl.return_value = _encoded(b"")

            result = await main.get_file_content("123", "empty.txt")

            self.assertEqual(result["content"], "")
            self.assertEqual(result["line_count"], 0)
            self.assertIsNone(result["first_line"])
            self.assertIsNone(result["last_line"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_line_range(self, mock_run_curl):
        """start_line and end_line return only those lines, both included."""

        async def run_test():
            mock_run_curl.return_value = _encoded(FOUR_LINES)

            result = await main.get_file_content(
                "123", "src/main.py", start_line=2, end_line=3
            )

            self.assertEqual(result["content"], "two\nthree\n")
            self.assertEqual(result["first_line"], 2)
            self.assertEqual(result["last_line"], 3)
            self.assertEqual(result["line_count"], 4)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_range_with_one_end(self, mock_run_curl):
        """An omitted end of the range is the first or the last line."""

        async def run_test():
            mock_run_curl.return_value = _encoded(FOUR_LINES)

            from_line_3 = await main.get_file_content(
                "123", "src/main.py", start_line=3
            )
            up_to_line_2 = await main.get_file_content("123", "src/main.py", end_line=2)

            self.assertEqual(from_line_3["content"], "three\nfour\n")
            self.assertEqual(from_line_3["first_line"], 3)
            self.assertEqual(up_to_line_2["content"], "one\ntwo\n")
            self.assertEqual(up_to_line_2["last_line"], 2)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_end_past_last_line(self, mock_run_curl):
        """An end_line past the file stops at its last line."""

        async def run_test():
            mock_run_curl.return_value = _encoded(FOUR_LINES)

            result = await main.get_file_content(
                "123", "src/main.py", start_line=3, end_line=10
            )

            self.assertEqual(result["content"], "three\nfour\n")
            self.assertEqual(result["last_line"], 4)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_range_outside_file(self, mock_run_curl):
        """A range with no line in the file raises with the line count."""

        async def run_test():
            mock_run_curl.return_value = _encoded(FOUR_LINES)

            for start_line, end_line in ((10, 12), (0, 2)):
                with self.assertRaises(ValueError) as context:
                    await main.get_file_content(
                        "123", "src/main.py", start_line=start_line, end_line=end_line
                    )
                self.assertIn("line count: 4", str(context.exception))

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_file_content_range_counts_newlines_only(self, mock_run_curl):
        """Lines are numbered as in Gerrit: a form feed does not end a line."""

        async def run_test():
            mock_run_curl.return_value = _encoded(b"one\x0ctwo\nthree\n")

            result = await main.get_file_content("123", "src/main.py", start_line=2)

            self.assertEqual(result["content"], "three\n")
            self.assertEqual(result["first_line"], 2)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
