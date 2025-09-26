# Example Use Cases

Here are a few examples of how you can use the Gerrit MCP Server with a language model:

| Category          | Natural Language Query                                                                                              | Corresponding Tool(s)                                 |
| :---------------- | :------------------------------------------------------------------------------------------------------------------ | :---------------------------------------------------- |
| **Find recent work** | "Show me the last 5 CLs I submitted."                                                                               | `query_changes`                                       |
|                   | "What are the open CLs for the 'main' branch in the 'my-project' project?"                                      | `query_changes`                                       |
|                   | "Find CLs merged between 2025-09-01 and 2025-09-05 containing 'bug fix'."                                         | `query_changes_by_date_and_filters`                   |
| **Get CL details**  | "What are the details for CL 12345?"                                                                              | `get_change_details`                                  |
|                   | "Who are the reviewers on CL 67890?"                                                                              | `get_change_details`                                  |
|                   | "Get the commit message for change 54321."                                                                        | `get_commit_message`                                  |
|                   | "List the files changed in CL 12345."                                                                             | `list_change_files`                                   |
|                   | "Show me the diff for 'src/main.py' in CL 12345."                                                               | `get_file_diff`                                       |
|                   | "What bugs are linked to CL 12345?"                                                                               | `get_bugs_from_cl`                                    |
| **Manage Reviews**  | "Add user@example.com as a reviewer to CL 12345."                                                                 | `add_reviewer`                                        |
|                   | "Set CL 12345 to ready for review."                                                                               | `set_ready_for_review`                                |
|                   | "Mark CL 67890 as work in progress."                                                                              | `set_work_in_progress`                                |
|                   | "Abandon CL 54321."                                                                                               | `abandon_change`                                      |
|                   | "Suggest reviewers for CL 12345 who know about the 'auth' module."                                                | `suggest_reviewers`                                   |
| **Review Helper**   | "List the comments on CL 12345."                                                                                  | `list_change_comments`                                |
|                   | "Post a comment on CL 12345, file 'utils.py', line 20: 'Add a test for this case.'"                               | `post_review_comment`                                 |
| **Advanced**        | "Revert CL 12345 with the message 'Broke the build'."                                                             | `revert_change`                                       |
|                   | "What other changes would be submitted with CL 67890?"                                                            | `changes_submitted_together`                          |
|                   | "Create a new change in project 'test-project', branch 'dev', with subject 'Test new feature'."                   | `create_change`                                       |

## Data Analysis Use Cases

These scenarios often involve chaining commands, using specific query syntax, and potentially combining the output with other tools or manual analysis.

| Category                          | Natural Language Query                                                                                                        | Corresponding Tool(s)                                 |
| :-------------------------------- | :---------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------- |
| **Track a feature**               | "Find all CLs with the topic 'feature-x-implementation'."                                                                    | `query_changes`                                       |
|                                   | "List all files modified in CLs related to topic 'performance-improvements'."                                               | `query_changes` -> `list_change_files` (for each CL)    |
| **Analyze code churn**            | "Show me all CLs by 'user@example.com' in the 'analytics' project merged last week."                                        | `query_changes`                                       |
|                                   | "Get the details for all changes in topic 'refactor-backend' and list the modified files and their change sizes."             | `query_changes` -> `list_change_files` (for each CL)    |
| **Identify key contributors**     | "Find the top 5 authors with the most merged CLs in the 'data-pipeline' project this month." (Requires aggregation)       | `query_changes` -> Manual/External Aggregation        |
| **Audit changes**                 | "List all CLs merged to the 'production' branch between '2025-09-01' and '2025-09-05'."                                      | `query_changes_by_date_and_filters`                   |
|                                   | "Get the commit messages for all changes in CL set 12345, 12346, and 12347."                                                | `get_commit_message` (multiple calls)                 |
| **Correlate bugs with changes**   | "Find all CLs that fix bugs in hotlist 'critical-fixes'." (Requires external bug tool to get IDs)                         | External Tool -> `query_changes`                      |
|                                   | "For CLs 12300 to 12310, extract all mentioned bug IDs."                                                                    | `get_bugs_from_cl` (multiple calls)                   |