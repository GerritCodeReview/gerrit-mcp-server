# Best Practices

Here are some best practices and tips for using the Gerrit MCP server effectively.

## Use Natural Language

The server's tools are designed to be called by a language model. You don't need to remember the exact tool names or parameters. Just state what you want to do in plain English.

*   **Instead of:** `gerrit.query_changes(query="owner:me status:open")`
*   **Prefer:** "Show me my open CLs"

*   **Instead of:** `gerrit.get_change_details(change_id="12345")`
*   **Prefer:** "What are the details for CL 12345?"

## Be Specific to Reduce Noise

Gerrit repositories can be very busy. The more specific your query, the more relevant the results will be.

*   **Good:** "Find CLs in the 'fuchsia' project"
*   **Better:** "Search for open CLs in the 'fuchsia' project with the word 'refactor'"
*   **Best:** "Show me open CLs by `user@example.com` in the `zircon` project from the last week"

## Chaining Commands

You can ask the model to perform a series of actions.

*   "Find the most recent CL by `user@example.com`."
*   (After the result is returned) "Now, list the files in that CL."
*   (After the file list is returned) "Show me the diff for `src/main.py`."

## Use Different Gerrit Instances

If your `gerrit_config.json` is configured with multiple hosts, you can specify which one to use in your prompt.

*   "On the **AOSP gerrit**, find CLs related to 'kernel'."
*   "Search for CLs on the **internal server** by `user@google.com`."

If you don't specify a host, the `default_gerrit_base_url` from your configuration will be used.
