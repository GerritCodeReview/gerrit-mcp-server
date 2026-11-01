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
This module handles the creation of authentication-specific curl commands for Gerrit.
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
from urllib.parse import urlsplit, urlunsplit

REDACTED = "<redacted>"


@dataclass(frozen=True)
class CurlAuth:
    """A curl command prefix together with the credentials it puts on it.

    The function that builds an authenticated command is the one that knows
    which of its arguments are credentials, so it names them here instead of
    leaving a later caller to recognise them in a flat argument list.
    """

    argv: List[str]
    secrets: Tuple[str, ...] = field(default=(), repr=False)
    stdin: bytes | None = field(default=None, repr=False)

    @property
    def redacted_argv(self) -> List[str]:
        """The command prefix with every credential argument masked."""
        secret_set = set(filter(None, self.secrets))
        return [REDACTED if token in secret_set else token for token in self.argv]


def _get_auth_for_gob(config: Dict[str, Any]) -> CurlAuth:
    """Returns the command for gob-curl authentication."""
    return CurlAuth(["gob-curl", "-s"])


def _get_auth_for_http_basic(config: Dict[str, Any]) -> CurlAuth:
    """Returns the command for HTTP basic authentication.

    The preferred setup omits both 'username' and 'auth_token', so curl reads
    credentials from a netrc file (keyed by host) via '--netrc', or
    '--netrc-file <netrc_path>' when 'netrc_path' is set. This mirrors
    'git_cookies' and avoids duplicating credentials in gerrit_config.json.

    Alternatively, credentials may be supplied explicitly via 'username' and
    'auth_token', in which case curl authenticates with '--user'.
    """
    username = config.get("username")
    auth_token = config.get("auth_token")

    if not username and not auth_token:
        netrc_path = config.get("netrc_path")
        if netrc_path:
            expanded_netrc_path = os.path.expanduser(netrc_path)
            if not os.path.exists(expanded_netrc_path):
                raise ValueError(
                    f"Specified 'netrc_path' does not exist: {expanded_netrc_path}"
                )
            return CurlAuth(["curl", "--netrc-file", expanded_netrc_path, "-L"])
        return CurlAuth(["curl", "--netrc", "-L"])

    if not username or not auth_token:
        raise ValueError(
            "For 'http_basic' authentication, provide both 'username' and "
            "'auth_token', or omit both to use credentials from your netrc file."
        )
    credentials = f"{username}:{auth_token}"
    return CurlAuth(["curl", "--user", credentials, "-L"], secrets=(credentials,))


def _get_auth_for_git_credentials(
    gerrit_base_url: str, config: Dict[str, Any]
) -> CurlAuth:
    """Look up HTTP credentials using Git's user/system credential helpers."""
    if any(ord(c) < 32 for c in gerrit_base_url):
        raise ValueError("Git credential URL must not contain control characters.")
    url = urlsplit(gerrit_base_url)
    path = url.path.rstrip("/")
    if path.endswith("/a"):
        path = path[:-2]
    if (
        url.scheme not in ("http", "https")
        or not url.hostname
        or url.username is not None
        or url.query
        or url.fragment
    ):
        raise ValueError("Git credentials require an HTTP(S) Gerrit base URL.")
    credential_url = urlunsplit((url.scheme, url.netloc, path, "", ""))
    username = config.get("username")
    if username is not None and (not isinstance(username, str) or not username):
        raise ValueError("Git credentials username must be a non-empty string.")
    request = f"url={credential_url}\n"
    if username:
        request += f"username={username}\n"
    if any(c in credential_url + (username or "") for c in "\r\n\0"):
        raise ValueError("Git credential input must not contain control characters.")

    env = os.environ.copy()
    # Do not let the agent's repository select credential helpers.
    for key in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_COMMON_DIR",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_CONFIG",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG_PARAMETERS",
    ):
        env.pop(key, None)
    env.update(GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="", SSH_ASKPASS="")
    try:
        with tempfile.TemporaryDirectory(prefix="gerrit-credentials-") as cwd:
            # Stop discovery before reaching a repository containing the temp dir.
            env["GIT_CEILING_DIRECTORIES"] = cwd
            result = subprocess.run(
                [
                    "git",
                    "-c",
                    "core.askPass=",
                    "-c",
                    "credential.interactive=false",
                    "credential",
                    "fill",
                ],
                input=request + "\n",
                text=True,
                capture_output=True,
                timeout=30,
                cwd=cwd,
                env=env,
                check=False,
            )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError(
            "Git credential lookup failed or timed out. Check that Git is installed "
            "and your credential helper/keyring is available."
        ) from None
    if result.returncode:
        # Helper stderr and exceptions may contain credentials: never relay them.
        raise ValueError(
            "Git credential lookup failed. Configure a Git credential helper "
            "and unlock its credential store; interactive prompting is disabled."
        )
    credentials = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            credentials[key] = value
    user = credentials.get("username")
    password = credentials.get("password")
    if not user or not password:
        raise ValueError(
            "Git credential helper did not return a username and password."
        )
    if ":" in user or any(ord(c) < 32 for c in user + password):
        raise ValueError(
            "Git credential helper returned unsupported credential characters."
        )

    # curl config quoting: secrets travel over stdin, never argv or a disk file.
    value = (user + ":" + password).replace("\\", "\\\\").replace('"', '\\"')
    return CurlAuth(
        ["curl", "--config", "-", "-L"],
        secrets=(password,),
        stdin=f'user = "{value}"\n'.encode(),
    )


def _get_auth_for_gitcookies(gerrit_base_url: str, config: Dict[str, Any]) -> CurlAuth:
    """
    Returns the command for gitcookies authentication, falling back to an
    unauthenticated request if the cookie is not found.
    """
    gitcookies_path_str = config.get("gitcookies_path")
    if not gitcookies_path_str:
        # This indicates a configuration error where gitcookies is the intended
        # method but the path is missing.
        raise ValueError("Authentication method requires 'gitcookies_path' to be set.")

    gitcookies_path = os.path.expanduser(gitcookies_path_str)

    last_found_cookie = None
    if os.path.exists(gitcookies_path):
        domain = (
            gerrit_base_url.replace("https://", "").replace("http://", "").split("/")[0]
        )
        with open(gitcookies_path, "r") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) == 7:
                    cookie_domain = parts[0]
                    # Support exact match and wildcard (leading dot) domains.
                    # A leading dot means the entry also matches subdomains;
                    # without it, only an exact host match is allowed.
                    if cookie_domain.startswith("."):
                        normalized = cookie_domain.lstrip(".")
                        match = domain == normalized or domain.endswith(
                            "." + normalized
                        )
                    else:
                        match = domain == cookie_domain
                    if match:
                        last_found_cookie = f"{parts[5]}={parts[6]}"

        if last_found_cookie:
            return CurlAuth(
                ["curl", "-b", last_found_cookie, "-L"], secrets=(last_found_cookie,)
            )

    # Fallback for when the cookie file doesn't exist or has no matching cookie.
    return CurlAuth(["curl", "-s", "-L"])
