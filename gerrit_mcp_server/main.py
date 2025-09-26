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

import asyncio
import json
import sys
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote
import os
import datetime  # Added this import
import argparse

from gerrit_mcp_server.gerrit_urls import get_curl_command_for_gerrit_url
from gerrit_mcp_server.bug_utils import extract_bugs_from_commit_message
from gerrit_mcp_server.sort_util import sort_changes_by_date
from mcp.server.fastmcp import FastMCP
import mcp.types as types

# --- Load Gerrit details from JSON ---
# Define paths outside the try block to ensure they are always initialized.
PKG_PATH = Path(__file__).parent
SERVER_ROOT_PATH = PKG_PATH.parent
LOG_FILE_PATH = SERVER_ROOT_PATH / "server.log"
CONFIG_FILE_PATH = PKG_PATH / "gerrit_config.json"


def load_gerrit_config() -> Dict[str, Any]:
    """Loads the Gerrit configuration from the JSON file."""
    config_path_str = os.environ.get("GERRIT_CONFIG_PATH")
    if config_path_str:
        config_path = Path(config_path_str)
    else:
        config_path = CONFIG_FILE_PATH

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found at {config_path}. "
            "Please create this file to proceed. You can copy "
            "'gerrit_mcp_server/gerrit_config.sample.json' to "
            "'gerrit_mcp_server/gerrit_config.json' as a starting point. "
            "Refer to the README.md for more details on the configuration options."
        )
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(
            f"[gerrit-mcp-server-error] Could not parse {config_path}: {e}. Please check the file for syntax errors.",
            file=sys.stderr,
        )
        raise e


try:
    with open(PKG_PATH / "gerrit_details.json", "r") as f:
        gerrit_details = json.load(f)
    # This file is not used in this implementation, but kept for pattern consistency
    with open(PKG_PATH / "gerrit_command_argument_defs.json", "r") as f:
        gerrit_arg_defs = json.load(f)
except Exception as e:
    print(
        f"[gerrit-mcp-server-error] Failed to load or parse JSON files: {e}. Using default descriptions.",
        file=sys.stderr,
    )
    gerrit_details = {
        "toolOverallDescription": "A tool to interact with Gerrit code review systems using curl."
    }

# --- Initialize FastMCP Server ---
mcp = FastMCP("gerrit")

# --- Session State ---


def _get_gerrit_base_url(gerrit_base_url: Optional[str] = None) -> str:
    """Returns the Gerrit base URL, prioritizing the parameter over the environment variable."""
    if gerrit_base_url:
        return gerrit_base_url

    config = load_gerrit_config()
    return os.environ.get(
        "GERRIT_BASE_URL",
        config.get(
            "default_gerrit_base_url", "https://fuchsia-review.googlesource.com"
        ),
    )


def _normalize_gerrit_url(url: str) -> str:
    """Normalizes a Gerrit URL based on the mappings in the config."""
    config = load_gerrit_config()
    gerrit_hosts = config.get("gerrit_hosts", [])

    # Store the original URL for explicit internal URL matching
    original_url = url.rstrip("/")
    stripped_original_url = original_url.replace("https://", "").replace("http://", "")

    normalized_url = url  # Default to original if no match found

    for host in gerrit_hosts:
        internal_url = host.get("internal_url")
        external_url = host.get("external_url")

        stripped_internal = (
            internal_url.replace("https://", "").replace("http://", "").rstrip("/")
            if internal_url
            else None
        )
        stripped_external = (
            external_url.replace("https://", "").replace("http://", "").rstrip("/")
            if external_url
            else None
        )

        if (
            stripped_original_url == stripped_internal
            or stripped_original_url == stripped_external
        ):
            # Match found. Prefer external URL if it exists.
            if external_url:
                normalized_url = external_url
            elif internal_url:
                normalized_url = internal_url
            break  # Found a match, so we can exit the loop.

    # Ensure https, then strip trailing slash
    if not (
        normalized_url.startswith("http://") or normalized_url.startswith("https://")
    ):
        normalized_url = "https://" + normalized_url
    elif normalized_url.startswith("http://"):
        normalized_url = normalized_url.replace("http://", "https://")

    return normalized_url.rstrip("/")


async def run_curl(args: List[str], gerrit_base_url: str) -> str:
    """Executes a curl command and returns the output."""
    config = load_gerrit_config()
    command = get_curl_command_for_gerrit_url(gerrit_base_url, config) + args
    with open(LOG_FILE_PATH, "a") as log_file:
        log_file.write(f"[gerrit-mcp-server] Executing: {" ".join(command)}\n")

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    stdout_str = stdout.decode()
    stderr_str = stderr.decode()

    with open(LOG_FILE_PATH, "a") as log_file:
        log_file.write("[gerrit-mcp-server] curl command finished.\n")
        log_file.write(f"[gerrit-mcp-server] stdout:\n{stdout_str}\n")
        log_file.write(f"[gerrit-mcp-server] stderr:\n{stderr_str}\n")

    if process.returncode != 0:
        error_msg = f"curl command failed with exit code {process.returncode}.\nSTDERR:\n{stderr_str}"
        with open(LOG_FILE_PATH, "a") as log_file:
            log_file.write(f"[gerrit-mcp-server] {error_msg}\n")
        raise Exception(error_msg)

    # Gerrit prepends )]\' to JSON responses to prevent XSSI.
    # We need to remove it before parsing.
    if stdout_str.startswith(")]}'"):
        stdout_str = stdout_str[4:]

    with open(LOG_FILE_PATH, "a") as log_file:
        log_file.write(f"[gerrit-mcp-server] JSON to parse:\n{stdout_str}\n")

    return stdout_str.strip()


def _create_post_args(url: str, payload: Optional[Dict[str, Any]] = None) -> List[str]:
    """Creates the argument list for a curl POST request."""
    args = ["-X", "POST"]
    if payload:
        payload_json = json.dumps(payload)
        args.extend(["-H", "Content-Type: application/json", "--data", payload_json])
    args.append(url)
    return args


def _create_put_args(url: str, payload: Optional[Dict[str, Any]] = None) -> List[str]:
    """Creates the argument list for a curl PUT request."""
    args = ["-X", "PUT"]
    if payload:
        payload_json = json.dumps(payload)
        args.extend(["-H", "Content-Type: application/json", "--data", payload_json])
    args.append(url)
    return args


# --- Tool Implementations ---


@mcp.tool()
async def query_changes(
    query: str,
    gerrit_base_url: Optional[str] = None,
    limit: Optional[int] = None,
    options: Optional[List[str]] = None,
) -> List[types.TextContent]:
    """
    Searches for CLs matching a given query string.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/?q={quote(query)}"
    if limit:
        url += f"&n={limit}"
    if options:
        for option in options:
            url += f"&o={option}"

    result_json_str = await run_curl([url], base_url)
    changes = json.loads(result_json_str)
    changes = sort_changes_by_date(changes)

    if not changes:
        return [{"type": "text", "text": f"No changes found for query: {query}"}]

    output = f'Found {len(changes)} changes for query "{query}":\n'
    for change in changes:
        wip_prefix = "[WIP] " if change.get("work_in_progress") else ""
        output += f"- {change["_number"]}: {wip_prefix}{change["subject"]}\n"

    return [{"type": "text", "text": output}]


@mcp.tool()
async def query_changes_by_date_and_filters(  # Renamed method
    start_date: str,  # Format YYYY-MM-DD
    end_date: str,  # Format YYYY-MM-DD
    gerrit_base_url: Optional[str] = None,
    limit: Optional[int] = None,
    project: Optional[str] = None,
    message_substring: Optional[str] = None,
    status: str = "merged",
) -> List[types.TextContent]:
    """
    Searches for Gerrit changes within a specified date range, optionally filtered by project,
    a substring in the commit message, and change status. This tool provides a flexible way
    to find changes based on their dates and content.

    Args:
        start_date: The start date for the changes (e.g., "2025-08-18").
        end_date: The end date for the changes (e.g., "2025-08-19").
        gerrit_base_url: The base URL of the Gerrit instance.
        limit: The maximum number of changes to return.
        project: Optional project name to filter by. This filter is only applied if `gerrit_base_url` is not explicitly provided, in which case the default Gerrit instance will be queried.
        message_substring: An optional substring to search for in the commit message.
        status: The status of the changes to search for (e.g., "merged", "open", "abandoned"). Defaults to "merged".
    """
    # Parse dates and increment end_date by one day for Gerrit's 'before' operator
    try:
        parsed_start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        parsed_end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        return [
            {
                "type": "text",
                "text": "Invalid date format. Please use YYYY-MM-DD for start_date and end_date.",
            }
        ]

    # Increment the end date by one day to make the 'before' query inclusive of the target end_date
    effective_end_date = parsed_end_date + datetime.timedelta(days=1)
    effective_end_date_str = effective_end_date.strftime("%Y-%m-%d")

    # Construct the Gerrit query string based on the specialized parameters
    query_parts = [
        f"status:{status}",
        f"after:{parsed_start_date.strftime('%Y-%m-%d')}",
        f"before:{effective_end_date_str}",  # Use the incremented date here
    ]
    # If a project is specified, add it to the query.
    if project:
        query_parts.append(f"project:{project}")
    if message_substring:
        query_parts.append(f'message:"{message_substring}"')

    full_query = " ".join(query_parts)

    # Re-use the existing 'query_changes' tool to execute the constructed query
    return await query_changes(
        query=full_query, gerrit_base_url=gerrit_base_url, limit=limit
    )


@mcp.tool()
async def get_change_details(
    change_id: str,
    gerrit_base_url: Optional[str] = None,
    options: Optional[List[str]] = None,
) -> List[types.TextContent]:
    """
    Retrieves a comprehensive summary of a single CL.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))

    # Always get the commit message and other details
    base_options = ["CURRENT_REVISION", "CURRENT_COMMIT", "DETAILED_LABELS"]
    if options:
        # Combine with user-provided options, ensuring no duplicates
        options = list(set(base_options + options))
    else:
        options = base_options

    query_params = "&".join([f"o={option}" for option in options])
    url = f"{base_url}/changes/{change_id}/detail?{query_params}"

    result_json_str = await run_curl([url], base_url)
    details = json.loads(result_json_str)

    output = f"Summary for CL {details['_number']}:\n"
    output += f"Subject: {details['subject']}\n"
    output += f"Owner: {details['owner']['email']}\n"
    output += f"Status: {details['status']}\n"

    # Extract and display bugs from commit message
    if "current_revision" in details and details["current_revision"] in details.get(
        "revisions", {}
    ):
        current_rev_info = details["revisions"][details["current_revision"]]
        if "commit" in current_rev_info and "message" in current_rev_info["commit"]:
            commit_message = current_rev_info["commit"]["message"]
            bugs = extract_bugs_from_commit_message(commit_message)
            if bugs:
                output += f"Bugs: {', '.join(sorted(list(bugs)))}\n"

    if "reviewers" in details and "REVIEWER" in details["reviewers"]:
        output += "Reviewers:\n"
        for reviewer in details["reviewers"]["REVIEWER"]:
            votes = []
            if "labels" in details:
                for label, info in details["labels"].items():
                    for vote in info.get("all", []):
                        if vote.get("_account_id") == reviewer.get("_account_id"):
                            vote_value = vote.get("value", 0)
                            vote_str = (
                                f"+{vote_value}" if vote_value > 0 else str(vote_value)
                            )
                            votes.append(f"{label}: {vote_str}")
            reviewer_email = reviewer.get("email", "N/A")
            output += f"- {reviewer_email} ({', '.join(votes)})\n"

    if "messages" in details and details["messages"]:
        output += "Recent Messages:\n"
        for msg in details["messages"][-3:]:
            author = msg.get("author", {}).get("name", "Gerrit")
            timestamp = msg.get("date", "No date")
            message_summary = msg["message"].splitlines()[0]
            output += f"- (Patch Set {msg['_revision_number']}) [{timestamp}] ({author}): {message_summary}\n"

    return [{"type": "text", "text": output}]


@mcp.tool()
async def get_commit_message(
    change_id: str,
    gerrit_base_url: Optional[str] = None,
) -> List[types.TextContent]:
    """
    Gets the commit message of a change from the current patch set.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/{change_id}/message"

    try:
        result_str = await run_curl([url], base_url)
        commit_info = json.loads(result_str)

        output = f"Commit message for CL {change_id}:\n"
        output += f"Subject: {commit_info.get('subject', 'N/A')}\n\n"
        output += "Full Message:\n"
        output += "--------------------------------------------------------\n"
        output += f"{commit_info.get('full_message', 'Message not found.')}\n"
        output += "--------------------------------------------------------\n"

        if "footers" in commit_info and commit_info["footers"]:
            output += "\nFooters:\n"
            for key, value in commit_info["footers"].items():
                output += f"- {key}: {value}\n"

        return [{"type": "text", "text": output}]

    except json.JSONDecodeError:
        return [
            {
                "type": "text",
                "text": f"Failed to get commit message for CL {change_id}. Invalid JSON response.",
            }
        ]
    except Exception as e:
        with open(LOG_FILE_PATH, "a") as log_file:
            log_file.write(
                f"[gerrit-mcp-server] Error getting commit message for CL {change_id}: {e}\n"
            )
        return [
            {
                "type": "text",
                "text": f"An error occurred while getting the commit message for CL {change_id}: {e}",
            }
        ]


@mcp.tool()
async def list_change_files(
    change_id: str, gerrit_base_url: Optional[str] = None
) -> List[types.TextContent]:
    """
    Lists all files modified in the most recent patch set of a CL.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/{change_id}/revisions/current/files/"
    result_json_str = await run_curl([url], base_url)
    files = json.loads(result_json_str)

    # We need the revision number for the patch set
    detail_url = f"{base_url}/changes/{change_id}/detail"
    detail_json_str = await run_curl([detail_url], base_url)
    details = json.loads(detail_json_str)
    patch_set = details.get("current_revision_number", "current")

    output = f"Files in CL {change_id} (Patch Set {patch_set}):\n"
    for file_path, file_info in files.items():
        if file_path == "/COMMIT_MSG":
            continue
        status = file_info.get("status", "MODIFIED")
        status_char = status[0] if status in ["ADDED", "DELETED", "RENAMED"] else "M"
        lines_inserted = file_info.get("lines_inserted", 0)
        lines_deleted = file_info.get("lines_deleted", 0)
        output += f"[{status_char}] {file_path} (+{lines_inserted}, -{lines_deleted})\n"

    return [{"type": "text", "text": output}]


@mcp.tool()
async def get_file_diff(
    change_id: str, file_path: str, gerrit_base_url: Optional[str] = None
) -> List[types.TextContent]:
    """
    Retrieves the diff for a single, specified file within a CL.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    encoded_file_path = quote(file_path, safe="")
    url = f"{base_url}/changes/{change_id}/revisions/current/patch?path={encoded_file_path}"

    diff_base64 = await run_curl([url], base_url)
    # The response is a base64 encoded string, we need to decode it.
    # The result from run_curl is already a string, so we encode it back to bytes for b64decode
    diff_text = base64.b64decode(diff_base64.encode("utf-8")).decode("utf-8")
    return [{"type": "text", "text": diff_text}]


@mcp.tool()
async def list_change_comments(
    change_id: str, gerrit_base_url: Optional[str] = None
) -> List[types.TextContent]:
    """
    list_change_comments is useful for reviewing feedback, reading comments on a change, analyzing comments, and responding to comments.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/{change_id}/comments"
    result_json_str = await run_curl([url], base_url)
    try:
        comments_by_file = json.loads(result_json_str)
    except json.JSONDecodeError:
        return [
            {
                "type": "text",
                "text": f"Failed to parse JSON response from Gerrit. Raw response:\n{result_json_str}",
            }
        ]

    output = f"Comments for CL {change_id}:\n"
    found_comments = False
    for file_path, comments in comments_by_file.items():
        output += f"---\nFile: {file_path}\n"
        found_comments = True
        for comment in comments:
            line = comment.get("line", "File")
            author = comment.get("author", {}).get("name", "Unknown")
            timestamp = comment.get("updated", "No date")
            message = comment["message"]
            status = "UNRESOLVED" if comment.get("unresolved", False) else "RESOLVED"
            output += f"L{line}: [{author}] ({timestamp}) - {status}\n"
            output += f"  {message}\n"

    if not found_comments:
        return [{"type": "text", "text": f"No comments found for CL {change_id}."}]

    return [{"type": "text", "text": output}]


@mcp.tool()
async def add_reviewer(
    change_id: str,
    reviewer: str,
    gerrit_base_url: Optional[str] = None,
    state: str = "REVIEWER",
) -> List[types.TextContent]:
    """
    Adds a user or a group to a CL as either a reviewer or a CC.
    """
    if state.upper() not in ["REVIEWER", "CC"]:
        return [
            {
                "type": "text",
                "text": f"Failed to add {reviewer}: Invalid state '{state}'. State must be either 'REVIEWER' or 'CC'.",
            }
        ]

    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/{change_id}/reviewers"
    payload = {"reviewer": reviewer, "state": state}
    args = _create_post_args(url, payload)

    try:
        result_str = await run_curl(args, base_url)
        try:
            result_data = json.loads(result_str)
            if "error" in result_data:
                return [
                    {
                        "type": "text",
                        "text": f"Failed to add {reviewer} as a {state} to CL {change_id}. Response: {result_data['error']}",
                    }
                ]
        except json.JSONDecodeError:
            # If the response is not JSON, it might be a plain text error from Gerrit
            if "error" in result_str.lower():
                return [
                    {
                        "type": "text",
                        "text": f"Failed to add {reviewer} as a {state} to CL {change_id}. Response: {result_str}",
                    }
                ]

        return [
            {
                "type": "text",
                "text": f"Successfully added {reviewer} as a {state} to CL {change_id}.",
            }
        ]
    except Exception as e:
        with open(LOG_FILE_PATH, "a") as log_file:
            log_file.write(
                f"[gerrit-mcp-server] Error adding reviewer to CL {change_id}: {e}\n"
            )
        raise e


@mcp.tool()
async def set_ready_for_review(
    change_id: str,
    gerrit_base_url: Optional[str] = None,
) -> List[types.TextContent]:
    """
    Sets a CL as ready for review.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/{change_id}/ready"
    args = _create_post_args(url)

    try:
        result_json = await run_curl(args, base_url)
        if result_json:
            return [
                {
                    "type": "text",
                    "text": f"Failed to set CL {change_id} as ready for review. Response: {result_json}",
                }
            ]
        return [{"type": "text", "text": f"CL {change_id} is now ready for review."}]
    except Exception as e:
        with open(LOG_FILE_PATH, "a") as log_file:
            log_file.write(
                f"[gerrit-mcp-server] Error setting CL {change_id} as ready for review: {e}\n"
            )
        raise e


@mcp.tool()
async def set_work_in_progress(
    change_id: str,
    message: Optional[str] = None,
    gerrit_base_url: Optional[str] = None,
) -> List[types.TextContent]:
    """
    Sets a CL as work-in-progress.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/{change_id}/wip"
    payload = {"message": message} if message else None
    args = _create_post_args(url, payload)

    try:
        result_json = await run_curl(args, base_url)
        if result_json:
            return [
                {
                    "type": "text",
                    "text": f"Failed to set CL {change_id} as work-in-progress. Response: {result_json}",
                }
            ]
        return [{"type": "text", "text": f"CL {change_id} is now a work-in-progress."}]
    except Exception as e:
        with open(LOG_FILE_PATH, "a") as log_file:
            log_file.write(
                f"[gerrit-mcp-server] Error setting CL {change_id} as work-in-progress: {e}\n"
            )
        raise e


@mcp.tool()
async def revert_change(
    change_id: str,
    message: Optional[str] = None,
    gerrit_base_url: Optional[str] = None,
) -> List[types.TextContent]:
    """
    Reverts a single change, creating a new CL.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/{change_id}/revert"
    payload = {"message": message} if message else None
    args = _create_post_args(url, payload)

    try:
        result_str = await run_curl(args, base_url)
        revert_info = json.loads(result_str)
        if "id" in revert_info and "_number" in revert_info:
            output = (
                f"Successfully reverted CL {change_id}.\n"
                f"New revert CL created: {revert_info['_number']}\n"
                f"Subject: {revert_info['subject']}"
            )
            return [{"type": "text", "text": output}]
        else:
            return [
                {
                    "type": "text",
                    "text": f"Failed to revert CL {change_id}. Response: {result_str}",
                }
            ]
    except json.JSONDecodeError:
        return [
            {
                "type": "text",
                "text": f"Failed to revert CL {change_id}. Response: {result_str}",
            }
        ]
    except Exception as e:
        with open(LOG_FILE_PATH, "a") as log_file:
            log_file.write(f"[gerrit-mcp-server] Error reverting CL {change_id}: {e}\n")
        raise e


@mcp.tool()
async def revert_submission(
    change_id: str,
    message: Optional[str] = None,
    gerrit_base_url: Optional[str] = None,
) -> List[types.TextContent]:
    """
    Reverts an entire submission, creating one or more new CLs.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/{change_id}/revert_submission"
    payload = {"message": message} if message else None
    args = _create_post_args(url, payload)

    try:
        result_str = await run_curl(args, base_url)
        submission_info = json.loads(result_str)
        if "revert_changes" in submission_info:
            output = f"Successfully reverted submission for CL {change_id}.\n"
            output += "Created revert changes:\n"
            for change in submission_info["revert_changes"]:
                output += f"- {change['_number']}: {change['subject']}\n"
            return [{"type": "text", "text": output}]
        else:
            return [
                {
                    "type": "text",
                    "text": f"Failed to revert submission for CL {change_id}. Response: {result_str}",
                }
            ]
    except json.JSONDecodeError:
        return [
            {
                "type": "text",
                "text": f"Failed to revert submission for CL {change_id}. Response: {result_str}",
            }
        ]
    except Exception as e:
        with open(LOG_FILE_PATH, "a") as log_file:
            log_file.write(
                f"[gerrit-mcp-server] Error reverting submission for CL {change_id}: {e}\n"
            )
        raise e


@mcp.tool()
async def create_change(
    project: str,
    subject: str,
    branch: str,
    topic: Optional[str] = None,
    status: Optional[str] = None,
    gerrit_base_url: Optional[str] = None,
) -> List[types.TextContent]:
    """
    Creates a new change in Gerrit.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/"

    payload = {
        "project": project,
        "subject": subject,
        "branch": branch,
    }
    if topic:
        payload["topic"] = topic
    if status:
        payload["status"] = status

    payload_json = json.dumps(payload)

    args = [
        "-X",
        "POST",
        "-H",
        "Content-Type: application/json",
        "--data",
        payload_json,
        url,
    ]

    try:
        result_str = await run_curl(args, base_url)
        if not result_str.startswith("{"):
            return [
                {
                    "type": "text",
                    "text": f"Failed to create change. Response: {result_str}",
                }
            ]

        change_info = json.loads(result_str)
        if "id" in change_info and "_number" in change_info:
            output = (
                f"Successfully created new change {change_info['_number']}.\n"
                f"Subject: {change_info['subject']}\n"
                f"Project: {change_info['project']}, Branch: {change_info['branch']}"
            )
            return [{"type": "text", "text": output}]
        else:
            return [
                {
                    "type": "text",
                    "text": f"Failed to create change. Response: {result_str}",
                }
            ]

    except Exception as e:
        return [
            {
                "type": "text",
                "text": f"An error occurred while creating the change: {e}",
            }
        ]


@mcp.tool()
async def set_topic(
    change_id: str,
    topic: str,
    gerrit_base_url: Optional[str] = None,
) -> List[types.TextContent]:
    """
    Sets the topic of a change. An empty string deletes the topic.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/{change_id}/topic"

    payload = json.dumps({"topic": topic})
    args = ["-X", "PUT", "-H", "Content-Type: application/json", "--data", payload, url]

    try:
        result_str = await run_curl(args, base_url)

        if not result_str:
            return [
                {
                    "type": "text",
                    "text": f"Topic successfully deleted from CL {change_id}.",
                }
            ]

        new_topic = json.loads(result_str)
        return [
            {
                "type": "text",
                "text": f"Successfully set topic for CL {change_id} to: {new_topic}",
            }
        ]

    except Exception as e:
        # Check if the exception is a JSONDecodeError and try to get the response text
        if isinstance(e, json.JSONDecodeError):
            # The raw response is not directly available in the exception,
            # so we have to re-run the command to get the raw output for the error message.
            # This is not ideal, but it's the most reliable way to get the error message.
            try:
                raw_response = await run_curl(args, base_url)
                return [
                    {
                        "type": "text",
                        "text": f"Failed to set topic for CL {change_id}. Response: {raw_response}",
                    }
                ]
            except Exception as inner_e:
                return [
                    {
                        "type": "text",
                        "text": f"An error occurred while setting the topic for CL {change_id}: {inner_e}",
                    }
                ]
        return [
            {
                "type": "text",
                "text": f"An error occurred while setting the topic for CL {change_id}: {e}",
            }
        ]


@mcp.tool()
async def changes_submitted_together(
    change_id: str,
    gerrit_base_url: Optional[str] = None,
    options: Optional[List[str]] = None,
) -> List[types.TextContent]:
    """
    Computes and lists all changes that would be submitted together with a given CL.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/{change_id}/submitted_together"

    if options:
        query_params = "&".join([f"o={option}" for option in options])
        url += f"?{query_params}"

    try:
        result_str = await run_curl([url], base_url)
        if not result_str:
            return [
                {"type": "text", "text": "This change would be submitted by itself."}
            ]

        data = json.loads(result_str)

        changes = []
        non_visible_changes = 0

        if isinstance(data, dict) and "changes" in data:
            changes = data.get("changes", [])
            non_visible_changes = data.get("non_visible_changes", 0)
        elif isinstance(data, list):
            changes = data

        if not changes:
            return [
                {"type": "text", "text": "This change would be submitted by itself."}
            ]

        output = f"The following {len(changes)} changes would be submitted together:\n"
        for change in changes:
            output += f"- {change['_number']}: {change['subject']}\n"

        if non_visible_changes > 0:
            output += f"Plus {non_visible_changes} other changes that are not visible to you.\n"

        return [{"type": "text", "text": output}]

    except json.JSONDecodeError:
        return [
            {
                "type": "text",
                "text": f"Failed to get submitted together info for CL {change_id}. Response: {result_str}",
            }
        ]
    except Exception as e:
        return [
            {
                "type": "text",
                "text": f"An error occurred while getting submitted together info for CL {change_id}: {e}",
            }
        ]


@mcp.tool()
async def suggest_reviewers(
    change_id: str,
    query: str,
    limit: Optional[int] = None,
    exclude_groups: bool = False,
    reviewer_state: Optional[str] = None,
    gerrit_base_url: Optional[str] = None,
) -> List[types.TextContent]:
    """
    Suggests reviewers for a change based on a query.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/{change_id}/suggest_reviewers?q={quote(query)}"

    if limit:
        url += f"&n={limit}"
    if exclude_groups:
        url += "&exclude-groups"
    if reviewer_state:
        url += f"&reviewer-state={reviewer_state}"

    try:
        result_str = await run_curl([url], base_url)
        if not result_str:
            return [{"type": "text", "text": "No reviewers found for the given query."}]

        reviewers = json.loads(result_str)
        if not reviewers:
            return [{"type": "text", "text": "No reviewers found for the given query."}]

        output = "Suggested reviewers:\n"
        for suggestion in reviewers:
            if "account" in suggestion:
                account = suggestion["account"]
                output += f"- Account: {account.get('name', '')} ({account.get('email', 'No email')})\n"
            elif "group" in suggestion:
                group = suggestion["group"]
                output += f"- Group: {group.get('name', 'Unnamed Group')}\n"

        return [{"type": "text", "text": output}]

    except json.JSONDecodeError:
        return [
            {
                "type": "text",
                "text": f"Failed to get reviewer suggestions for CL {change_id}. Response: {result_str}",
            }
        ]
    except Exception as e:
        return [
            {
                "type": "text",
                "text": f"An error occurred while suggesting reviewers for CL {change_id}: {e}",
            }
        ]


@mcp.tool()
async def abandon_change(
    change_id: str,
    message: Optional[str] = None,
    gerrit_base_url: Optional[str] = None,
) -> List[types.TextContent]:
    """
    Abandons a change.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/{change_id}/abandon"
    payload = {"message": message} if message else None
    args = _create_post_args(url, payload)

    try:
        result_str = await run_curl(args, base_url)
        abandon_info = json.loads(result_str)
        if "id" in abandon_info and abandon_info.get("status") == "ABANDONED":
            output = (
                f"Successfully abandoned CL {change_id}.\n"
                f"Status: {abandon_info['status']}"
            )
            return [{"type": "text", "text": output}]
        else:
            return [
                {
                    "type": "text",
                    "text": f"Failed to abandon CL {change_id}. Response: {result_str}",
                }
            ]
    except json.JSONDecodeError:
        return [
            {
                "type": "text",
                "text": f"Failed to abandon CL {change_id}. Response: {result_str}",
            }
        ]
    except Exception as e:
        with open(LOG_FILE_PATH, "a") as log_file:
            log_file.write(
                f"[gerrit-mcp-server] Error abandoning CL {change_id}: {e}\n"
            )
        raise e


@mcp.tool()
async def get_most_recent_cl(
    user: str, gerrit_base_url: Optional[str] = None
) -> List[types.TextContent]:
    """
    Gets the most recent CL for a user.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    query = f"owner:{user}"
    url = f"{base_url}/changes/?q={quote(query)}&n=1"
    result_json_str = await run_curl([url], base_url)
    changes = json.loads(result_json_str)

    if not changes:
        return [{"type": "text", "text": f"No changes found for user: {user}"}]

    change = changes[0]
    wip_prefix = "[WIP] " if change.get("work_in_progress") else ""
    output = f"Most recent CL for {user}:\n"
    output += f"- {change["_number"]}: {wip_prefix}{change["subject"]}\n"

    return [{"type": "text", "text": output}]


@mcp.tool()
async def get_bugs_from_cl(
    change_id: str, gerrit_base_url: Optional[str] = None
) -> List[types.TextContent]:
    """
    Extracts bug IDs from the commit message of a CL.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/{change_id}/revisions/current/commit"
    result_json_str = await run_curl([url], base_url)
    if not result_json_str:
        return [
            {"type": "text", "text": f"No commit message found for CL {change_id}."}
        ]
    details = json.loads(result_json_str)

    commit_message = details.get("message")

    if not commit_message:
        return [
            {"type": "text", "text": f"No commit message found for CL {change_id}."}
        ]

    bug_ids = extract_bugs_from_commit_message(commit_message)

    if not bug_ids:
        return [
            {
                "type": "text",
                "text": f"No bug IDs found in the commit message for CL {change_id}.",
            }
        ]

    bug_list_str = ", ".join(sorted(list(bug_ids)))
    return [
        {
            "type": "text",
            "text": f"Found bug(s): {bug_list_str}. Would you like me to get more details using the `@bugged` tool?",
        }
    ]


@mcp.tool()
async def post_review_comment(
    change_id: str,
    file_path: str,
    line_number: int,
    message: str,
    unresolved: bool = True,
    gerrit_base_url: Optional[str] = None,
) -> List[types.TextContent]:
    """
    Posts a review comment on a specific line of a file in a CL.
    """
    base_url = _normalize_gerrit_url(_get_gerrit_base_url(gerrit_base_url))
    url = f"{base_url}/changes/{change_id}/revisions/current/review"

    payload = {
        "comments": {
            file_path:
                [
                    {
                        "line": line_number,
                        "message": message,
                        "unresolved": unresolved,
                    }
                ],
        }
    }
    args = _create_post_args(url, payload)

    try:
        result_str = await run_curl(args, base_url)
        # A successful response should contain the updated review information
        if "comments" in result_str:
            return [
                {
                    "type": "text",
                    "text": f"Successfully posted comment to CL {change_id} on file {file_path} at line {line_number}.",
                }
            ]
        else:
            return [
                {
                    "type": "text",
                    "text": f"Failed to post comment. Response: {result_str}",
                }
            ]
    except Exception as e:
        with open(LOG_FILE_PATH, "a") as log_file:
            log_file.write(
                f"[gerrit-mcp-server] Error posting comment to CL {change_id}: {e}\n"
            )
        raise e



def cli_main(argv: List[str]):
    """
    The main entry point for the command-line interface.
    This function is responsible for parsing arguments and running the server.
    """
    # If 'stdio' is an argument, run in stdio mode and bypass HTTP server logic.
    if "stdio" in argv:
        mcp.run(transport="stdio")
    else:
        # Otherwise, run as a normal HTTP server.
        parser = argparse.ArgumentParser(description="Gerrit MCP Server")
        parser.add_argument(
            "--host", type=str, default="localhost", help="Host to bind the server to."
        )
        parser.add_argument(
            "--port",
            type=int,
            default=6322,
            help="Port to bind the server to. Defaults to 6322 (close to 'gerrit' in leetspeak).",
        )
        args = parser.parse_args(argv[1:])

        # Update the server's settings with the parsed arguments
        mcp.settings.host = args.host
        mcp.settings.port = args.port

        # Run the server using the correct transport
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    cli_main(sys.argv)

app = mcp.streamable_http_app()