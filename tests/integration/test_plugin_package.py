import json
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def _load_json(relative_path: str) -> dict:
    path = PROJECT_ROOT / relative_path
    return json.loads(path.read_text())


def _skill_metadata(path: Path) -> dict[str, str]:
    content = path.read_text()
    assert content.startswith("---\n")
    _, front_matter, _ = content.split("---", 2)

    metadata = {}
    for line in front_matter.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key] = value.strip().strip('"')
    return metadata


# Console scripts the hooks run from the environment without `uv run`.
HOOK_SCRIPTS = ("gerrit-git-guard", "gerrit-session-context")


def _run_config_hook(
    tmp_path: Path,
    return_code: int,
    synced_scripts: tuple[str, ...] = HOOK_SCRIPTS,
    scripts_before: tuple[str, ...] = HOOK_SCRIPTS,
) -> subprocess.CompletedProcess:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    environment_bin = tmp_path / "plugin-data" / ".venv" / "bin"
    environment_bin.mkdir(parents=True)
    for script in scripts_before:
        (environment_bin / script).write_text("#!/bin/sh\n")
        (environment_bin / script).chmod(0o755)
    args_path = tmp_path / "uv-args"
    environment_path = tmp_path / "uv-environment"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/usr/bin/env bash\n"
        'printf \'%s\\n\' "$*" > "$FAKE_UV_ARGS_PATH"\n'
        'printf \'%s\\n\' "$UV_PROJECT_ENVIRONMENT" > "$FAKE_UV_ENVIRONMENT_PATH"\n'
        "printf '%s\\n' \"$FAKE_UV_OUTPUT\"\n"
        'mkdir -p "$UV_PROJECT_ENVIRONMENT/bin"\n'
        "for script in $FAKE_UV_SCRIPTS; do\n"
        '  printf "#!/bin/sh\\n" > "$UV_PROJECT_ENVIRONMENT/bin/$script"\n'
        '  chmod +x "$UV_PROJECT_ENVIRONMENT/bin/$script"\n'
        "done\n"
        'exit "$FAKE_UV_RETURN_CODE"\n'
    )
    fake_uv.chmod(0o755)

    plugin_data = tmp_path / "plugin-data"
    environment = os.environ.copy()
    environment.update(
        {
            "CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT),
            "CLAUDE_PLUGIN_DATA": str(plugin_data),
            "FAKE_UV_ARGS_PATH": str(args_path),
            "FAKE_UV_ENVIRONMENT_PATH": str(environment_path),
            "FAKE_UV_OUTPUT": "controlled uv output",
            "FAKE_UV_RETURN_CODE": str(return_code),
            "FAKE_UV_SCRIPTS": " ".join(synced_scripts),
            "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
        }
    )

    return subprocess.run(
        ["bash", str(PROJECT_ROOT / "hooks/check-config.sh")],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_git_guard_hook(
    tmp_path: Path, command: str, install_guard: bool = True
) -> subprocess.CompletedProcess:
    plugin_data = tmp_path / "plugin-data"
    guard_bin = plugin_data / ".venv" / "bin"
    guard_bin.mkdir(parents=True)
    calls_path = tmp_path / "guard-calls"
    if install_guard:
        guard = guard_bin / "gerrit-git-guard"
        guard.write_text(
            "#!/usr/bin/env bash\n"
            'cat > "$FAKE_GUARD_CALLS_PATH"\n'
            'echo \'{"hookSpecificOutput": {"permissionDecision": "deny"}}\'\n'
        )
        guard.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT),
            "CLAUDE_PLUGIN_DATA": str(plugin_data),
            "FAKE_GUARD_CALLS_PATH": str(calls_path),
        }
    )
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": "/"}
    return subprocess.run(
        ["bash", str(PROJECT_ROOT / "hooks/git-guard.sh")],
        input=json.dumps(payload),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_claude_plugin_manifest_identifies_gerrit():
    manifest = _load_json(".claude-plugin/plugin.json")

    assert manifest["name"] == "gerrit"
    assert manifest["license"] == "Apache-2.0"
    assert manifest["repository"] == "https://gerrit.googlesource.com/gerrit-mcp-server"


def test_claude_marketplace_installs_plugin_from_repository_root():
    marketplace = _load_json(".claude-plugin/marketplace.json")

    assert marketplace["name"] == "gerrit-mcp"
    assert marketplace["plugins"] == [{"name": "gerrit", "source": "./"}]


def test_claude_mcp_manifest_uses_plugin_data_for_environment():
    server = _load_json(".mcp.json")["mcpServers"]["gerrit"]

    assert server["command"] == "uv"
    assert server["args"] == [
        "run",
        "--directory",
        "${CLAUDE_PLUGIN_ROOT}",
        "gerrit-mcp-server",
    ]
    assert server["env"] == {"UV_PROJECT_ENVIRONMENT": "${CLAUDE_PLUGIN_DATA}/.venv"}


def test_claude_skills_have_required_agent_skill_metadata():
    skill_paths = sorted((PROJECT_ROOT / "skills").glob("*/SKILL.md"))

    assert skill_paths
    for skill_path in skill_paths:
        metadata = _skill_metadata(skill_path)
        assert metadata["name"]
        assert metadata["description"]


def test_config_hook_reports_valid_configuration(tmp_path):
    result = _run_config_hook(tmp_path, return_code=0)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "systemMessage" not in payload
    assert "tools are available" in payload["hookSpecificOutput"]["additionalContext"]


def test_config_hook_reports_missing_configuration(tmp_path):
    result = _run_config_hook(tmp_path, return_code=1)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "no config yet" in payload["systemMessage"]
    assert "/gerrit:setup" in payload["hookSpecificOutput"]["additionalContext"]


def test_config_hook_reports_invalid_configuration(tmp_path):
    result = _run_config_hook(tmp_path, return_code=2)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "config is invalid" in payload["systemMessage"]
    assert "controlled uv output" in payload["hookSpecificOutput"]["additionalContext"]


def test_config_hook_warns_when_git_guard_is_missing_after_sync(tmp_path):
    result = _run_config_hook(
        tmp_path, return_code=0, synced_scripts=(), scripts_before=()
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "not active" in payload["systemMessage"]
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert "tools are available" in context
    assert "gerrit-git-guard" in context
    assert "build-gerrit.sh" in context


def test_config_hook_asks_for_restart_after_environment_update(tmp_path):
    result = _run_config_hook(tmp_path, return_code=0, scripts_before=())

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "Restart the session" in payload["systemMessage"]
    assert "restart" in payload["hookSpecificOutput"]["additionalContext"]


def test_config_hook_passes_plugin_paths_to_uv(tmp_path):
    result = _run_config_hook(tmp_path, return_code=0)

    assert result.returncode == 0
    assert (tmp_path / "uv-args").read_text().strip() == (
        f"run --directory {PROJECT_ROOT} gerrit-check-config"
    )
    assert (tmp_path / "uv-environment").read_text().strip() == (
        f"{tmp_path / 'plugin-data'}/.venv"
    )


def _run_session_context_hook(
    tmp_path: Path, install: bool = True
) -> subprocess.CompletedProcess:
    plugin_data = tmp_path / "plugin-data"
    bin_dir = plugin_data / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    calls_path = tmp_path / "context-calls"
    if install:
        script = bin_dir / "gerrit-session-context"
        script.write_text(
            "#!/usr/bin/env bash\n"
            'cat > "$FAKE_CONTEXT_CALLS_PATH"\n'
            'echo \'{"hookSpecificOutput": {"additionalContext": "rules"}}\'\n'
        )
        script.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT),
            "CLAUDE_PLUGIN_DATA": str(plugin_data),
            "FAKE_CONTEXT_CALLS_PATH": str(calls_path),
        }
    )
    return subprocess.run(
        ["bash", str(PROJECT_ROOT / "hooks/session-context.sh")],
        input=json.dumps({"hook_event_name": "SessionStart", "cwd": "/repo"}),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_hooks_register_session_context_after_config_check():
    session_start = _load_json("hooks/hooks.json")["hooks"]["SessionStart"]

    commands = [hook["command"] for entry in session_start for hook in entry["hooks"]]
    assert commands == [
        "${CLAUDE_PLUGIN_ROOT}/hooks/check-config.sh",
        "${CLAUDE_PLUGIN_ROOT}/hooks/session-context.sh",
    ]


def test_session_context_entry_point_is_declared():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text()

    assert (
        'gerrit-session-context = "gerrit_mcp_server.session_context:main"' in pyproject
    )


def test_session_context_hook_passes_payload_to_script(tmp_path):
    result = _run_session_context_hook(tmp_path)

    assert result.returncode == 0
    assert (
        json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"] == "rules"
    )
    assert json.loads((tmp_path / "context-calls").read_text())["cwd"] == "/repo"


def test_session_context_hook_is_silent_when_environment_is_not_built(tmp_path):
    result = _run_session_context_hook(tmp_path, install=False)

    assert result.returncode == 0
    assert result.stdout == ""


def test_hooks_register_git_guard_for_bash():
    pre_tool_use = _load_json("hooks/hooks.json")["hooks"]["PreToolUse"]

    assert [entry["matcher"] for entry in pre_tool_use] == ["Bash"]
    assert pre_tool_use[0]["hooks"][0]["command"] == (
        "${CLAUDE_PLUGIN_ROOT}/hooks/git-guard.sh"
    )


def test_git_guard_entry_point_is_declared():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text()

    assert 'gerrit-git-guard = "gerrit_mcp_server.git_guard:main"' in pyproject


def test_git_guard_hook_passes_git_command_to_guard(tmp_path):
    result = _run_git_guard_hook(tmp_path, "git commit -n -m x")

    assert result.returncode == 0
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == (
        "deny"
    )
    passed = json.loads((tmp_path / "guard-calls").read_text())
    assert passed["tool_input"]["command"] == "git commit -n -m x"


def test_git_guard_hook_skips_commands_without_git(tmp_path):
    result = _run_git_guard_hook(tmp_path, "ls -la")

    assert result.returncode == 0
    assert result.stdout == ""
    assert not (tmp_path / "guard-calls").exists()


def test_git_guard_hook_allows_when_environment_is_not_built(tmp_path):
    result = _run_git_guard_hook(tmp_path, "git commit -n -m x", install_guard=False)

    assert result.returncode == 0
    assert result.stdout == ""
