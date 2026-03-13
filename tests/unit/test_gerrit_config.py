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
from unittest.mock import patch
from gerrit_mcp_server.main import _normalize_gerrit_url


class TestGerritConfig(unittest.TestCase):

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    def test_normalize_gerrit_url_with_full_mapping(self, mock_load_config):
        mock_load_config.return_value = {
            "gerrit_hosts": [
                {
                    "name": "Foo",
                    "internal_url": "https://foo.internal/",
                    "external_url": "https://external.foo/",
                }
            ]
        }
        gerrit_hosts = mock_load_config.return_value["gerrit_hosts"]
        self.assertEqual(_normalize_gerrit_url("foo.internal", gerrit_hosts), "https://external.foo")
        self.assertEqual(
            _normalize_gerrit_url("https://foo.internal", gerrit_hosts), "https://external.foo"
        )
        self.assertEqual(_normalize_gerrit_url("external.foo", gerrit_hosts), "https://external.foo")

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    def test_normalize_gerrit_url_with_internal_only_mapping(self, mock_load_config):
        mock_load_config.return_value = {
            "gerrit_hosts": [
                {"name": "Internal", "internal_url": "https://internal2.foo/"}
            ]
        }
        gerrit_hosts = mock_load_config.return_value["gerrit_hosts"]
        self.assertEqual(
            _normalize_gerrit_url("internal2.foo", gerrit_hosts), "https://internal2.foo"
        )

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    def test_normalize_gerrit_url_with_external_only_mapping(self, mock_load_config):
        mock_load_config.return_value = {
            "gerrit_hosts": [
                {"name": "External", "external_url": "https://another.gerrit.com/"}
            ]
        }
        gerrit_hosts = mock_load_config.return_value["gerrit_hosts"]
        self.assertEqual(
            _normalize_gerrit_url("another.gerrit.com", gerrit_hosts), "https://another.gerrit.com"
        )

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    def test_normalize_gerrit_url_no_mapping(self, mock_load_config):
        mock_load_config.return_value = {"gerrit_hosts": []}
        gerrit_hosts = mock_load_config.return_value["gerrit_hosts"]
        self.assertEqual(
            _normalize_gerrit_url("unmapped.url.com", gerrit_hosts), "https://unmapped.url.com"
        )

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    def test_normalize_gerrit_url_with_mixed_mappings(self, mock_load_config):
        mock_load_config.return_value = {
            "gerrit_hosts": [
                {
                    "name": "Foo",
                    "internal_url": "https://foo.internal/",
                    "external_url": "https://external.foo/",
                },
                {"name": "Internal2", "internal_url": "https://internal2.foo/"},
                {"name": "Another", "external_url": "https://another.gerrit.com/"},
            ]
        }
        gerrit_hosts = mock_load_config.return_value["gerrit_hosts"]
        self.assertEqual(_normalize_gerrit_url("foo.internal", gerrit_hosts), "https://external.foo")
        self.assertEqual(
            _normalize_gerrit_url("internal2.foo", gerrit_hosts), "https://internal2.foo"
        )
        self.assertEqual(
            _normalize_gerrit_url("another.gerrit.com", gerrit_hosts), "https://another.gerrit.com"
        )
        self.assertEqual(
            _normalize_gerrit_url("unmapped.url.com", gerrit_hosts), "https://unmapped.url.com"
        )


    @patch("gerrit_mcp_server.main.load_gerrit_config")
    def test_normalize_gerrit_url_adds_a_prefix_for_http_basic(self, mock_load_config):
        mock_load_config.return_value = {
            "gerrit_hosts": [
                {
                    "name": "GerritHub",
                    "external_url": "https://review.gerrithub.io/",
                    "authentication": {"type": "http_basic", "username": "u", "auth_token": "t"},
                }
            ]
        }
        gerrit_hosts = mock_load_config.return_value["gerrit_hosts"]
        self.assertEqual(
            _normalize_gerrit_url("review.gerrithub.io", gerrit_hosts), "https://review.gerrithub.io/a"
        )

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    def test_normalize_gerrit_url_adds_a_prefix_for_git_cookies(self, mock_load_config):
        mock_load_config.return_value = {
            "gerrit_hosts": [
                {
                    "name": "Self-hosted",
                    "external_url": "https://gerrit.example.com/",
                    "authentication": {"type": "git_cookies", "gitcookies_path": "~/.gitcookies"},
                }
            ]
        }
        gerrit_hosts = mock_load_config.return_value["gerrit_hosts"]
        self.assertEqual(
            _normalize_gerrit_url("gerrit.example.com", gerrit_hosts), "https://gerrit.example.com/a"
        )

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    def test_normalize_gerrit_url_no_a_prefix_for_gob_curl(self, mock_load_config):
        mock_load_config.return_value = {
            "gerrit_hosts": [
                {
                    "name": "Google",
                    "external_url": "https://fuchsia-review.googlesource.com/",
                    "authentication": {"type": "gob_curl"},
                }
            ]
        }
        gerrit_hosts = mock_load_config.return_value["gerrit_hosts"]
        self.assertEqual(
            _normalize_gerrit_url("fuchsia-review.googlesource.com", gerrit_hosts),
            "https://fuchsia-review.googlesource.com",
        )

    @patch("gerrit_mcp_server.main.load_gerrit_config")
    def test_normalize_gerrit_url_no_a_prefix_without_authentication(self, mock_load_config):
        mock_load_config.return_value = {
            "gerrit_hosts": [
                {
                    "name": "NoAuth",
                    "external_url": "https://noauth.gerrit.com/",
                }
            ]
        }
        gerrit_hosts = mock_load_config.return_value["gerrit_hosts"]
        self.assertEqual(
            _normalize_gerrit_url("noauth.gerrit.com", gerrit_hosts), "https://noauth.gerrit.com"
        )


if __name__ == "__main__":
    unittest.main()
