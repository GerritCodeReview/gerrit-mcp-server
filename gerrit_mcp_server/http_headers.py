"""Builds curl attribution headers for Gerrit REST API requests."""

import contextvars
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version


@dataclass
class RequestObservabilityContext:
    tool_name: str
    client_name: str | None
    client_version: str | None
    protocol_version: str | None


_request_obs: contextvars.ContextVar[RequestObservabilityContext | None] = (
    contextvars.ContextVar("gerrit_mcp_request_obs", default=None)
)


def _package_version(pkg: str) -> str:
    try:
        return version(pkg)
    except PackageNotFoundError:
        return "unknown"


def build_curl_header_args(obs: RequestObservabilityContext | None) -> list[str]:
    """Returns curl args that set User-Agent and X-MCP-* attribution headers."""
    server_ver = _package_version("gerrit-mcp-server")
    sdk_ver = _package_version("mcp")

    ua_parts = [f"gerrit-mcp-server/{server_ver}", f"mcp-python-sdk/{sdk_ver}"]
    if obs and obs.client_name:
        client_ver = obs.client_version or "unknown"
        ua_parts.append(f"{obs.client_name}/{client_ver}")

    result = ["-A", " ".join(ua_parts)]

    if obs:
        if obs.tool_name:
            result += ["-H", f"X-MCP-Tool: {obs.tool_name}"]
        if obs.client_name:
            result += ["-H", f"X-MCP-Client: {obs.client_name}"]
        if obs.protocol_version:
            result += ["-H", f"X-MCP-Protocol-Version: {obs.protocol_version}"]

    return result
