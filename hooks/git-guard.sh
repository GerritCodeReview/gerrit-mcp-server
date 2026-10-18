#!/usr/bin/env bash
# PreToolUse hook for the Bash tool: guard git commands in Gerrit repositories.
#
# The decision comes from the gerrit-git-guard console script
# (gerrit_mcp_server/git_guard.py), which prints a PreToolUse permission
# decision as JSON ("deny" or "ask"), a note for the model without a
# decision, or nothing, and always exits 0.
#
# This wrapper keeps the hook cheap and fail-open:
#   - a command that does not mention git never starts Python;
#   - the console script runs straight from the environment the MCP server
#     uses (${CLAUDE_PLUGIN_DATA}/.venv, see .mcp.json), without `uv run`, so
#     there is no sync and no network on the hot path;
#   - an environment that is not built yet, or a guard that fails, allows the
#     command. The SessionStart hook (check-config.sh) reports a missing
#     environment to the user.

set -uo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
ENV_PATH="${CLAUDE_PLUGIN_DATA:-$PLUGIN_ROOT}/.venv"
GUARD="$ENV_PATH/bin/gerrit-git-guard"

payload=$(cat) || exit 0
case "$payload" in
  *git*) ;;
  *) exit 0 ;;
esac
[ -x "$GUARD" ] || exit 0

printf '%s' "$payload" | "$GUARD" 2>/dev/null || true
exit 0
