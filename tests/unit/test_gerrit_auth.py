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

"""
Tests for the gerrit_auth module.
"""

import unittest
from unittest.mock import patch, mock_open
from gerrit_mcp_server import gerrit_auth


class TestGerritAuth(unittest.TestCase):

    def test_get_auth_for_gob(self):
        """Tests that the correct command is returned for gob-curl."""
        self.assertEqual(gerrit_auth._get_auth_for_gob({}), ["gob-curl", "-s"])

    def test_get_auth_for_http_basic_success(self):
        """Tests that the correct command is returned for http_basic auth."""
        config = {"username": "testuser", "auth_token": "secret"}
        expected = ["curl", "--user", "testuser:secret", "-L"]
        self.assertEqual(gerrit_auth._get_auth_for_http_basic(config), expected)

    def test_get_auth_for_http_basic_missing_username(self):
        """Tests that an error is raised if username is missing for http_basic."""
        with self.assertRaisesRegex(ValueError, "both 'username' and 'auth_token'"):
            gerrit_auth._get_auth_for_http_basic({"auth_token": "secret"})

    def test_get_auth_for_http_basic_missing_token(self):
        """Tests that an error is raised if auth_token is missing for http_basic."""
        with self.assertRaisesRegex(ValueError, "both 'username' and 'auth_token'"):
            gerrit_auth._get_auth_for_http_basic({"username": "testuser"})

    @patch("os.path.exists", return_value=True)
    def test_get_auth_for_gitcookies_success(self, mock_exists):
        """Tests that the correct command is returned for gitcookies auth."""
        config = {"gitcookies_path": "~/.gitcookies"}
        url = "https://my-gerrit.com"
        m = mock_open(
            read_data="my-gerrit.com\tFALSE\t/\tTRUE\t2147483647\to\tgit-token"
        )
        with patch("builtins.open", m):
            command = gerrit_auth._get_auth_for_gitcookies(url, config)
        self.assertEqual(command, ["curl", "-b", "o=git-token", "-L"])

    @patch("os.path.exists", return_value=False)
    def test_get_auth_for_gitcookies_file_not_found(self, mock_exists):
        """Tests fallback to unauthenticated curl if gitcookies file is not found."""
        config = {"gitcookies_path": "~/.gitcookies"}
        url = "https://my-gerrit.com"
        command = gerrit_auth._get_auth_for_gitcookies(url, config)
        self.assertEqual(command, ["curl", "-s", "-L"])

    def test_get_auth_for_gitcookies_missing_path(self):
        """Tests that an error is raised if gitcookies_path is missing."""
        with self.assertRaisesRegex(ValueError, "requires 'gitcookies_path'"):
            gerrit_auth._get_auth_for_gitcookies("https://a.com", {})


if __name__ == "__main__":
    unittest.main()
