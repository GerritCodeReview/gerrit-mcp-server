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


def _run_config_hook(
    tmp_path: Path,
    return_code: int,
    *,
    codex_environment: bool = False,
) -> subprocess.CompletedProcess:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    args_path = tmp_path / "uv-args"
    environment_path = tmp_path / "uv-environment"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" > \"$FAKE_UV_ARGS_PATH\"\n"
        "printf '%s\\n' \"$UV_PROJECT_ENVIRONMENT\" > \"$FAKE_UV_ENVIRONMENT_PATH\"\n"
        "printf '%s\\n' \"$FAKE_UV_OUTPUT\"\n"
        "exit \"$FAKE_UV_RETURN_CODE\"\n"
    )
    fake_uv.chmod(0o755)

    plugin_data = tmp_path / "plugin-data"
    environment = os.environ.copy()
    environment.pop("CLAUDE_PLUGIN_ROOT", None)
    environment.pop("CLAUDE_PLUGIN_DATA", None)
    environment.pop("PLUGIN_ROOT", None)
    environment.pop("PLUGIN_DATA", None)
    environment.update(
        {
            "PLUGIN_ROOT" if codex_environment else "CLAUDE_PLUGIN_ROOT": str(
                PROJECT_ROOT
            ),
            "PLUGIN_DATA" if codex_environment else "CLAUDE_PLUGIN_DATA": str(
                plugin_data
            ),
            "FAKE_UV_ARGS_PATH": str(args_path),
            "FAKE_UV_ENVIRONMENT_PATH": str(environment_path),
            "FAKE_UV_OUTPUT": "controlled uv output",
            "FAKE_UV_RETURN_CODE": str(return_code),
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
    assert server["env"] == {
        "UV_PROJECT_ENVIRONMENT": "${CLAUDE_PLUGIN_DATA}/.venv"
    }


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


def test_config_hook_passes_plugin_paths_to_uv(tmp_path):
    result = _run_config_hook(tmp_path, return_code=0)

    assert result.returncode == 0
    assert (tmp_path / "uv-args").read_text().strip() == (
        f"run --directory {PROJECT_ROOT} gerrit-check-config"
    )
    assert (tmp_path / "uv-environment").read_text().strip() == (
        f"{tmp_path / 'plugin-data'}/.venv"
    )


def test_codex_plugin_manifest_identifies_gerrit():
    manifest = _load_json("plugin.json")

    assert manifest["$schema"] == (
        "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    )
    assert manifest["name"] == "gerrit"
    assert manifest["version"]
    assert manifest["license"] == "Apache-2.0"


def test_codex_mcp_manifest_uses_codex_plugin_runtime():
    server = _load_json("mcp.json")["mcpServers"]["gerrit"]

    assert server["type"] == "stdio"
    assert server["command"] == "uv"
    assert server["args"] == [
        "run",
        "--directory",
        "${PLUGIN_ROOT}",
        "gerrit-mcp-server",
    ]
    assert server["env"] == {"UV_PROJECT_ENVIRONMENT": "${PLUGIN_DATA}/.venv"}


def test_codex_setup_skill_disables_implicit_invocation():
    metadata = (PROJECT_ROOT / "skills/setup/agents/openai.yaml").read_text()

    assert "allow_implicit_invocation: false" in metadata


def test_config_hook_accepts_codex_plugin_paths(tmp_path):
    result = _run_config_hook(tmp_path, return_code=0, codex_environment=True)

    assert result.returncode == 0
    assert (tmp_path / "uv-args").read_text().strip() == (
        f"run --directory {PROJECT_ROOT} gerrit-check-config"
    )
    assert (tmp_path / "uv-environment").read_text().strip() == (
        f"{tmp_path / 'plugin-data'}/.venv"
    )
