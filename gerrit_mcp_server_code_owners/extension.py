"""gerrit-mcp-server extension for the Gerrit code-owners plugin.

Exposes three MCP tools:
  - get_code_owner_status: per-file code owner approval status for a change
  - get_code_owners_for_path: code owners for a specific path in a change revision
  - check_code_owner: check whether a user is a code owner for a path in a branch

All tools require the 'code-owners' Gerrit plugin via @requires_plugin.
"""

import json
from typing import Any, Dict, List, NotRequired, Optional, TypedDict
from urllib.parse import quote

from gerrit_mcp_server.extensions import ExtensionContext, requires_plugin


class _PathCodeOwnerStatusInfo(TypedDict):
    path: str
    status: str
    reasons: NotRequired[List[str]]


class _FileCodeOwnerStatusInfo(TypedDict):
    change_type: NotRequired[str]
    old_path_status: NotRequired[_PathCodeOwnerStatusInfo]
    new_path_status: NotRequired[_PathCodeOwnerStatusInfo]


class _CodeOwnerStatusResult(TypedDict):
    change_id: str
    patch_set_number: int
    file_code_owner_statuses: List[_FileCodeOwnerStatusInfo]
    more: NotRequired[bool]


class _AccountInfo(TypedDict):
    account_id: int
    name: NotRequired[str]
    email: NotRequired[str]
    username: NotRequired[str]


class _CodeOwnerInfo(TypedDict):
    account: _AccountInfo
    scorings: NotRequired[Dict[str, int]]


class _CodeOwnersForPathResult(TypedDict):
    change_id: str
    revision_id: str
    path: str
    code_owners: List[_CodeOwnerInfo]
    owned_by_all_users: NotRequired[bool]


class _CheckCodeOwnerResult(TypedDict):
    project: str
    branch: str
    path: str
    email: str
    is_code_owner: bool
    is_resolvable: bool
    can_read_ref: NotRequired[bool]
    can_see_change: NotRequired[bool]
    can_approve_change: NotRequired[bool]
    is_fallback_code_owner: NotRequired[bool]
    is_default_code_owner: NotRequired[bool]
    is_global_code_owner: NotRequired[bool]
    is_owned_by_all_users: NotRequired[bool]
    annotations: NotRequired[List[str]]


def _parse_path_status(
    raw: Optional[Dict[str, Any]],
) -> Optional[_PathCodeOwnerStatusInfo]:
    if raw is None:
        return None
    result: _PathCodeOwnerStatusInfo = {
        "path": raw.get("path", ""),
        "status": raw.get("status", ""),
    }
    reasons = raw.get("reasons")
    if reasons:
        result["reasons"] = reasons
    return result


def register(ctx: ExtensionContext) -> None:
    """Register code-owners MCP tools."""

    @ctx.mcp.tool()
    @requires_plugin("code-owners", ctx.plugin_registry)
    async def get_code_owner_status(
        change_id: str,
        limit: Optional[int] = None,
        start: Optional[int] = None,
        gerrit_base_url: Optional[str] = None,
    ) -> _CodeOwnerStatusResult:
        """Return code owner approval status for each file in a change.

        The status field for each path is one of:
          APPROVED   - at least one code owner has approved
          PENDING    - a code owner has been added as reviewer but not approved
          NOT_FOUND  - no code owner could be determined

        Pass limit and start for pagination when a change touches many files.
        """
        base_url = ctx.get_base_url(gerrit_base_url)
        url = f"{base_url}/changes/{quote(str(change_id))}/code_owners.status"
        params = []
        if limit is not None:
            params.append(f"-n={limit}")
        if start is not None:
            params.append(f"-S={start}")
        if params:
            url += "?" + "&".join(params)

        result_str = await ctx.run_curl([url], base_url)
        try:
            data = json.loads(result_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse Gerrit response: {result_str}") from e

        file_statuses: List[_FileCodeOwnerStatusInfo] = []
        for raw_file in data.get("fileCodeOwnerStatuses", []):
            entry: _FileCodeOwnerStatusInfo = {}
            change_type = raw_file.get("changeType")
            if change_type:
                entry["change_type"] = change_type
            old_status = _parse_path_status(raw_file.get("oldPathStatus"))
            if old_status is not None:
                entry["old_path_status"] = old_status
            new_status = _parse_path_status(raw_file.get("newPathStatus"))
            if new_status is not None:
                entry["new_path_status"] = new_status
            file_statuses.append(entry)

        result: _CodeOwnerStatusResult = {
            "change_id": change_id,
            "patch_set_number": data.get("patchSetNumber", 0),
            "file_code_owner_statuses": file_statuses,
        }
        if data.get("more"):
            result["more"] = True
        return result

    @ctx.mcp.tool()
    @requires_plugin("code-owners", ctx.plugin_registry)
    async def get_code_owners_for_path(
        change_id: str,
        path: str,
        revision_id: str = "current",
        limit: Optional[int] = None,
        gerrit_base_url: Optional[str] = None,
    ) -> _CodeOwnersForPathResult:
        """Return suggested code owners for a specific path in a change revision.

        The plugin filters out the change owner and service users, and ranks
        reviewers higher. Use this to find who should review a particular file.

        Pass revision_id to target a specific patch set (defaults to 'current').
        Pass limit to cap how many owners are returned.
        """
        base_url = ctx.get_base_url(gerrit_base_url)
        encoded_path = quote(path.lstrip("/"), safe="/")
        url = (
            f"{base_url}/changes/{quote(str(change_id))}"
            f"/revisions/{quote(str(revision_id))}"
            f"/code_owners/{encoded_path}"
        )
        if limit is not None:
            url += f"?-n={limit}"

        result_str = await ctx.run_curl([url], base_url)
        try:
            data = json.loads(result_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse Gerrit response: {result_str}") from e

        owners: List[_CodeOwnerInfo] = []
        for raw_owner in data.get("code_owners", []):
            raw_account = raw_owner.get("account", {})
            account: _AccountInfo = {"account_id": raw_account.get("_account_id", 0)}
            for field in ("name", "email", "username"):
                val = raw_account.get(field)
                if val:
                    account[field] = val  # type: ignore[literal-required]
            owner: _CodeOwnerInfo = {"account": account}
            scorings = raw_owner.get("scorings")
            if scorings:
                owner["scorings"] = scorings
            owners.append(owner)

        result: _CodeOwnersForPathResult = {
            "change_id": change_id,
            "revision_id": revision_id,
            "path": path,
            "code_owners": owners,
        }
        if data.get("owned_by_all_users"):
            result["owned_by_all_users"] = True
        return result

    @ctx.mcp.tool()
    @requires_plugin("code-owners", ctx.plugin_registry)
    async def check_code_owner(
        project: str,
        branch: str,
        path: str,
        email: str,
        change_id: Optional[str] = None,
        gerrit_base_url: Optional[str] = None,
    ) -> _CheckCodeOwnerResult:
        """Check whether a user (by email) is a code owner for a path in a branch.

        Returns detailed ownership information including whether the user can
        read the ref, see and approve the change (if change_id is provided),
        and which kind of code owner they are (global, default, fallback).

        Pass change_id to also check change-level permissions.
        """
        base_url = ctx.get_base_url(gerrit_base_url)
        encoded_project = quote(project, safe="")
        encoded_branch = quote(branch, safe="")
        url = (
            f"{base_url}/projects/{encoded_project}"
            f"/branches/{encoded_branch}"
            f"/code_owners.check"
            f"?--email={quote(email)}&--path={quote(path)}"
        )
        if change_id is not None:
            url += f"&--change={quote(str(change_id))}"

        result_str = await ctx.run_curl([url], base_url)
        try:
            data = json.loads(result_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse Gerrit response: {result_str}") from e

        result: _CheckCodeOwnerResult = {
            "project": project,
            "branch": branch,
            "path": path,
            "email": email,
            "is_code_owner": data.get("is_code_owner", False),
            "is_resolvable": data.get("is_resolvable", False),
        }
        for bool_field in (
            "can_read_ref",
            "can_see_change",
            "can_approve_change",
            "is_fallback_code_owner",
            "is_default_code_owner",
            "is_global_code_owner",
            "is_owned_by_all_users",
        ):
            val = data.get(bool_field)
            if val is not None:
                result[bool_field] = val  # type: ignore[literal-required]
        annotations = data.get("annotations")
        if annotations:
            result["annotations"] = annotations
        return result
