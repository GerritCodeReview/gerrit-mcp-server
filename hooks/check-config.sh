#!/usr/bin/env bash
# SessionStart hook: verify the Gerrit MCP server environment and config.
#
# Why this is a script and not an inline command:
#   SessionStart stdout goes to the MODEL's context, not the user's terminal, so
#   a bare `echo` on failure is invisible to the human AND a `|| echo` forces the
#   hook to "succeed". We instead emit JSON: `systemMessage` (shown to the user)
#   + `additionalContext` (tells the model what to do). See the Claude Code
#   hooks docs.
#
# Exit code contract of `gerrit-check-config` (gerrit_mcp_server/main.py):
#   0 = config valid; 1 = config file missing; 2 = config invalid.
# A `uv run` spawn failure (env not built / package missing) surfaces as some
# other non-zero code and is treated as an ENV failure.

set -uo pipefail

# pyproject.toml (which defines the gerrit-check-config console script) lives at
# the repo root = ${CLAUDE_PLUGIN_ROOT}, so `uv run --directory $PLUGIN_ROOT` is
# correct here. The fallback (hooks/..) resolves to the repo root for standalone
# runs. ENV_PATH mirrors .mcp.json so the build target and MCP server agree.
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
ENV_PATH="${CLAUDE_PLUGIN_DATA:-$PLUGIN_ROOT}/.venv"

out=$(UV_PROJECT_ENVIRONMENT="$ENV_PATH" \
      uv run --directory "$PLUGIN_ROOT" gerrit-check-config 2>&1)
rc=$?

# Emit a JSON object with optional systemMessage + additionalContext.
# Args: <systemMessage-or-empty> <additionalContext>
emit() {
  if ! command -v python3 &>/dev/null; then
    echo '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"python3 not found; Gerrit MCP server config check hook could not emit status."}}'
    return
  fi
  python3 - "$1" "$2" <<'PY'
import json, sys
sys_msg, ctx = sys.argv[1], sys.argv[2]
obj = {"hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": ctx,
}}
if sys_msg:
    obj["systemMessage"] = sys_msg
print(json.dumps(obj))
PY
}

case "$rc" in
  0)
    emit "" "Gerrit MCP server config check passed; the gerrit MCP tools are available."
    ;;
  1)
    # Config file missing — interactive setup needed. /gerrit:setup is
    # disable-model-invocation (skills/setup/SKILL.md), so the model must ask
    # the USER to run it.
    emit \
      "⚠️  Gerrit MCP server has no config yet. Run /gerrit:setup to configure it." \
      "The gerrit MCP server has NO configuration file yet (gerrit-check-config exited 1). This is the normal first-run state, NOT a broken install. Do NOT call gerrit MCP tools. Tell the user to run the /gerrit:setup slash command (it is interactive and cannot be invoked by the model). Do not offer to create the config yourself."
    ;;
  2)
    # Config present but invalid (bad JSON / URL mismatch). Same: user runs setup.
    emit \
      "⚠️  Gerrit MCP server config is invalid. Run /gerrit:setup to fix it." \
      "The gerrit MCP server config is INVALID (gerrit-check-config exited 2). Do NOT call gerrit MCP tools. Tell the user to run the /gerrit:setup slash command to repair it. Error detail: ${out}"
    ;;
  *)
    # Env failure: uv/venv not built, package not installed, etc. This is the
    # non-interactive case, so the model SHOULD offer to run the build itself.
    rebuild="UV_PROJECT_ENVIRONMENT=\"$ENV_PATH\" bash \"$PLUGIN_ROOT/build-gerrit.sh\""
    echo "gerrit-check-config env failure (rc=$rc): $out" >&2
    emit \
      "⚠️  Gerrit MCP server environment is not built. Claude can rebuild it for you." \
      "The gerrit MCP server Python environment is broken or not built (gerrit-check-config could not be spawned, rc=${rc}). Do NOT call gerrit MCP tools until this is fixed. OFFER to run this exact command for the user (it is non-interactive), then re-run the check: ${rebuild}"
    ;;
esac

# Always exit 0: SessionStart cannot block, and the JSON above carries the
# signal. A non-zero exit here would only add a redundant transcript error.
exit 0
