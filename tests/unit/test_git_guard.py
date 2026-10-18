import io
import json
import os
import subprocess
from pathlib import Path

import pytest

from gerrit_mcp_server import git_guard

# Stands in for Gerrit's commit-msg hook: adds a Change-Id unless one is there.
FAKE_COMMIT_MSG_HOOK = """#!/bin/sh
grep -q '^Change-Id:' "$1" && exit 0
printf '\\nChange-Id: I%s\\n' "$(git hash-object "$1")" >> "$1"
"""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _install_hook(repo: Path) -> None:
    hook = repo / ".git" / "hooks" / "commit-msg"
    hook.write_text(FAKE_COMMIT_MSG_HOOK)
    hook.chmod(0o755)


@pytest.fixture
def plain_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("GERRIT_CONFIG_PATH", str(tmp_path / "no-config.json"))
    repo = tmp_path / "plain"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "master")
    _git(repo, "config", "user.email", "author@example.com")
    _git(repo, "config", "user.name", "Author")
    (repo / "a.txt").write_text("a\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "Base")
    return repo


@pytest.fixture
def gerrit_repo(plain_repo):
    (plain_repo / ".gitreview").write_text("[gerrit]\nhost=gerrit.example.com\n")
    _install_hook(plain_repo)
    _git(plain_repo, "commit", "-q", "--amend", "--no-edit")
    return plain_repo


def _decide(command: str, cwd: Path) -> dict | None:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
    return git_guard.evaluate(payload).to_hook_output()


def _verdict(command: str, cwd: Path) -> str | None:
    output = _decide(command, cwd)
    return output["hookSpecificOutput"]["permissionDecision"] if output else None


def test_allows_plain_commit_in_gerrit_repo(gerrit_repo):
    assert _verdict("git commit -m 'Add b'", gerrit_repo) is None


def test_ignores_repository_not_on_gerrit(plain_repo):
    assert _verdict("git commit --no-verify -m x", plain_repo) is None


@pytest.mark.parametrize(
    "command",
    [
        "git commit --no-verify -m 'Add b'",
        "git commit -n -m 'Add b'",
        "git commit -an -m 'Add b'",
    ],
)
def test_denies_skipping_the_hook(gerrit_repo, command):
    output = _decide(command, gerrit_repo)

    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "--no-verify" in output["hookSpecificOutput"]["permissionDecisionReason"]
    assert (
        "Nothing in this command ran."
        in output["hookSpecificOutput"]["permissionDecisionReason"]
    )


def test_reads_n_inside_a_message_as_text(gerrit_repo):
    assert _verdict("git commit -m'-n is fine here'", gerrit_repo) is None


def test_denies_commit_without_hook(gerrit_repo):
    (gerrit_repo / ".git" / "hooks" / "commit-msg").unlink()

    output = _decide("git commit -m 'Add b'", gerrit_repo)

    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "commit-msg hook" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_denies_hand_written_change_id_in_message(gerrit_repo):
    command = "git commit -m 'Add b' -m 'Change-Id: I1234567890abcdef'"

    assert _verdict(command, gerrit_repo) == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'Add b' --trailer 'Change-Id: I1234567890abcdef'",
        "git commit -m 'Add b' --trailer=Change-Id=I1234567890abcdef",
        "git commit --amend --no-edit --trai 'change-id: I1234567890abcdef'",
    ],
)
def test_denies_hand_written_change_id_in_trailer(gerrit_repo, command):
    assert _verdict(command, gerrit_repo) == "deny"


def test_allows_other_trailers(gerrit_repo):
    command = "git commit -m 'Add b' --trailer 'Signed-off-by: A <a@example.com>'"

    assert _verdict(command, gerrit_repo) is None


def test_denies_hand_written_change_id_in_heredoc(gerrit_repo):
    command = (
        "git commit -m \"$(cat <<'EOF'\n"
        "Add b\n\nIt's needed.\n\nChange-Id: I1234567890abcdef\n"
        "EOF\n"
        ')"'
    )

    assert _verdict(command, gerrit_repo) == "deny"


def test_allows_heredoc_message_with_apostrophe(gerrit_repo):
    command = (
        "git commit -m \"$(cat <<'EOF'\n"
        "Add b\n\nIt's needed because the old one isn't.\n"
        "EOF\n"
        ')"'
    )

    assert _verdict(command, gerrit_repo) is None


def test_denies_hand_written_change_id_in_message_file(gerrit_repo):
    (gerrit_repo / "msg").write_text("Add b\n\nChange-Id: I1234567890abcdef\n")

    assert _verdict("git commit -F msg", gerrit_repo) == "deny"


def test_denies_amend_with_message(gerrit_repo):
    output = _decide("git commit --amend -m 'Reword'", gerrit_repo)

    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "--no-edit" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_allows_amend_no_edit(gerrit_repo):
    assert _verdict("git commit --amend --no-edit", gerrit_repo) is None


def test_allows_amend_from_file_that_keeps_head_change_id(gerrit_repo):
    message = _git(gerrit_repo, "log", "-1", "--format=%B")
    (gerrit_repo / "msg").write_text(message.replace("Base", "Base, reworded"))

    assert _verdict("git commit --amend -F msg", gerrit_repo) is None


def test_denies_amend_from_file_without_change_id(gerrit_repo):
    (gerrit_repo / "msg").write_text("Base, reworded\n")

    output = _decide("git commit --amend -F msg", gerrit_repo)

    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert (
        "git reset --soft HEAD~1"
        in (output["hookSpecificOutput"]["permissionDecisionReason"])
    )


def test_allows_amend_from_file_it_cannot_check_yet(gerrit_repo):
    command = "git log -1 --format=%B > msg && git commit --amend -F msg"

    assert _verdict(command, gerrit_repo) is None
    assert _verdict("git commit --amend -F -", gerrit_repo) is None


def test_allows_amend_that_reapplies_another_change_id(gerrit_repo):
    (gerrit_repo / "msg").write_text("Base\n\nChange-Id: I1234567890abcdef\n")

    assert _verdict("git commit --amend -F msg", gerrit_repo) is None


def _amend_with_heredoc(change_id: str) -> str:
    return (
        "cat > msg <<'EOF'\nBase, reworded\n\n"
        f"Change-Id: {change_id}\nEOF\ngit commit --amend -F msg"
    )


def test_notes_amend_heredoc_that_types_head_change_id(gerrit_repo):
    head = _git(
        gerrit_repo, "log", "-1", "--format=%(trailers:key=Change-Id,valueonly)"
    )

    output = _decide(_amend_with_heredoc(head), gerrit_repo)

    assert "permissionDecision" not in output["hookSpecificOutput"]
    assert output["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "git log -1 --format=%B" in output["hookSpecificOutput"]["additionalContext"]


def test_denies_amend_heredoc_that_types_another_change_id(gerrit_repo):
    output = _decide(_amend_with_heredoc("I1234567890abcdef"), gerrit_repo)

    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    reason = output["hookSpecificOutput"]["permissionDecisionReason"]
    assert "differs from HEAD's" in reason
    assert "show both ids to the user" in reason


def test_checks_only_the_file_when_heredoc_has_no_change_id(gerrit_repo):
    (gerrit_repo / "msg").write_text("Base, reworded\n")
    command = "cat > notes <<'EOF'\nno trailer here\nEOF\ngit commit --amend -F msg"

    assert _verdict(command, gerrit_repo) == "deny"
    (gerrit_repo / "msg").write_text(_git(gerrit_repo, "log", "-1", "--format=%B"))
    assert _decide(command, gerrit_repo) is None


def test_allows_typed_change_id_when_head_has_none(plain_repo):
    (plain_repo / ".gitreview").write_text("[gerrit]\nhost=gerrit.example.com\n")
    _install_hook(plain_repo)

    assert _decide(_amend_with_heredoc("I1234567890abcdef"), plain_repo) is None


def test_allows_typed_change_id_without_head(gerrit_repo, tmp_path):
    repo = tmp_path / "unborn"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "master")
    (repo / ".gitreview").write_text("[gerrit]\nhost=gerrit.example.com\n")
    _install_hook(repo)

    assert _verdict("git commit -n -m x", repo) == "deny"  # still guarded
    assert _decide(_amend_with_heredoc("I1234567890abcdef"), repo) is None


# Records each call; answers a signing request with a fake signature.
SPY_GPG = """#!/bin/sh
echo "$*" >> "$SPY_GPG_CALLS"
case "$*" in
  *-bsau*) cat > /dev/null; echo '[GNUPG:] SIG_CREATED ' >&2
    printf -- '-----BEGIN PGP SIGNATURE-----\\n\\nZmFrZQ==\\n'
    printf -- '-----END PGP SIGNATURE-----\\n' ;;
esac
"""


def _commit_signed_with_spy(repo: Path, tmp_path: Path, monkeypatch) -> Path:
    """Commits a signed commit; the repo then verifies signatures on git log."""
    spy = tmp_path / "spy-gpg"
    spy.write_text(SPY_GPG)
    spy.chmod(0o755)
    calls = tmp_path / "gpg-calls"
    monkeypatch.setenv("SPY_GPG_CALLS", str(calls))
    _git(repo, "config", "gpg.program", str(spy))
    _git(repo, "config", "user.signingkey", "key")
    _git(repo, "commit", "-q", "-S", "--allow-empty", "-m", "Signed")
    _git(repo, "config", "log.showSignature", "true")
    calls.unlink()
    return calls


def test_reads_head_without_running_signature_program(
    gerrit_repo, tmp_path, monkeypatch
):
    calls = _commit_signed_with_spy(gerrit_repo, tmp_path, monkeypatch)
    head = _git(
        gerrit_repo,
        "log",
        "-1",
        "--no-show-signature",
        "--format=%(trailers:key=Change-Id,valueonly)",
    )

    output = _decide(_amend_with_heredoc(head), gerrit_repo)

    assert "additionalContext" in output["hookSpecificOutput"]
    assert not calls.exists()


def test_follows_cd_and_dash_c(gerrit_repo, tmp_path):
    assert _verdict(f"cd {gerrit_repo} && git commit -n -m x", tmp_path) == "deny"
    assert _verdict(f"git -C {gerrit_repo} commit -n -m x", tmp_path) == "deny"
    assert _verdict("git -C .. status && git commit -n -m x", gerrit_repo) == "deny"


def test_finds_commit_on_a_later_line(gerrit_repo):
    assert _verdict("git add a.txt\ngit commit -n -m x", gerrit_repo) == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "env GIT_TRACE=0 git commit -n -m x",
        "command git commit -n -m x",
        "bash -c 'git commit -n -m x'",
        'sh -c "cd . && git commit -n -m x"',
    ],
)
def test_looks_through_wrappers_and_shells(gerrit_repo, command):
    assert _verdict(command, gerrit_repo) == "deny"


def test_denies_moving_hooks_away(gerrit_repo):
    command = "git -c core.hooksPath=/dev/null commit -m x"

    assert _verdict(command, gerrit_repo) == "deny"
    reason = _decide(command, gerrit_repo)["hookSpecificOutput"][
        "permissionDecisionReason"
    ]
    assert "core.hooksPath" in reason


def test_asks_when_repository_is_overridden(gerrit_repo):
    assert _verdict("git --git-dir=/elsewhere/.git commit -m x", gerrit_repo) == "ask"
    assert _verdict("git --work-tree /elsewhere commit -m x", gerrit_repo) == "ask"


def test_keeps_lines_after_quoted_heredoc_marker(gerrit_repo):
    command = "echo '<<EOF'\ngit commit -n -m x"

    assert _verdict(command, gerrit_repo) == "deny"


def test_does_not_read_message_from_fifo(gerrit_repo):
    os.mkfifo(gerrit_repo / "msg")

    assert _verdict("git commit --amend -F msg", gerrit_repo) is None


def test_expands_git_aliases(gerrit_repo):
    _git(gerrit_repo, "config", "alias.ci", "commit -n")
    _git(gerrit_repo, "config", "alias.shci", "!git commit -n")

    assert _verdict("git ci -m x", gerrit_repo) == "deny"
    assert _verdict("git shci -m x", gerrit_repo) == "deny"
    assert _verdict("git -c alias.c2='commit --no-verify' c2 -m x", gerrit_repo) == (
        "deny"
    )


def test_asks_when_environment_changes_git_config(gerrit_repo):
    command = "GIT_CONFIG_PARAMETERS=\"'core.hooksPath=/dev/null'\" git commit -m x"

    assert _verdict(command, gerrit_repo) == "ask"
    assert _verdict("env GIT_DIR=/elsewhere git commit -m x", gerrit_repo) == "ask"


def test_denies_moving_hooks_away_through_config_env(gerrit_repo):
    command = "git --config-env=core.hooksPath=HOOKS commit -m x"

    assert _verdict(command, gerrit_repo) == "deny"


@pytest.mark.parametrize(
    "command", ["git commit --no-ver -m x", "git commit --amen --mess=x"]
)
def test_reads_abbreviated_long_options_like_git(gerrit_repo, command):
    assert _verdict(command, gerrit_repo) == "deny"


def test_follows_wrapper_options_and_exports(gerrit_repo, tmp_path):
    assert _verdict(f"env -C {gerrit_repo} git commit -n -m x", tmp_path) == "deny"
    assert _verdict("env -u HOME git commit -n -m x", gerrit_repo) == "deny"
    assert _verdict("env -S 'git commit -n -m x'", gerrit_repo) == "deny"
    assert _verdict("sudo git commit -m x", gerrit_repo) == "ask"
    assert _verdict("sudo -u someone git commit -m x", gerrit_repo) == "ask"
    assert _verdict("export GIT_DIR=/x; git commit -m x", gerrit_repo) == "ask"


def test_skips_other_git_verbs(gerrit_repo):
    assert _verdict("git log --grep='Change-Id: I123' -n 1", gerrit_repo) is None


def test_allows_command_it_cannot_parse(gerrit_repo):
    assert _verdict("git commit -n -m 'unbalanced", gerrit_repo) is None


def test_detects_gerrit_by_remote_host_from_config(plain_repo, tmp_path, monkeypatch):
    config = tmp_path / "gerrit_config.json"
    config.write_text(
        json.dumps(
            {"gerrit_hosts": [{"external_url": "https://gerrit-review.example.com/"}]}
        )
    )
    monkeypatch.setenv("GERRIT_CONFIG_PATH", str(config))
    _git(plain_repo, "remote", "add", "origin", "https://gerrit.example.com/project")

    assert git_guard.is_gerrit_repo(plain_repo)
    assert _verdict("git commit -m x", plain_repo) == "deny"  # no hook installed


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://gerrit.example.com/project", "gerrit.example.com"),
        ("ssh://user@gerrit.example.com:29418/project", "gerrit.example.com"),
        ("user@gerrit.example.com:project.git", "gerrit.example.com"),
        ("/srv/git/project.git", None),
    ],
)
def test_reads_hostname_of_remote_url(url, expected):
    assert git_guard._remote_hostname(url) == expected


def test_main_prints_decision_and_exits_zero(gerrit_repo, monkeypatch, capsys):
    payload = {"tool_input": {"command": "git commit -n -m x"}, "cwd": str(gerrit_repo)}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    with pytest.raises(SystemExit) as exit_info:
        git_guard.main()

    assert exit_info.value.code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_stays_silent_on_bad_payload(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))

    with pytest.raises(SystemExit) as exit_info:
        git_guard.main()

    assert exit_info.value.code == 0
    assert capsys.readouterr().out == ""


@pytest.fixture
def gerrit_chain(gerrit_repo, tmp_path):
    """A Gerrit repo with origin/master at Base and two local commits on top."""
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "master", str(remote))
    _git(gerrit_repo, "remote", "add", "origin", str(remote))
    _git(gerrit_repo, "push", "-q", "origin", "HEAD:refs/heads/master")
    _git(gerrit_repo, "fetch", "-q", "origin")
    for name in ("b", "c"):
        (gerrit_repo / f"{name}.txt").write_text(f"{name}\n")
        _git(gerrit_repo, "add", f"{name}.txt")
        _git(gerrit_repo, "commit", "-q", "-m", f"Add {name}")
    return gerrit_repo


def _reason(command: str, cwd: Path) -> str:
    return _decide(command, cwd)["hookSpecificOutput"]["permissionDecisionReason"]


def test_asks_before_push_for_review_with_chain_summary(gerrit_chain):
    command = "git push origin HEAD:refs/for/master"

    assert _verdict(command, gerrit_chain) == "ask"
    reason = _reason(command, gerrit_chain)
    assert "Push 2 change(s) to refs/for/master on origin" in reason
    assert reason.index("Add b") < reason.index("Add c")


def test_lists_chain_without_running_signature_program(
    gerrit_chain, tmp_path, monkeypatch
):
    calls = _commit_signed_with_spy(gerrit_chain, tmp_path, monkeypatch)

    reason = _reason("git push origin HEAD:refs/for/master", gerrit_chain)

    assert "Signed" in reason
    assert not calls.exists()


def test_mentions_topic_submit_on_push_with_topic(gerrit_chain):
    for command in (
        "git push origin HEAD:refs/for/master%topic=feature",
        "git push -o topic=feature origin HEAD:refs/for/master",
    ):
        assert "submitWholeTopic" in _reason(command, gerrit_chain)


def test_does_not_mention_topic_for_hashtag(gerrit_chain):
    reason = _reason("git push origin HEAD:refs/for/master%t=feature", gerrit_chain)

    assert "submitWholeTopic" not in reason


@pytest.mark.parametrize(
    "command",
    [
        "git push origin HEAD:refs/heads/master",
        "git push origin HEAD:master",
        "git push origin master",
        "git push origin --delete master",
        "git push",
        "git push --all origin",
    ],
)
def test_denies_direct_push_to_a_branch(gerrit_chain, command):
    assert _verdict(command, gerrit_chain) == "deny"
    assert "refs/for/master" in _reason(command, gerrit_chain)


def test_allows_direct_push_when_clone_opts_in(gerrit_chain):
    _git(gerrit_chain, "config", "gerrit-mcp.allowDirectPush", "true")

    assert _verdict("git push origin HEAD:refs/heads/master", gerrit_chain) is None


def test_pushes_for_review_without_asking_when_clone_opts_in(gerrit_chain):
    _git(gerrit_chain, "config", "gerrit-mcp.confirmPush", "false")

    assert _verdict("git push origin HEAD:refs/for/master", gerrit_chain) is None


@pytest.mark.parametrize(
    "command",
    [
        "git push origin HEAD:refs/for/master%submit",
        "git push origin HEAD:refs/for/master%topic=x,l=Code-Review+2",
        "git push -o Label=Verified+1 origin HEAD:refs/for/master",
        "git push --push-option=merged origin HEAD:refs/for/master",
    ],
)
def test_denies_push_options_that_vote_or_submit(gerrit_chain, command):
    _git(gerrit_chain, "config", "gerrit-mcp.confirmPush", "false")

    assert _verdict(command, gerrit_chain) == "deny"


def test_denies_configured_push_options_that_submit(gerrit_chain):
    _git(gerrit_chain, "config", "gerrit-mcp.confirmPush", "false")
    _git(gerrit_chain, "config", "push.pushOption", "submit")

    assert _verdict("git push origin HEAD:refs/for/master", gerrit_chain) == "deny"
    command = "git push -o topic=x origin HEAD:refs/for/master"
    assert _verdict(command, gerrit_chain) is None


def test_uses_configured_push_refspec(gerrit_chain):
    _git(gerrit_chain, "config", "remote.origin.push", "HEAD:refs/for/master")

    assert _verdict("git push", gerrit_chain) == "ask"


def test_ignores_tag_push(gerrit_chain):
    _git(gerrit_chain, "tag", "v1.0")

    assert _verdict("git push origin v1.0", gerrit_chain) is None
    assert _verdict("git push origin --tags", gerrit_chain) is None


@pytest.mark.parametrize(
    "command",
    [
        "git push --force origin HEAD:refs/for/master",
        "git push -f origin HEAD:refs/for/master",
        "git push origin +HEAD:refs/for/master",
    ],
)
def test_denies_force_push_for_review(gerrit_chain, command):
    assert _verdict(command, gerrit_chain) == "deny"


def test_denies_push_with_fixup_commits(gerrit_chain):
    (gerrit_chain / "b.txt").write_text("b fixed\n")
    _git(gerrit_chain, "commit", "-q", "-a", "--fixup=HEAD~1")

    reason = _reason("git push origin HEAD:refs/for/master", gerrit_chain)

    assert "fixup! Add b" in reason
    assert "--autosquash" in reason


def test_leaves_change_id_checks_to_gerrit(gerrit_chain):
    _git(gerrit_chain, "commit", "-q", "--allow-empty", "--no-verify", "-m", "No id")

    assert _verdict("git push origin HEAD:refs/for/master", gerrit_chain) == "ask"


def test_ignores_push_outside_gerrit(plain_repo):
    assert _verdict("git push origin HEAD:refs/heads/master", plain_repo) is None


def test_asks_when_push_repository_is_overridden(gerrit_chain):
    command = "git --git-dir=/elsewhere/.git push origin HEAD:refs/heads/master"

    assert _verdict(command, gerrit_chain) == "ask"


def test_treats_unqualified_destination_as_branch_despite_local_tag(gerrit_chain):
    _git(gerrit_chain, "tag", "v1.0")

    assert _verdict("git push origin HEAD:v1.0", gerrit_chain) == "deny"


def test_asks_before_push_to_other_refs(gerrit_chain):
    assert _verdict("git push origin HEAD:refs/meta/config", gerrit_chain) == "ask"
    assert _verdict("git push origin v1:refs/tags/v1", gerrit_chain) is None


def test_asks_when_push_config_is_overridden(gerrit_chain):
    command = "git -c remote.origin.push=HEAD:refs/heads/master push"

    assert _verdict(command, gerrit_chain) == "ask"
    assert "remote.origin.push" in _reason(command, gerrit_chain)


def test_keeps_direct_push_opt_out_with_the_user(gerrit_chain):
    reason = _reason("git push origin HEAD:refs/heads/master", gerrit_chain)

    assert "allowDirectPush" not in reason
    assert _verdict("git config gerrit-mcp.allowDirectPush true", gerrit_chain) == (
        "deny"
    )
    assert _verdict("git config --get gerrit-mcp.allowDirectPush", gerrit_chain) is None


def test_asks_on_any_config_override_for_push(gerrit_chain):
    command = "git -c user.name=x push origin HEAD:refs/for/master"

    assert _verdict(command, gerrit_chain) == "ask"
    assert "-c user.name=x" in _reason(command, gerrit_chain)


def test_denies_guard_settings_in_any_repository(plain_repo):
    command = "git config --global gerrit-mcp.allowDirectPush true"

    assert _verdict(command, plain_repo) == "deny"


def test_reads_direct_push_opt_out_from_clone_only(gerrit_chain, tmp_path, monkeypatch):
    global_config = tmp_path / "global-gitconfig"
    global_config.write_text("[gerrit-mcp]\n\tallowDirectPush = true\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))

    assert _verdict("git push origin HEAD:refs/heads/master", gerrit_chain) == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "git push --forc origin HEAD:refs/for/master",
        "git push --mirr origin",
    ],
)
def test_reads_abbreviated_push_options_like_git(gerrit_chain, command):
    assert _verdict(command, gerrit_chain) == "deny"


def test_treats_mirror_remote_as_push_of_every_branch(gerrit_chain):
    _git(gerrit_chain, "config", "remote.origin.mirror", "true")

    assert _verdict("git push", gerrit_chain) == "deny"


def test_asks_on_shell_expansion_in_push_or_config(gerrit_chain):
    assert _verdict("git push origin $REF", gerrit_chain) == "ask"
    assert _verdict("git config $KEY true", gerrit_chain) == "ask"


def test_denies_config_write_that_mentions_a_read_action(gerrit_chain):
    command = "git config --comment --get gerrit-mcp.allowDirectPush true"

    assert _verdict(command, gerrit_chain) == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "git push origin HEAD:refs/{heads,for}/master",
        "git push origin HEAD:refs/heads/maste?",
        "git push origin mast*",
        "git push origin -fo*:refs/for/master",
        "git config $KEY true",
    ],
)
def test_asks_on_brace_and_glob_expansion(gerrit_chain, command):
    assert _verdict(command, gerrit_chain) == "ask"


@pytest.mark.parametrize(
    "command",
    [
        "git config gerrit-{mcp,x}.allowDirectPush true",
        "git config gerrit-mc?.allowDirectPush true",
        "GIT_EDITOR=true git config --edit",
        "GIT_EDITOR=true git config --ed",
        "GIT_EDITOR=true git config -ze",
        "GIT_EDITOR=true git config edit",
    ],
)
def test_denies_config_that_may_reach_guard_settings(gerrit_chain, command):
    assert _verdict(command, gerrit_chain) == "deny"


def test_denies_config_that_names_guard_section_anywhere(gerrit_chain):
    command = "git config --rename-section x gerrit-mcp"

    assert _verdict(command, gerrit_chain) == "deny"


def test_guards_other_ways_to_send_refs_or_settings(gerrit_chain):
    assert _verdict("git send-pack origin HEAD:master", gerrit_chain) == "ask"
    command = "git -c gerrit-mcp.allowDirectPush=true push origin HEAD:master"
    assert _verdict(command, gerrit_chain) == "deny"
    command = "git clone -c gerrit-mcp.allowDirectPush=true origin copy"
    assert _verdict(command, gerrit_chain) == "deny"


def test_allows_paths_and_messages_that_mention_the_project(gerrit_chain):
    assert _verdict("git log -- /src/gerrit-mcp-server/README.md", gerrit_chain) is None
    command = "git config -f /src/gerrit-mcp-server/.git/config user.name x"
    assert _verdict(command, gerrit_chain) is None
    command = "git commit -m 'Document gerrit-mcp.allowDirectPush'"
    assert _verdict(command, gerrit_chain) is None
