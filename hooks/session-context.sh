#!/usr/bin/env bash
# SessionStart hook: in a Gerrit repository, tell the model the chain rules.
#
# The text comes from the gerrit-session-context console script
# (gerrit_mcp_server/session_context.py), which prints a SessionStart
# additionalContext as JSON in a Gerrit repository, nothing elsewhere, and
# always exits 0.
#
# Like git-guard.sh, the script runs straight from the environment the MCP
# server uses (${CLAUDE_PLUGIN_DATA}/.venv) without `uv run`, so there is no
# sync and no network at session start; an environment that is not built yet
# adds no context.

set -uo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
ENV_PATH="${CLAUDE_PLUGIN_DATA:-$PLUGIN_ROOT}/.venv"
CONTEXT="$ENV_PATH/bin/gerrit-session-context"

payload=$(cat) || exit 0
[ -x "$CONTEXT" ] || exit 0

printf '%s' "$payload" | "$CONTEXT" 2>/dev/null || true
exit 0
