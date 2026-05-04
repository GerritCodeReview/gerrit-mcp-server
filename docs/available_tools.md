# Available Tools

This document lists the tools available in the Gerrit MCP Server, extracted from
`gerrit_mcp_server/main.py`.

## Tools

- **query_changes**: Searches for CLs matching a given query string.
- **query_changes_by_date_and_filters**: Searches for Gerrit changes within a
  specified date range, optionally filtered by project, a substring in the
  commit message, and change status.
- **get_change_details**: Retrieves a comprehensive summary of a single CL.
- **get_commit_message**: Gets the commit message of a change from the current
  patch set.
- **list_change_files**: Lists all files modified in the most recent patch set
  of a CL.
- **get_file_diff**: Retrieves the diff for a single, specified file within a
  CL.
- **list_change_comments**: list_change_comments is useful for reviewing
  feedback, reading comments on a change, analyzing comments, and responding to
  comments.
- **add_reviewer**: Adds a user or a group to a CL as either a reviewer or a CC.
- **set_ready_for_review**: Sets a CL as ready for review.
- **set_work_in_progress**: Sets a CL as work-in-progress.
- **revert_change**: Reverts a single change, creating a new CL.
- **revert_submission**: Reverts an entire submission, creating one or more new
  CLs.
- **create_change**: Creates a new change in Gerrit.
- **set_topic**: Sets the topic of a change. An empty string deletes the topic.
- **changes_submitted_together**: Computes and lists all changes that would be
  submitted together with a given CL.
- **get_related_changes**: Returns the relation chain for a change — the queried
  change, its git-parent ancestors, and any descendants sharing the chain — with
  per-entry merge status and patch-set numbers, for diagnosing implicit
  git-parent dependencies.
- **get_revision_commit**: Returns the full commit object for a change's
  revision — commit SHA, parent SHA(s), author, committer, subject, and the
  verbatim message — so an agent can retrieve parent SHAs (e.g. to check whether
  each parent is merged via `query_changes("commit:<sha>")`).
- **get_git_parent_changes**: Returns the immediate git-parent changes of a CL,
  using the `parentof:` query operator to find changes whose commit is a direct
  parent of the given change's commit. Only immediate parents are returned, not
  grandparents or higher ancestors.
- **suggest_reviewers**: Suggests reviewers for a change based on a query.
- **abandon_change**: Abandons a change.
- **get_most_recent_cl**: Gets the most recent CL for a user.
- **get_bugs_from_cl**: Extracts bug IDs from the commit message of a CL.
- **post_review_comment**: Posts a review comment on a specific line of a file
  in a CL.

## Extension Tools

These tools are provided by bundled [extensions](extensions.md) rather than the
core server. They are registered at startup and become available automatically.

### Task plugin (`gerrit_mcp_server_task`)

Requires the [`task`](https://gerrit.googlesource.com/plugins/task/) plugin on
the target Gerrit host. Both tools auto-route to a configured host that has the
plugin installed.

- **get_task_tree**: Returns the full task tree attached to a change (pruned to
  applicable tasks via `task--applicable`). Pass `task_only` to scope to a
  single root task.
- **get_actionable_tasks**: Walks the task tree depth-first and returns only the
  actionable tasks — those with status `READY` or `FAIL`. `WAITING` nodes are
  descended into but not returned. Pass `task_only` to scope to a single root
  task.

### Depends-on plugin (`gerrit_mcp_server_depends_on`)

Requires the [`depends-on`](https://gerrit.googlesource.com/plugins/depends-on/)
plugin on the target Gerrit host. Both tools auto-route to a configured host
that has the plugin installed.

- **get_depends_on**: Returns the Depends-on plugin dependencies declared on a
  change. Each item is either resolved (has a `change_number`) or unresolved
  (has an unresolved I-hash that couldn't be matched to a change in the
  configured deliverables). Uses the `--depends-on--all` DynamicOption to
  include all dependencies regardless of deliverable scope.
- **get_dependents**: Returns changes that explicitly declare `Depends-on:` on
  the given change, via the `independson:<change_id>` query operator registered
  by the plugin.
