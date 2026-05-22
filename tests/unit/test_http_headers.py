import unittest
from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

from gerrit_mcp_server.http_headers import (
    RequestObservabilityContext,
    build_curl_header_args,
)


def _make_obs(**kwargs):
    defaults = dict(
        tool_name="my_tool",
        client_name="test-client",
        client_version="1.2.3",
        protocol_version="2025-11-25",
    )
    defaults.update(kwargs)
    return RequestObservabilityContext(**defaults)


class TestBuildCurlHeaderArgs(unittest.TestCase):
    def test_no_obs_returns_static_ua_only(self):
        result = build_curl_header_args(None)
        self.assertEqual(result[0], "-A")
        ua = result[1]
        self.assertIn("gerrit-mcp-server/", ua)
        self.assertIn("mcp-python-sdk/", ua)
        # No X- headers
        self.assertNotIn("-H", result)

    def test_full_obs_has_three_ua_tokens_and_all_x_headers(self):
        result = build_curl_header_args(_make_obs())
        ua = result[1]
        tokens = ua.split(" ")
        self.assertEqual(len(tokens), 3)
        self.assertTrue(tokens[0].startswith("gerrit-mcp-server/"))
        self.assertTrue(tokens[1].startswith("mcp-python-sdk/"))
        self.assertEqual(tokens[2], "test-client/1.2.3")
        self.assertIn("X-MCP-Tool: my_tool", result)
        self.assertIn("X-MCP-Client: test-client", result)
        self.assertIn("X-MCP-Protocol-Version: 2025-11-25", result)

    def test_missing_client_name_omits_x_mcp_client_and_ua_token(self):
        result = build_curl_header_args(_make_obs(client_name=None))
        ua = result[1]
        tokens = ua.split(" ")
        self.assertEqual(len(tokens), 2)
        self.assertNotIn("X-MCP-Client: None", result)
        header_values = [result[i + 1] for i, v in enumerate(result) if v == "-H"]
        self.assertFalse(any("X-MCP-Client" in h for h in header_values))

    def test_missing_client_version_uses_unknown_in_ua(self):
        result = build_curl_header_args(_make_obs(client_version=None))
        ua = result[1]
        self.assertIn("test-client/unknown", ua)

    def test_missing_protocol_version_omits_x_mcp_protocol_version(self):
        result = build_curl_header_args(_make_obs(protocol_version=None))
        header_values = [result[i + 1] for i, v in enumerate(result) if v == "-H"]
        self.assertFalse(any("X-MCP-Protocol-Version" in h for h in header_values))

    def test_version_fallback_on_package_not_found(self):
        with patch(
            "gerrit_mcp_server.http_headers.version",
            side_effect=PackageNotFoundError("pkg"),
        ):
            result = build_curl_header_args(None)
        ua = result[1]
        self.assertIn("gerrit-mcp-server/unknown", ua)
        self.assertIn("mcp-python-sdk/unknown", ua)
