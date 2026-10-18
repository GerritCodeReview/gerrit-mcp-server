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
rebuild="UV_PROJECT_ENVIRONMENT=\"$ENV_PATH\" bash \"$PLUGIN_ROOT/build-gerrit.sh\""

# Console scripts the other hooks run straight from the environment, without
# `uv run`: when one is missing, that hook silently does nothing. An
# environment built by an older release lacks the newer ones until the sync
# below.
HOOK_SCRIPTS=(gerrit-git-guard gerrit-session-context)

missing_hook_scripts() {
  local script
  for script in "${HOOK_SCRIPTS[@]}"; do
    [ -x "$ENV_PATH/bin/$script" ] || printf '%s ' "$script"
  done
}

missing_before=$(missing_hook_scripts)
out=$(UV_PROJECT_ENVIRONMENT="$ENV_PATH" \
      uv run --directory "$PLUGIN_ROOT" gerrit-check-config 2>&1)
rc=$?

hook_message=""
hook_context=""
missing=$(missing_hook_scripts)
if [ -n "$missing" ]; then
  hook_message="⚠️  Gerrit git guard or session context not active: ${missing% } missing from the plugin environment. Claude can rebuild it."
  hook_context="The console scripts ${missing% } are missing from $ENV_PATH even after the sync, so the hooks that run them do nothing: gerrit-git-guard is the git guard, gerrit-session-context adds the chain rules at session start. OFFER to run this exact command for the user (it is non-interactive), then ask them to restart the session: ${rebuild}"
else
  case " $missing_before " in
    *" gerrit-session-context "*)
      # The session context hook runs alongside this one, so it most likely
      # found no script. The guard checks on every command and needs nothing.
      hook_message="Gerrit plugin environment updated. Restart the session to get the chain rules context."
      hook_context="The Gerrit plugin environment was updated at session start, so this session may lack the Gerrit chain rules context. Tell the user to restart the session."
      ;;
  esac
fi

# Emit a JSON object with optional systemMessage + additionalContext, adding
# the hook script warnings.
# Args: <systemMessage-or-empty> <additionalContext>
emit() {
  if ! command -v python3 &>/dev/null; then
    echo '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"python3 not found; Gerrit MCP server config check hook could not emit status."}}'
    return
  fi
  python3 - "$1" "$2" "$hook_message" "$hook_context" <<'PY'
import json, sys
sys_msg = "\n".join(m for m in sys.argv[1::2] if m)
ctx = " ".join(c for c in sys.argv[2::2] if c)
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
    # The rebuild also restores the hook scripts, so no separate warning.
    hook_message=""
    hook_context=""
    echo "gerrit-check-config env failure (rc=$rc): $out" >&2
    emit \
      "⚠️  Gerrit MCP server environment is not built. Claude can rebuild it for you." \
      "The gerrit MCP server Python environment is broken or not built (gerrit-check-config could not be spawned, rc=${rc}). Do NOT call gerrit MCP tools until this is fixed. OFFER to run this exact command for the user (it is non-interactive), then re-run the check: ${rebuild}"
    ;;
esac

# Always exit 0: SessionStart cannot block, and the JSON above carries the
# signal. A non-zero exit here would only add a redundant transcript error.
exit 0
