# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from unittest.mock import patch, AsyncMock
import asyncio
import os
import json

from gerrit_mcp_server import main


class TestMain(unittest.TestCase):
    @patch.dict(os.environ, {"GERRIT_BASE_URL": "https://another-gerrit.com"})
    def test_get_gerrit_base_url_with_env_var(self):
        self.assertEqual(main._get_gerrit_base_url(), "https://another-gerrit.com")

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    def test_get_gerrit_base_url_with_parameter(self, mock_load_config):
        self.assertEqual(
            main._get_gerrit_base_url("https://parameter-gerrit.com"),
            "https://parameter-gerrit.com",
        )
        mock_load_config.assert_not_called()

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    def test_normalize_gerrit_url(self, mock_load_config):
        mock_load_config.return_value = {
            "gerrit_hosts": [
                {
                    "name": "Fuchsia",
                    "internal_url": "https://fuchsia-review.git.private.corporation.com/",
                    "external_url": "https://fuchsia-review.googlesource.com/",
                }
            ]
        }
        self.assertEqual(
            main._normalize_gerrit_url("fuchsia-review.git.private.corporation.com"),
            "https://fuchsia-review.googlesource.com",
        )
        self.assertEqual(
            main._normalize_gerrit_url("https://fuchsia-review.git.private.corporation.com"),
            "https://fuchsia-review.googlesource.com",
        )
        self.assertEqual(
            main._normalize_gerrit_url("fuchsia-review.googlesource.com"),
            "https://fuchsia-review.googlesource.com",
        )
        self.assertEqual(
            main._normalize_gerrit_url("another-gerrit.com"),
            "https://another-gerrit.com",
        )
        self.assertEqual(
            main._normalize_gerrit_url("http://another-gerrit.com"),
            "https://another-gerrit.com",
        )
        self.assertEqual(
            main._normalize_gerrit_url("https://another-gerrit.com"),
            "https://another-gerrit.com",
        )

    @patch("gerrit_mcp_server.main.Path.exists", return_value=False)
    def test_load_gerrit_config_not_found(self, mock_exists):
        with self.assertRaises(FileNotFoundError):
            main.load_gerrit_config()

    @patch(
        "builtins.open",
        new_callable=unittest.mock.mock_open,
        read_data='{"key": "value"}',
    )
    @patch("pathlib.Path.exists", return_value=True)
    @patch.dict(os.environ, {"GERRIT_CONFIG_PATH": "/fake/path/gerrit_config.json"})
    def test_load_gerrit_config_with_env_var(self, mock_exists, mock_open):
        from pathlib import Path

        config = main.load_gerrit_config()
        self.assertEqual(config, {"key": "value"})
        mock_open.assert_called_once_with(Path("/fake/path/gerrit_config.json"), "r")

    @patch.dict(os.environ, {}, clear=True)
    def test_get_gerrit_base_url_with_no_env_var(self):
        self.assertEqual(
            main._get_gerrit_base_url(), "https://fuchsia-review.googlesource.com/"
        )

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    def test_run_curl_timeout(self, mock_exec, mock_load_config):
        async def run_test():
            mock_load_config.return_value = {
                "gerrit_hosts": [
                    {
                        "name": "Example",
                        "external_url": "https://example.com",
                        "authentication": {"type": "gob_curl"},
                    }
                ]
            }
            # Mock the subprocess to simulate a hanging process
            mock_process = AsyncMock()
            mock_process.communicate.side_effect = asyncio.TimeoutError
            mock_exec.return_value = mock_process

            with self.assertRaises(asyncio.TimeoutError):
                await main.run_curl(["https://example.com"], "https://example.com")

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    def test_run_curl_large_output(self, mock_exec, mock_load_config):
        async def run_test():
            mock_load_config.return_value = {
                "gerrit_hosts": [
                    {
                        "name": "Example",
                        "external_url": "https://example.com",
                        "authentication": {"type": "gob_curl"},
                    }
                ]
            }
            # Mock the subprocess to simulate a large output
            large_output = "a" * 10000
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (large_output.encode(), b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await main.run_curl(["https://example.com"], "https://example.com")
            self.assertEqual(result, large_output)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    def test_run_curl_non_zero_exit(self, mock_exec, mock_load_config):
        async def run_test():
            mock_load_config.return_value = {
                "gerrit_hosts": [
                    {
                        "name": "Example",
                        "external_url": "https://example.com",
                        "authentication": {"type": "gob_curl"},
                    }
                ]
            }
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"error")
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            with self.assertRaises(Exception):
                await main.run_curl(["https://example.com"], "https://example.com")

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    def test_run_curl_removes_gerrit_prefix(self, mock_exec, mock_load_config):
        async def run_test():
            mock_load_config.return_value = {
                "gerrit_hosts": [
                    {
                        "name": "Example",
                        "external_url": "https://example.com",
                        "authentication": {"type": "gob_curl"},
                    }
                ]
            }
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b')]}\'\n{"key": "value"}', b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await main.run_curl(["https://example.com"], "https://example.com")
            self.assertEqual(result, '{"key": "value"}')

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_bugs_from_cl_with_one_bug(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = '{"message": "Fixes: b/12345"}'
            result = await main.get_bugs_from_cl("123")
            self.assertIn("Found bug(s): 12345", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_bugs_from_cl_with_multiple_bugs(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = '{"message": "Fixes: b/12345, b/67890"}'
            result = await main.get_bugs_from_cl("123")
            self.assertIn("Found bug(s): 12345, 67890", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_bugs_from_cl_no_bugs(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = '{"message": "No bugs here"}'
            result = await main.get_bugs_from_cl("123")
            self.assertIn("No bug IDs found", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_bugs_from_cl_no_commit_message(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "{}"
            result = await main.get_bugs_from_cl("123")
            self.assertIn("No commit message found", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_bugs_from_cl_empty_response(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = ""
            result = await main.get_bugs_from_cl("123")
            self.assertIn("No commit message found", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_review_comment_success(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = '{"comments": {}}'
            result = await main.post_review_comment(
                "123", "file.py", 10, "test comment"
            )
            self.assertIn("Successfully posted comment", result[0]["text"])
            # Verify that the 'unresolved' flag is sent as True by default
            args, _ = mock_run_curl.call_args
            curl_args = args[0]
            data_index = curl_args.index("--data")
            request_body = json.loads(curl_args[data_index + 1])
            self.assertTrue(request_body["comments"]["file.py"][0]["unresolved"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_review_comment_unresolved_false(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = '{"comments": {}}'
            result = await main.post_review_comment(
                "123", "file.py", 10, "test comment", unresolved=False
            )
            self.assertIn("Successfully posted comment", result[0]["text"])
            args, _ = mock_run_curl.call_args
            curl_args = args[0]
            data_index = curl_args.index("--data")
            request_body = json.loads(curl_args[data_index + 1])
            self.assertFalse(request_body["comments"]["file.py"][0]["unresolved"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_review_comment_unresolved_true(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = '{"comments": {}}'
            result = await main.post_review_comment(
                "123", "file.py", 10, "test comment", unresolved=True
            )
            self.assertIn("Successfully posted comment", result[0]["text"])
            args, _ = mock_run_curl.call_args
            curl_args = args[0]
            data_index = curl_args.index("--data")
            request_body = json.loads(curl_args[data_index + 1])
            self.assertTrue(request_body["comments"]["file.py"][0]["unresolved"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_post_review_comment_failure(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = '{"error": "failed"}'
            result = await main.post_review_comment(
                "123", "file.py", 10, "test comment"
            )
            self.assertIn("Failed to post comment", result[0]["text"])

        asyncio.run(run_test())

    # --- Edge Case Tests ---

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_change_details_handles_missing_reviewers(self, mock_run_curl):
        async def run_test():
            """Tests that get_change_details handles a response with no 'reviewers' field."""
            mock_run_curl.return_value = json.dumps(
                {
                    "_number": 123,
                    "subject": "Test",
                    "owner": {"email": "a@b.com"},
                    "status": "NEW",
                }
            )
            result = await main.get_change_details("123")
            self.assertNotIn("Reviewers:", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_change_details_handles_empty_reviewers_list(self, mock_run_curl):
        async def run_test():
            """Tests that get_change_details handles a response with an empty 'REVIEWER' list."""
            mock_run_curl.return_value = json.dumps(
                {
                    "_number": 123,
                    "subject": "Test",
                    "owner": {"email": "a@b.com"},
                    "status": "NEW",
                    "reviewers": {"REVIEWER": []},
                }
            )
            result = await main.get_change_details("123")
            self.assertIn(
                "Reviewers:", result[0]["text"]
            )  # The header should still be present

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_get_change_details_handles_reviewer_missing_email(self, mock_run_curl):
        async def run_test():
            """Tests that get_change_details handles a reviewer object without an 'email'."""
            mock_run_curl.return_value = json.dumps(
                {
                    "_number": 123,
                    "subject": "Test",
                    "owner": {"email": "a@b.com"},
                    "status": "NEW",
                    "reviewers": {"REVIEWER": [{"_account_id": 1, "name": "No Email"}]},
                }
            )
            result = await main.get_change_details("123")
            # This should not crash, and we expect it to gracefully handle the missing field.
            # A more advanced test could check for a placeholder, but for now we just check for no crash.
            self.assertIn("Reviewers:", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_list_change_files_handles_empty_response(self, mock_run_curl):
        async def run_test():
            """Tests that list_change_files handles an empty JSON response."""
            mock_run_curl.side_effect = [
                json.dumps({}),
                json.dumps({"current_revision_number": 1}),
            ]
            result = await main.list_change_files("123")
            self.assertIn("Files in CL 123 (Patch Set 1)", result[0]["text"])
            # Check that it doesn't crash and produces a header but no file lines
            self.assertNotIn("[", result[0]["text"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
