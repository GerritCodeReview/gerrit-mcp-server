import io
import json
import subprocess
from pathlib import Path

import pytest

from gerrit_mcp_server import session_context


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)


@pytest.fixture
def plain_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("GERRIT_CONFIG_PATH", str(tmp_path / "no-config.json"))
    repo = tmp_path / "plain"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "master")
    return repo


@pytest.fixture
def gerrit_repo(plain_repo):
    (plain_repo / ".gitreview").write_text("[gerrit]\nhost=gerrit.example.com\n")
    hook = plain_repo / ".git" / "hooks" / "commit-msg"
    hook.write_text("#!/bin/sh\n# adds a Change-Id\n")
    hook.chmod(0o755)
    return plain_repo


def _run_main(monkeypatch, capsys, payload: str) -> str:
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    with pytest.raises(SystemExit) as exit_info:
        session_context.main()
    assert exit_info.value.code == 0
    return capsys.readouterr().out


def test_says_nothing_outside_gerrit(plain_repo, tmp_path):
    assert session_context.context_for(plain_repo) is None
    assert session_context.context_for(tmp_path / "missing") is None


def test_names_the_skills_and_rules_in_a_gerrit_repo(gerrit_repo):
    text = session_context.context_for(gerrit_repo)

    for needle in (
        "gerrit-workflow",
        "stack-planner",
        "gerrit-review",
        "refs/for/<branch>",
        "--no-verify",
    ):
        assert needle in text
    assert "not installed" not in text
    assert "conventions" not in text


def test_asks_for_the_hook_when_it_is_missing(gerrit_repo):
    (gerrit_repo / ".git" / "hooks" / "commit-msg").unlink()

    assert "The commit-msg hook is not installed" in session_context.context_for(
        gerrit_repo
    )


def test_points_at_the_documented_conventions(gerrit_repo):
    (gerrit_repo / "AGENTS.md").write_text("# Conventions\n")
    (gerrit_repo / "CONTRIBUTING.md").write_text("# Contributing\n")
    sub = gerrit_repo / "src"
    sub.mkdir()

    text = session_context.context_for(sub)

    assert text.splitlines()[-1] == (
        "Commit and review-comment conventions of this repository: "
        "AGENTS.md, CONTRIBUTING.md."
    )


def test_main_prints_session_start_context(gerrit_repo, monkeypatch, capsys):
    out = _run_main(monkeypatch, capsys, json.dumps({"cwd": str(gerrit_repo)}))

    output = json.loads(out)["hookSpecificOutput"]
    assert output["hookEventName"] == "SessionStart"
    assert "stack-planner" in output["additionalContext"]


@pytest.mark.parametrize("payload", ["not json", "{}", '{"cwd": "/nonexistent/dir"}'])
def test_main_is_silent_when_it_cannot_tell(payload, monkeypatch, capsys):
    assert _run_main(monkeypatch, capsys, payload) == ""


def test_main_is_silent_outside_gerrit(plain_repo, monkeypatch, capsys):
    assert _run_main(monkeypatch, capsys, json.dumps({"cwd": str(plain_repo)})) == ""
