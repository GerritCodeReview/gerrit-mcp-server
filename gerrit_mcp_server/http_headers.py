"""Builds curl attribution headers for Gerrit REST API requests.

Per-request identity comes from the MCP client's ``Authorization`` header,
either ``Basic`` or Gerrit's ``Bearer`` token. That value is held in
``_client_authorization`` for the duration of a tool call and forwarded to
Gerrit. When the header is absent, curl falls back to the username and
auth_token in ``gerrit_config.json``.
"""

import contextvars
import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

# Gerrit matches these prefixes exactly, including the trailing space and the
# capitalisation (see ProjectOAuthFilter: "Basic " / "Bearer ").
_AUTH_SCHEMES = {"basic": "Basic", "bearer": "Bearer"}


def _reject_if_unsafe(value: str, sentinel: str = "unparseable") -> str:
    """Return value unchanged, or sentinel if it contains control characters."""
    return sentinel if _CONTROL_CHARS.search(value) else value


@dataclass
class RequestObservabilityContext:
    tool_name: str
    client_name: str | None
    client_version: str | None
    protocol_version: str | None


_request_obs: contextvars.ContextVar[RequestObservabilityContext | None] = (
    contextvars.ContextVar("gerrit_mcp_request_obs", default=None)
)

# The calling MCP client's Authorization header, forwarded to Gerrit as-is.
# None means this request has no client credential and config auth applies.
_client_authorization: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "gerrit_mcp_client_authorization", default=None
)


def _package_version(pkg: str) -> str:
    try:
        return version(pkg)
    except PackageNotFoundError:
        return "unknown"


def _lookup_header(headers: Mapping[str, str], name: str) -> str | None:
    """Return one header value, matching the name case-insensitively."""
    wanted = name.lower()
    getter = getattr(headers, "get", None)
    if callable(getter):
        found = getter(name)
        if found is None:
            found = getter(wanted)
        if found is not None:
            return found
    for key, value in headers.items():
        if str(key).lower() == wanted:
            return value
    return None


def client_authorization(headers: Mapping[str, str] | None) -> str | None:
    """Return the MCP client's Authorization value, or None when it is absent.

    ``Basic <credentials>`` is the HTTP password. ``Bearer <token>`` is the
    Gerrit 3 token. The scheme is rewritten to the spelling Gerrit matches.
    Control characters, an unknown scheme, or a missing credential are
    rejected so the value cannot inject extra curl headers. An empty header
    is treated as absent.
    """
    if not headers:
        return None
    raw = _lookup_header(headers, "authorization")
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    if _CONTROL_CHARS.search(value):
        raise ValueError("Authorization header contains control characters")
    scheme, _sep, credential = value.partition(" ")
    canonical = _AUTH_SCHEMES.get(scheme.lower())
    credential = credential.strip()
    if canonical is None or not credential:
        raise ValueError(
            "Authorization must be 'Basic <credentials>' or 'Bearer <token>'"
        )
    if _CONTROL_CHARS.search(credential):
        raise ValueError("Authorization header contains control characters")
    return f"{canonical} {credential}"


def build_curl_header_args(obs: RequestObservabilityContext | None) -> list[str]:
    """Returns curl args that set User-Agent and X-MCP-* attribution headers."""
    server_ver = _package_version("gerrit-mcp-server")
    sdk_ver = _package_version("mcp")

    ua_parts = [f"gerrit-mcp-server/{server_ver}", f"mcp-python-sdk/{sdk_ver}"]
    if obs and obs.client_name:
        client_name = _reject_if_unsafe(obs.client_name)
        client_ver = (
            _reject_if_unsafe(obs.client_version) if obs.client_version else "unknown"
        )
        ua_parts.append(f"{client_name}/{client_ver}")

    result = ["-A", " ".join(ua_parts)]

    if obs:
        if obs.tool_name:
            result += ["-H", f"X-MCP-Tool: {_reject_if_unsafe(obs.tool_name)}"]
        if obs.client_name:
            result += ["-H", f"X-MCP-Client: {_reject_if_unsafe(obs.client_name)}"]
        if obs.protocol_version:
            result += [
                "-H",
                f"X-MCP-Protocol-Version: {_reject_if_unsafe(obs.protocol_version)}",
            ]

    return result
