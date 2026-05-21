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
