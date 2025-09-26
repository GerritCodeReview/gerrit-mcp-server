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
Tests for the gerrit_urls module, focusing on its role as a dispatcher.
"""

import unittest
from unittest.mock import patch
from gerrit_mcp_server import gerrit_urls


class TestGerritUrlsDispatcher(unittest.TestCase):

    @patch("gerrit_mcp_server.gerrit_auth._get_auth_for_gob")
    def test_dispatches_to_gob_curl(self, mock_get_auth):
        """Tests that the dispatcher correctly calls the gob-curl auth function."""
        mock_get_auth.return_value = ["gob-curl", "-s"]
        config = {
            "gerrit_hosts": [
                {
                    "name": "Fuchsia",
                    "external_url": "https://fuchsia-review.googlesource.com/",
                    "authentication": {"type": "gob_curl"},
                }
            ]
        }
        command = gerrit_urls.get_curl_command_for_gerrit_url(
            "https://fuchsia-review.googlesource.com", config
        )
        mock_get_auth.assert_called_once_with({"type": "gob_curl"})
        self.assertEqual(command, ["gob-curl", "-s"])

    @patch("gerrit_mcp_server.gerrit_auth._get_auth_for_http_basic")
    def test_dispatches_to_http_basic(self, mock_get_auth):
        """Tests that the dispatcher correctly calls the http_basic auth function."""
        auth_config = {"type": "http_basic", "username": "test", "auth_token": "token"}
        mock_get_auth.return_value = ["curl", "--user", "test:token", "-L"]
        config = {
            "gerrit_hosts": [
                {
                    "name": "Public",
                    "external_url": "https://public-gerrit.com/",
                    "authentication": auth_config,
                }
            ]
        }
        command = gerrit_urls.get_curl_command_for_gerrit_url(
            "https://public-gerrit.com", config
        )
        mock_get_auth.assert_called_once_with(auth_config)
        self.assertEqual(command, ["curl", "--user", "test:token", "-L"])

    @patch("gerrit_mcp_server.gerrit_auth._get_auth_for_gitcookies")
    def test_dispatches_to_gitcookies(self, mock_get_auth):
        """Tests that the dispatcher correctly calls the gitcookies auth function."""
        auth_config = {"type": "git_cookies", "gitcookies_path": "~/.gitcookies"}
        mock_get_auth.return_value = ["curl", "-b", "cookie", "-L"]
        config = {
            "gerrit_hosts": [
                {
                    "name": "Fuchsia",
                    "external_url": "https://fuchsia-review.googlesource.com/",
                    "authentication": auth_config,
                }
            ]
        }
        url = "https://fuchsia-review.googlesource.com"
        command = gerrit_urls.get_curl_command_for_gerrit_url(url, config)
        mock_get_auth.assert_called_once_with(url, auth_config)
        self.assertEqual(command, ["curl", "-b", "cookie", "-L"])

    def test_no_matching_host_raises_error(self):
        """Tests that a ValueError is raised when no matching host is found."""
        config = {"gerrit_hosts": []}
        with self.assertRaisesRegex(
            ValueError, "No configured Gerrit host found for URL"
        ):
            gerrit_urls.get_curl_command_for_gerrit_url(
                "https://some-other-gerrit.com", config
            )

    def test_no_valid_auth_method_raises_error(self):
        """Tests that a ValueError is raised when no valid auth method is configured."""
        config = {
            "gerrit_hosts": [
                {
                    "name": "Fuchsia",
                    "external_url": "https://fuchsia-review.googlesource.com/",
                    "authentication": {},  # Empty auth block
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "No valid authentication method found"):
            gerrit_urls.get_curl_command_for_gerrit_url(
                "https://fuchsia-review.googlesource.com", config
            )


if __name__ == "__main__":
    unittest.main()
