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
This module is responsible for determining the correct curl command for a given
Gerrit URL by dispatching to the appropriate authentication module.
"""

from typing import List, Dict, Any
from gerrit_mcp_server import gerrit_auth


def get_curl_command_for_gerrit_url(
    gerrit_base_url: str, config: Dict[str, Any]
) -> List[str]:
    """
    Determines the appropriate curl command based on the authentication settings
    for the given Gerrit host.
    """
    gerrit_hosts = config.get("gerrit_hosts", [])
    auth_config = None

    stripped_gerrit_base_url = (
        gerrit_base_url.replace("https://", "").replace("http://", "").rstrip("/")
    )

    for host in gerrit_hosts:
        internal_url = (
            host.get("internal_url", "")
            .replace("https://", "")
            .replace("http://", "")
            .rstrip("/")
        )
        external_url = (
            host.get("external_url", "")
            .replace("https://", "")
            .replace("http://", "")
            .rstrip("/")
        )
        if (
            stripped_gerrit_base_url == internal_url
            or stripped_gerrit_base_url == external_url
        ):
            auth_config = host.get("authentication")
            break

    if auth_config is None:
        raise ValueError(
            f"No configured Gerrit host found for URL: {gerrit_base_url}. "
            f"Please check your gerrit_config.json file."
        )

    auth_type = auth_config.get("type")

    if auth_type == "gob_curl":
        return gerrit_auth._get_auth_for_gob(auth_config)

    if auth_type == "http_basic":
        return gerrit_auth._get_auth_for_http_basic(auth_config)

    if auth_type == "git_cookies":
        return gerrit_auth._get_auth_for_gitcookies(gerrit_base_url, auth_config)

    raise ValueError(
        "No valid authentication method found in gerrit_config.json. "
        "Please configure a supported 'type' (e.g., 'http_basic', 'gob_curl', 'git_cookies') for the relevant host."
    )