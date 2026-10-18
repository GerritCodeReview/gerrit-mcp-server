"""Runs the git recipes the skills document, in temporary repositories.

Each recipe is asserted to appear verbatim in its skill file before it runs, so
a recipe edited in a skill must be edited here too. No editor is available:
a recipe that opens one fails.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[2]
WORKFLOW = PROJECT_ROOT / "skills/gerrit-workflow/SKILL.md"
CHAINS = PROJECT_ROOT / "skills/gerrit-workflow/references/relation-chains.md"
RETRO_SPLIT = PROJECT_ROOT / "skills/stack-planner/references/retro-split.md"

# Stands in for Gerrit's commit-msg hook: skips fixup!/squash! commits and adds
# a Change-Id, from the message and HEAD, unless one is there.
FAKE_COMMIT_MSG_HOOK = """#!/bin/sh
head -n1 "$1" | grep -q '^[a-z][a-z]*! ' && exit 0
grep -q '^Change-Id:' "$1" && exit 0
id=$({ git rev-parse -q --verify HEAD; cat "$1"; } | git hash-object --stdin)
printf '\\nChange-Id: I%s\\n' "$id" >> "$1"
"""

needs_perl = pytest.mark.skipif(shutil.which("perl") is None, reason="needs perl")


def _environment() -> dict[str, str]:
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_EDITOR": "false",
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    return environment


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=_environment(),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _recipe(doc: Path, template: str, **values: str) -> str:
    assert template in doc.read_text(), f"recipe not in {doc.name}: {template}"
    for placeholder, value in values.items():
        template = template.replace(f"<{placeholder}>", value)
    return template


def _run(repo: Path, command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        shell=True,
        cwd=repo,
        env=_environment(),
        capture_output=True,
        text=True,
    )


def _ok(repo: Path, command: str) -> str:
    result = _run(repo, command)
    assert result.returncode == 0, f"{command}\n{result.stdout}{result.stderr}"
    return result.stdout.strip()


def _commit(repo: Path, path: str, content: str, subject: str) -> None:
    (repo / path).write_text(content)
    _git(repo, "add", path)
    _git(repo, "commit", "-q", "-m", subject)


def _sha7(repo: Path, subject: str) -> str:
    return _git(repo, "log", "--format=%h", f"--grep=^{subject}$", "-1")


def _change_ids(repo: Path) -> list[str]:
    listing = _ok(
        repo,
        _recipe(
            CHAINS,
            "git log --reverse --format='%h %(trailers:key=Change-Id,valueonly,"
            "separator=%x2C) %s' origin/master..HEAD",
        ),
    )
    ids = [line.split(" ", 2)[1] for line in listing.splitlines()]
    assert all(re.fullmatch(r"I[0-9a-f]{40}", i) for i in ids), listing
    return ids


def _subjects(repo: Path) -> list[str]:
    return _git(repo, "log", "--reverse", "--format=%s", "origin/master..HEAD").split(
        "\n"
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q", "-b", "master")
    hook = path / ".git" / "hooks" / "commit-msg"
    hook.write_text(FAKE_COMMIT_MSG_HOOK)
    hook.chmod(0o755)
    _commit(path, "base.txt", "base\n", "Base")
    _git(path, "update-ref", "refs/remotes/origin/master", "HEAD")
    return path


@pytest.fixture
def chain(repo: Path) -> Path:
    for name in "abc":
        _commit(repo, f"{name}.txt", f"{name}\n", f"Add {name}")
    return repo


def test_change_id_list_has_one_id_per_commit(chain):
    assert len(_change_ids(chain)) == 3


def test_amend_message_from_file_keeps_change_id(chain, tmp_path):
    ids = _change_ids(chain)
    message = tmp_path / "message"

    _ok(chain, _recipe(CHAINS, "git log -1 --format=%B > <file>", file=str(message)))
    message.write_text(message.read_text().replace("Add c", "Add c file", 1))
    _ok(chain, _recipe(CHAINS, "git commit --amend -F <file>", file=str(message)))

    assert _change_ids(chain) == ids
    assert _subjects(chain)[-1] == "Add c file"


def test_fixup_into_middle_commit_keeps_change_ids(chain):
    ids = _change_ids(chain)
    (chain / "b.txt").write_text("b fixed\n")

    _ok(
        chain,
        _recipe(
            CHAINS,
            "git add <paths>\n"
            "git commit --fixup=<sha>\n"
            "git -c sequence.editor=true rebase -i --autosquash origin/master",
            paths="b.txt",
            sha=_sha7(chain, "Add b"),
        ),
    )

    assert _change_ids(chain) == ids
    assert _subjects(chain) == ["Add a", "Add b", "Add c"]
    assert _git(chain, "show", "HEAD~1:b.txt") == "b fixed"


@needs_perl
def test_reword_middle_commit_keeps_change_ids(chain, tmp_path):
    ids = _change_ids(chain)
    message = tmp_path / "message"

    _ok(
        chain,
        _recipe(
            CHAINS,
            "git -c sequence.editor=\"perl -pi -e 's/^pick <sha7> /edit <sha7> /'\" "
            "rebase -i origin/master",
            sha7=_sha7(chain, "Add b"),
        ),
    )
    _ok(chain, _recipe(CHAINS, "git log -1 --format=%B > <file>", file=str(message)))
    message.write_text(message.read_text().replace("Add b", "Add b file", 1))
    _ok(chain, _recipe(CHAINS, "git commit --amend -F <file>", file=str(message)))
    _ok(chain, _recipe(CHAINS, "git rebase --continue"))

    assert _change_ids(chain) == ids
    assert _subjects(chain) == ["Add a", "Add b file", "Add c"]


def test_verify_each_commit_stops_at_the_failing_one(chain):
    ids = _change_ids(chain)
    verify = _recipe(
        CHAINS,
        "git -c sequence.editor=true rebase -i --exec '<verify command>' origin/master",
        **{"verify command": "! grep -qx b b.txt"},
    )

    assert _run(chain, verify).returncode != 0
    assert _git(chain, "log", "-1", "--format=%s") == "Add b"

    (chain / "b.txt").write_text("b fixed\n")
    _ok(chain, _recipe(CHAINS, "git add <paths>", paths="b.txt"))
    _ok(chain, _recipe(CHAINS, "git commit --amend --no-edit"))
    _ok(chain, _recipe(CHAINS, "git rebase --continue"))

    assert _change_ids(chain) == ids
    assert _git(chain, "show", "HEAD~1:b.txt") == "b fixed"


@needs_perl
@pytest.mark.parametrize(
    "action, kept", [("fixup", "Add a"), ("fixup -C", "Add b")], ids=["fixup", "-C"]
)
def test_squash_keeps_one_change_id(chain, action, kept):
    ids = dict(zip(["Add a", "Add b", "Add c"], _change_ids(chain)))

    _ok(
        chain,
        _recipe(
            WORKFLOW,
            'git -c sequence.editor="perl -pi -e '
            f"'s/^pick <sha7> /{action} <sha7> /'\" rebase -i origin/master",
            sha7=_sha7(chain, "Add b"),
        ),
    )

    assert _subjects(chain) == [kept, "Add c"]
    assert _change_ids(chain) == [ids[kept], ids["Add c"]]
    assert _git(chain, "show", "HEAD~1:b.txt") == "b"


def test_cherry_pick_gets_new_change_id(chain, tmp_path):
    old_id = _change_ids(chain)[1]
    message = tmp_path / "message"
    _git(chain, "checkout", "-q", "-b", "backport", "origin/master")

    _ok(
        chain,
        _recipe(
            WORKFLOW,
            "git cherry-pick <commit-sha>",
            **{"commit-sha": _git(chain, "rev-parse", "master~1")},
        ),
    )
    _ok(
        chain,
        _recipe(
            WORKFLOW,
            "git log -1 --format=%B | grep -v '^Change-Id:' > <file>",
            file=str(message),
        ),
    )
    _ok(chain, _recipe(WORKFLOW, "git reset --soft HEAD~1"))
    _ok(chain, _recipe(WORKFLOW, "git commit -F <file>", file=str(message)))

    [new_id] = _change_ids(chain)
    assert new_id != old_id


def test_retro_split_of_worktree_keeps_the_tree(repo, tmp_path):
    lines = [f"line {n}\n" for n in range(1, 21)]
    _commit(repo, "shared.txt", "".join(lines), "Add shared")
    _git(repo, "update-ref", "refs/remotes/origin/master", "HEAD")
    lines[1] = "concern a\n"
    lines[17] = "concern b\n"
    (repo / "shared.txt").write_text("".join(lines))
    (repo / "new.txt").write_text("concern b\n")

    _ok(repo, _recipe(RETRO_SPLIT, "git add -A"))
    orig = _ok(repo, _recipe(RETRO_SPLIT, "git stash create"))
    _ok(repo, _recipe(RETRO_SPLIT, "git reset\n"))
    _ok(repo, _recipe(RETRO_SPLIT, "git tag retro-split/orig <orig>", orig=orig))

    # Concern a's patch: the diff header and the first of its two hunks.
    header, hunks = _git(repo, "diff", "--", "shared.txt").split("\n@@", 1)
    first_hunk = hunks.split("\n@@")[0]
    patch = tmp_path / "concern-a.patch"
    patch.write_text(f"{header}\n@@{first_hunk}\n")
    message = tmp_path / "message"
    _ok(
        repo,
        _recipe(
            RETRO_SPLIT,
            "git apply --cached --recount <patch-file>",
            **{"patch-file": str(patch)},
        ),
    )
    message.write_text("Concern a\n")
    _ok(
        repo,
        _recipe(RETRO_SPLIT, "git commit -F <msg-file>", **{"msg-file": str(message)}),
    )
    add = _recipe(RETRO_SPLIT, "git add <path>...")
    _ok(repo, add.replace("<path>...", "shared.txt new.txt"))
    message.write_text("Concern b\n")
    _ok(
        repo,
        _recipe(RETRO_SPLIT, "git commit -F <msg-file>", **{"msg-file": str(message)}),
    )

    assert _ok(repo, _recipe(RETRO_SPLIT, "git status --porcelain")) == ""
    assert (
        _ok(repo, _recipe(RETRO_SPLIT, "git diff retro-split/orig..HEAD --stat")) == ""
    )
    assert "concern b" not in _git(repo, "show", "HEAD~1:shared.txt")
    assert len(_change_ids(repo)) == 2


def test_retro_split_keeping_the_change_as_tip(chain):
    (chain / "x.txt").write_text("x\n")
    (chain / "y.txt").write_text("y\n")
    _git(chain, "add", "x.txt", "y.txt")
    _git(chain, "commit", "-q", "-m", "Add x and y")
    tip_id = _change_ids(chain)[-1]

    _ok(chain, _recipe(RETRO_SPLIT, "git tag retro-split/orig HEAD"))
    base = _ok(chain, _recipe(RETRO_SPLIT, "git rev-parse HEAD~1"))
    _ok(chain, _recipe(RETRO_SPLIT, "git reset <base>", base=base))
    _git(chain, "add", "x.txt")
    _git(chain, "commit", "-q", "-m", "Add x")
    _git(chain, "add", "y.txt")
    _ok(chain, _recipe(RETRO_SPLIT, "git commit -C retro-split/orig"))

    assert _change_ids(chain)[-1] == tip_id
    assert (
        _ok(chain, _recipe(RETRO_SPLIT, "git diff retro-split/orig..HEAD --stat")) == ""
    )
