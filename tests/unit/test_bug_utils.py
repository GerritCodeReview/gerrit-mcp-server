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
from gerrit_mcp_server.bug_utils import extract_bugs_from_commit_message


class TestBugUtils(unittest.TestCase):

    def test_extract_bugs_from_commit_message_simple(self):
        commit_message = "This is a test commit.\n\nBug: 12345"
        self.assertEqual(extract_bugs_from_commit_message(commit_message), {"12345"})

    def test_extract_bugs_from_commit_message_b_prefix(self):
        commit_message = "This is a test commit.\n\nFixes: b/12345"
        self.assertEqual(extract_bugs_from_commit_message(commit_message), {"12345"})

    def test_extract_bugs_from_commit_message_multiple_footers(self):
        commit_message = "This is a test commit.\n\nBug: 12345\nCloses: b/67890"
        self.assertEqual(
            extract_bugs_from_commit_message(commit_message), {"12345", "67890"}
        )

    def test_extract_bugs_from_commit_message_multiple_ids_in_footer(self):
        commit_message = "This is a test commit.\n\nFixes: 12345, b/67890"
        self.assertEqual(
            extract_bugs_from_commit_message(commit_message), {"12345", "67890"}
        )

    def test_extract_bugs_from_commit_message_inline(self):
        commit_message = "This commit fixes b/12345 and also addresses b/67890."
        self.assertEqual(
            extract_bugs_from_commit_message(commit_message), {"12345", "67890"}
        )

    def test_extract_bugs_from_commit_message_mixed(self):
        commit_message = "This commit fixes b/12345.\n\nBug: 67890"
        self.assertEqual(
            extract_bugs_from_commit_message(commit_message), {"12345", "67890"}
        )

    def test_extract_bugs_from_commit_message_no_bugs(self):
        commit_message = "This is a test commit with no bugs."
        self.assertEqual(extract_bugs_from_commit_message(commit_message), set())

    def test_extract_bugs_from_commit_message_greedy(self):
        commit_message = "Fix for bug 12345 in version 2.0"
        self.assertEqual(extract_bugs_from_commit_message(commit_message), set())


if __name__ == "__main__":
    unittest.main()
