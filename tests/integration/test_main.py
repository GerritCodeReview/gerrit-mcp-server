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

import asyncio
import json
import os
import unittest
from unittest.mock import patch, AsyncMock

from gerrit_mcp_server import main


class TestGerritMCP(unittest.IsolatedAsyncioTestCase):

    @patch.dict(
        os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}
    )
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_query_changes(self, mock_run_curl):
        mock_run_curl.return_value = json.dumps(
            [
                {
                    "_number": 1,
                    "subject": "Test Change 1",
                    "work_in_progress": False,
                    "updated": "2025-07-02T12:00:00Z",
                },
                {
                    "_number": 2,
                    "subject": "Test Change 2",
                    "work_in_progress": True,
                    "updated": "2025-07-01T10:00:00Z",
                },
            ]
        )

        result = await main.query_changes(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            query="status:open",
        )
        self.assertIn("Found 2 changes", result[0]["text"])
        self.assertIn("1: Test Change 1", result[0]["text"])
        self.assertIn("2: [WIP] Test Change 2", result[0]["text"])

    @patch.dict(
        os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}
    )
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_query_changes_no_results(self, mock_run_curl):
        mock_run_curl.return_value = json.dumps([])
        result = await main.query_changes(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            query="status:open",
        )
        self.assertIn("No changes found", result[0]["text"])

    @patch.dict(
        os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}
    )
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_get_change_details(self, mock_run_curl):
        mock_run_curl.return_value = json.dumps(
            {
                "_number": 123,
                "subject": "Test Subject",
                "owner": {"email": "owner@example.com"},
                "status": "NEW",
                "reviewers": {
                    "REVIEWER": [{"email": "reviewer@example.com", "_account_id": 1}]
                },
                "labels": {"Code-Review": {"all": [{"value": 1, "_account_id": 1}]}},
                "messages": [
                    {"_revision_number": 1, "message": "First message"},
                    {"_revision_number": 2, "message": "Second message"},
                ],
            }
        )

        result = await main.get_change_details(
            gerrit_base_url="https://fuchsia-review.googlesource.com", change_id="123"
        )
        self.assertIn("Summary for CL 123", result[0]["text"])
        self.assertIn("Subject: Test Subject", result[0]["text"])
        self.assertIn("owner@example.com", result[0]["text"])
        self.assertIn("reviewer@example.com (Code-Review: +1)", result[0]["text"])
        self.assertIn(
            "- (Patch Set 2) [No date] (Gerrit): Second message", result[0]["text"]
        )

    @patch.dict(
        os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}
    )
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_get_change_details_missing_fields(self, mock_run_curl):
        mock_run_curl.return_value = json.dumps(
            {
                "_number": 123,
                "subject": "Test Subject",
                "owner": {"email": "owner@example.com"},
                "status": "NEW",
            }
        )
        result = await main.get_change_details(
            gerrit_base_url="https://fuchsia-review.googlesource.com", change_id="123"
        )
        self.assertIn("Summary for CL 123", result[0]["text"])
        self.assertNotIn("Reviewers:", result[0]["text"])
        self.assertNotIn("Recent Messages:", result[0]["text"])

    @patch.dict(
        os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}
    )
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_list_change_files(self, mock_run_curl):
        mock_run_curl.side_effect = [
            json.dumps(
                {
                    "/COMMIT_MSG": {},
                    "file1.txt": {
                        "status": "ADDED",
                        "lines_inserted": 10,
                        "lines_deleted": 0,
                    },
                    "file2.txt": {
                        "status": "MODIFIED",
                        "lines_inserted": 5,
                        "lines_deleted": 2,
                    },
                }
            ),
            json.dumps({"current_revision_number": 3}),
        ]

        result = await main.list_change_files(
            gerrit_base_url="https://fuchsia-review.googlesource.com", change_id="123"
        )
        self.assertIn("Files in CL 123 (Patch Set 3)", result[0]["text"])
        self.assertIn("[A] file1.txt (+10, -0)", result[0]["text"])
        self.assertIn("[M] file2.txt (+5, -2)", result[0]["text"])
        self.assertNotIn("/COMMIT_MSG", result[0]["text"])

    @patch.dict(
        os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}
    )
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_list_change_files_no_files(self, mock_run_curl):
        mock_run_curl.side_effect = [
            json.dumps({"/COMMIT_MSG": {}}),
            json.dumps({"current_revision_number": 1}),
        ]
        result = await main.list_change_files(
            gerrit_base_url="https://fuchsia-review.googlesource.com", change_id="123"
        )
        self.assertIn("Files in CL 123 (Patch Set 1)", result[0]["text"])
        self.assertNotIn("[", result[0]["text"])

    @patch.dict(
        os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}
    )
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_get_file_diff(self, mock_run_curl):
        diff_text = "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1,1 +1,1 @@\n-hello\n+world"
        import base64

        encoded_diff = base64.b64encode(diff_text.encode("utf-8")).decode("utf-8")
        mock_run_curl.return_value = encoded_diff

        result = await main.get_file_diff(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            change_id="123",
            file_path="file.txt",
        )
        self.assertEqual(diff_text, result[0]["text"])

    @patch.dict(
        os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}
    )
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_list_change_comments(self, mock_run_curl):
        mock_run_curl.return_value = json.dumps(
            {
                "file1.txt": [
                    {
                        "line": 10,
                        "author": {"name": "user1@example.com"},
                        "message": "Comment 1",
                        "unresolved": True,
                        "updated": "2025-07-15T11:00:00Z",
                    },
                    {
                        "line": 12,
                        "author": {"name": "user2@example.com"},
                        "message": "Comment 2",
                        "unresolved": False,
                        "updated": "2025-07-15T11:05:00Z",
                    },
                ],
                "file2.txt": [
                    {
                        "line": 5,
                        "author": {"name": "user1@example.com"},
                        "message": "Comment 3",
                        "unresolved": True,
                        "updated": "2025-07-15T11:10:00Z",
                    },
                ],
            }
        )

        result = await main.list_change_comments(
            gerrit_base_url="https://fuchsia-review.googlesource.com", change_id="123"
        )
        self.assertIn("Comments for CL 123", result[0]["text"])
        self.assertIn("File: file1.txt", result[0]["text"])
        self.assertIn(
            "L10: [user1@example.com] (2025-07-15T11:00:00Z) - UNRESOLVED",
            result[0]["text"],
        )
        self.assertIn("Comment 1", result[0]["text"])
        self.assertIn(
            "L12: [user2@example.com] (2025-07-15T11:05:00Z) - RESOLVED",
            result[0]["text"],
        )
        self.assertIn("Comment 2", result[0]["text"])
        self.assertIn("File: file2.txt", result[0]["text"])
        self.assertIn(
            "L5: [user1@example.com] (2025-07-15T11:10:00Z) - UNRESOLVED",
            result[0]["text"],
        )
        self.assertIn("Comment 3", result[0]["text"])

    @patch.dict(
        os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}
    )
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_list_change_comments_no_unresolved(self, mock_run_curl):
        mock_run_curl.return_value = json.dumps(
            {
                "file1.txt": [
                    {
                        "line": 12,
                        "author": {"name": "user2@example.com"},
                        "message": "Comment 2",
                        "unresolved": False,
                        "updated": "2025-07-15T11:05:00Z",
                    },
                ]
            }
        )
        result = await main.list_change_comments(
            gerrit_base_url="https://fuchsia-review.googlesource.com", change_id="123"
        )
        self.assertIn("Comments for CL 123", result[0]["text"])
        self.assertIn(
            "L12: [user2@example.com] (2025-07-15T11:05:00Z) - RESOLVED",
            result[0]["text"],
        )

    @patch.dict(
        os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}
    )
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_list_change_comments_json_decode_error(self, mock_run_curl):
        mock_run_curl.return_value = "this is not json"
        result = await main.list_change_comments(
            gerrit_base_url="https://fuchsia-review.googlesource.com", change_id="123"
        )
        self.assertIn("Failed to parse JSON", result[0]["text"])

    @patch.dict(
        os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}
    )
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_add_reviewer(self, mock_run_curl):
        mock_run_curl.return_value = json.dumps({})  # Empty object for success

        result = await main.add_reviewer(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            change_id="123",
            reviewer="reviewer@example.com",
        )
        self.assertIn(
            "Successfully added reviewer@example.com as a REVIEWER to CL 123",
            result[0]["text"],
        )

    @patch.dict(
        os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}
    )
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_add_reviewer_failure(self, mock_run_curl):
        mock_run_curl.return_value = '{"error": "Reviewer not found"}'
        result = await main.add_reviewer(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            change_id="123",
            reviewer="nonexistent@example.com",
        )
        self.assertIn("Failed to add", result[0]["text"])
        self.assertIn("Reviewer not found", result[0]["text"])

    @patch.dict(
        os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}
    )
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_get_most_recent_cl(self, mock_run_curl):
        mock_run_curl.return_value = json.dumps(
            [
                {
                    "_number": 456,
                    "subject": "Most Recent",
                    "work_in_progress": False,
                    "updated": "2025-07-02T13:00:00Z",
                },
            ]
        )

        result = await main.get_most_recent_cl(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            user="owner@example.com",
        )
        self.assertIn("Most recent CL for owner@example.com", result[0]["text"])
        self.assertIn("456: Most Recent", result[0]["text"])

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_add_reviewer_invalid_state(self, mock_run_curl):
        # This test doesn't need to mock run_curl since the validation is local
        result = await main.add_reviewer(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            change_id="123",
            reviewer="reviewer@example.com",
            state="INVALID_STATE",
        )
        self.assertIn("Failed to add", result[0]["text"])
        self.assertIn("Invalid state", result[0]["text"])
        mock_run_curl.assert_not_called()

    @patch.dict(
        os.environ, {"GERRIT_BASE_URL": "https://fuchsia-review.googlesource.com"}
    )
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_get_most_recent_cl_no_results(self, mock_run_curl):
        mock_run_curl.return_value = json.dumps([])
        result = await main.get_most_recent_cl(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            user="owner@example.com",
        )
        self.assertIn("No changes found for user", result[0]["text"])

    @patch.dict(os.environ, {"GERRIT_BASE_URL": "https://another-gerrit.com"})
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_gerrit_base_url_override(self, mock_run_curl):
        mock_run_curl.return_value = json.dumps([])

        # The gerrit_base_url parameter is not provided, so it should use the one from the environment variable
        await main.query_changes(query="status:open")
        mock_run_curl.assert_called_once()
        self.assertIn(
            "https://another-gerrit.com/changes", mock_run_curl.call_args[0][0][0]
        )

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    @patch("asyncio.create_subprocess_exec")
    async def test_run_curl_auth_error(
        self,
        mock_create_subprocess_exec,
        mock_load_config,
    ):
        mock_load_config.return_value = {
            "gerrit_hosts": [
                {
                    "name": "Corporate",
                    "external_url": "https://gerrit.private.corp.corporation.com/",
                    "authentication": {"type": "gob_curl"},
                }
            ]
        }
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"",
            b"bad request: no valid session id provided",
        )
        mock_process.returncode = 1
        mock_create_subprocess_exec.return_value = mock_process

        with self.assertRaisesRegex(Exception, "curl command failed with exit code 1"):
            await main.run_curl(
                ["https://gerrit.private.corp.corporation.com/changes/123"],
                "https://gerrit.private.corp.corporation.com",
            )

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    @patch("asyncio.create_subprocess_exec")
    async def test_run_curl_generic_error(
        self,
        mock_create_subprocess_exec,
        mock_load_config,
    ):
        mock_load_config.return_value = {
            "gerrit_hosts": [
                {
                    "name": "Fake",
                    "external_url": "https://fakegerrit.com/",
                    "authentication": {
                        "type": "git_cookies",
                        "gitcookies_path": "~/.gitcookies",
                    },
                }
            ]
        }
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"",
            b"curl: (6) Could not resolve host: fakegerrit.com",
        )
        mock_process.returncode = 6
        mock_create_subprocess_exec.return_value = mock_process

        with self.assertRaisesRegex(Exception, "curl command failed with exit code 6"):
            await main.run_curl(["https://fakegerrit.com"], "https://fakegerrit.com")

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_tool_functions_with_invalid_change_id(self, mock_run_curl):
        mock_run_curl.side_effect = Exception(
            "curl command failed with exit code 1.\nSTDERR:\nNot Found"
        )

        # Test get_change_details
        with self.assertRaisesRegex(Exception, "Not Found"):
            await main.get_change_details(
                gerrit_base_url="https://fuchsia-review.googlesource.com",
                change_id="invalid",
            )

        # Test list_change_files
        with self.assertRaisesRegex(Exception, "Not Found"):
            await main.list_change_files(
                gerrit_base_url="https://fuchsia-review.googlesource.com",
                change_id="invalid",
            )

        # Test get_file_diff
        with self.assertRaisesRegex(Exception, "Not Found"):
            await main.get_file_diff(
                gerrit_base_url="https://fuchsia-review.googlesource.com",
                change_id="invalid",
                file_path="file.txt",
            )

        # Test list_change_comments
        with self.assertRaisesRegex(Exception, "Not Found"):
            await main.list_change_comments(
                gerrit_base_url="https://fuchsia-review.googlesource.com",
                change_id="invalid",
            )

        # Test add_reviewer
        with self.assertRaisesRegex(Exception, "Not Found"):
            await main.add_reviewer(
                gerrit_base_url="https://fuchsia-review.googlesource.com",
                change_id="invalid",
                reviewer="reviewer@example.com",
            )

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_tool_functions_with_malformed_json(self, mock_run_curl):
        mock_run_curl.return_value = "this is not json"

        with self.assertRaises(json.JSONDecodeError):
            await main.query_changes(
                gerrit_base_url="https://fuchsia-review.googlesource.com",
                query="status:open",
            )

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    async def test_tool_functions_with_unexpected_json(self, mock_run_curl):
        mock_run_curl.return_value = json.dumps(
            {"unexpected_field": "unexpected_value"}
        )

        with self.assertRaises(KeyError):
            await main.get_change_details(
                gerrit_base_url="https://fuchsia-review.googlesource.com",
                change_id="123",
            )

    async def test_concurrent_requests(self):
        with patch(
            "gerrit_mcp_server.main.run_curl", new_callable=AsyncMock
        ) as mock_run_curl:
            mock_run_curl.return_value = json.dumps([])

            tasks = [
                main.query_changes(
                    gerrit_base_url="https://fuchsia-review.googlesource.com",
                    query="status:open",
                ),
                main.query_changes(
                    gerrit_base_url="https://fuchsia-review.googlesource.com",
                    query="status:merged",
                ),
            ]
            results = await asyncio.gather(*tasks)

            self.assertEqual(len(results), 2)
            self.assertEqual(mock_run_curl.call_count, 2)

    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    async def test_command_injection(self, mock_exec):
        # This test ensures that the server is not vulnerable to command injection attacks
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"[]", b"")
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        await main.query_changes(
            gerrit_base_url="https://fuchsia-review.googlesource.com",
            query="status:open; rm -rf /",
        )

        # Check that the malicious command was not executed
        # The command is the first argument to create_subprocess_exec
        command_list = mock_exec.call_args[0][0]
        command_str = " ".join(command_list)
        self.assertNotIn(";", command_str)
        self.assertNotIn("rm", command_str)


if __name__ == "__main__":
    unittest.main()
