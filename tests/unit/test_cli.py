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
Tests for the command-line interface of the Gerrit MCP server.
"""

import unittest
from unittest.mock import patch
from gerrit_mcp_server import main


class TestCli(unittest.TestCase):

    @patch("gerrit_mcp_server.main.mcp")
    def test_cli_main_stdio_mode(self, mock_mcp):
        """Tests that the server runs in stdio mode when 'stdio' is an argument."""
        main.cli_main(["main.py", "stdio"])
        mock_mcp.run.assert_called_once_with(transport="stdio")

    @patch("gerrit_mcp_server.main.mcp")
    def test_cli_main_http_mode_default_args(self, mock_mcp):
        """Tests that the server runs in HTTP mode with default host and port."""
        main.cli_main(["main.py"])
        self.assertEqual(mock_mcp.settings.host, "localhost")
        self.assertEqual(mock_mcp.settings.port, 6322)
        mock_mcp.run.assert_called_once_with(transport="streamable-http")

    @patch("gerrit_mcp_server.main.mcp")
    def test_cli_main_http_mode_custom_args(self, mock_mcp):
        """Tests that the server runs in HTTP mode with custom host and port."""
        main.cli_main(["main.py", "--host", "0.0.0.0", "--port", "9999"])
        self.assertEqual(mock_mcp.settings.host, "0.0.0.0")
        self.assertEqual(mock_mcp.settings.port, 9999)
        mock_mcp.run.assert_called_once_with(transport="streamable-http")


if __name__ == "__main__":
    unittest.main()
