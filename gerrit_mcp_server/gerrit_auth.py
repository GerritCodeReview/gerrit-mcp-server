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
from typing import List, Dict, Any


def _get_auth_for_gob(config: Dict[str, Any]) -> List[str]:
    """Returns the command for gob-curl authentication."""
    return ["gob-curl", "-s"]


def _get_auth_for_http_basic(config: Dict[str, Any]) -> List[str]:
    """Returns the command for HTTP basic authentication."""
    username = config.get("username")
    auth_token = config.get("auth_token")
    if not username or not auth_token:
        raise ValueError(
            "For 'http_basic' authentication, both 'username' and 'auth_token' must be configured."
        )
    return ["curl", "--user", f"{username}:{auth_token}", "-L"]


def _get_auth_for_gitcookies(gerrit_base_url: str, config: Dict[str, Any]) -> List[str]:
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
                if domain in line:
                    parts = line.strip().split("\t")
                    if len(parts) == 7:
                        last_found_cookie = f"{parts[5]}={parts[6]}"

        if last_found_cookie:
            return ["curl", "-b", last_found_cookie, "-L"]

    # Fallback for when the cookie file doesn't exist or has no matching cookie.
    return ["curl", "-s", "-L"]