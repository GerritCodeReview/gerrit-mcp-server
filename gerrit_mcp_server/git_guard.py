"""PreToolUse guard for git commands run by Claude Code in Gerrit repositories.

Reads the hook payload from stdin and prints a permission decision as JSON:
"deny" for a command that would lose or forge a Change-Id or bypass review,
"ask" for one the user has to confirm (every push for review), nothing
otherwise. It always exits 0 and stays silent on
anything it cannot parse or check, so a broken guard never blocks git.

Only the standard library is used: the guard runs before every git command.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

CONFIG_FILE_PATH = Path(__file__).parent / "gerrit_config.json"

# git commit options whose value is the next token (or attached to a short one).
_COMMIT_SHORT_WITH_VALUE = set("mFCct")
# Short options whose optional value can only be attached (-S<keyid>, -u<mode>).
_COMMIT_SHORT_ATTACHED_VALUE = set("Su")
_COMMIT_LONG_WITH_VALUE = {
    "--message",
    "--file",
    "--reuse-message",
    "--reedit-message",
    "--template",
    "--author",
    "--date",
    "--cleanup",
    "--trailer",
    "--fixup",
    "--squash",
    "--pathspec-from-file",
}
_COMMIT_LONG_FLAGS = {"--amend", "--no-verify"}
_GIT_GLOBAL_WITH_VALUE = {"--git-dir", "--work-tree", "--namespace"}
_WRAPPERS = {"env", "command", "exec", "time", "nice", "nohup", "sudo", "xargs"}
_SHELLS = {"sh", "bash", "zsh", "dash"}
# Wrapper options that take a value. sudo is never needed for git, so the
# guard does not follow it: git under sudo always asks.
_WRAPPER_VALUES = {
    "env": {"-u", "--unset", "-C", "--chdir"},
    "xargs": {"-I", "-L", "-n", "-P", "-s", "-d", "-E", "-a"},
    "time": {"-o", "-f"},
    "nice": {"-n"},
}
_MAX_MESSAGE_FILE_BYTES = 1 << 20
_GIT_ENVIRONMENT_OVERRIDES = ("GIT_CONFIG", "GIT_DIR=", "GIT_WORK_TREE=")
_BUILTINS = {
    "add",
    "branch",
    "checkout",
    "cherry-pick",
    "clone",
    "commit",
    "config",
    "diff",
    "fetch",
    "grep",
    "init",
    "log",
    "ls-files",
    "merge",
    "pull",
    "push",
    "rebase",
    "remote",
    "reset",
    "restore",
    "rev-parse",
    "show",
    "stash",
    "status",
    "switch",
    "tag",
}
_CHANGE_ID_LINE = re.compile(r"^\s*Change-Id:", re.MULTILINE)
_CHANGE_ID_VALUE = re.compile(r"^\s*Change-Id:\s*(\S+)", re.MULTILINE)
# A --trailer value: git accepts both "key: value" and "key=value".
_CHANGE_ID_TRAILER = re.compile(r"\s*Change-Id\s*[:=]", re.IGNORECASE)
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SEPARATORS = {"&&", "||", ";", "|", "&", "\n", "(", ")"}


@dataclass
class GitInvocation:
    """One git command found in a Bash command line."""

    directory: Path
    verb: str
    args: List[str]
    config: List[str] = field(default_factory=list)  # git -c key=value
    repository_override: bool = False  # --git-dir, --work-tree, --namespace
    environment: List[str] = field(default_factory=list)  # NAME=value before git
    opaque_wrapper: Optional[str] = None  # e.g. env -S: arguments not parsed


@dataclass
class Decision:
    """The strictest verdict across all invocations: deny > ask > allow."""

    deny: List[str] = field(default_factory=list)
    ask: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)  # for the model; no verdict

    def to_hook_output(self) -> Optional[Dict]:
        if self.deny:
            verdict, reasons = "deny", [*self.deny, "Nothing in this command ran."]
        elif self.ask:
            verdict, reasons = "ask", self.ask
        elif self.notes:
            # No permissionDecision: the user's permission settings still apply.
            # "allow" would skip the prompt for the whole command.
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": "\n".join(self.notes),
                }
            }
        else:
            return None
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": verdict,
                "permissionDecisionReason": "\n".join(reasons),
            }
        }


def split_heredocs(command: str) -> Tuple[str, List[str]]:
    """Removes heredoc bodies from a command; returns it and the bodies.

    shlex cannot tokenize a heredoc body (an apostrophe in a commit message
    is an unbalanced quote), so the bodies are cut out before parsing and
    checked on their own.
    """
    bodies: List[str] = []
    lines = command.split("\n")
    kept: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        i += 1
        for match in _HEREDOC.finditer(line):
            delimiter = match.group(2)
            end = i
            while end < len(lines) and lines[end].strip() != delimiter:
                end += 1
            if end == len(lines):
                # No closing delimiter: not a heredoc (e.g. "<<EOF" inside
                # quotes). Keep the following lines so they are still parsed.
                continue
            bodies.append("\n".join(lines[i:end]))
            kept.append(lines[end])
            i = end + 1
    return "\n".join(kept), bodies


def tokenize(command: str) -> List[str]:
    """Splits a shell command into words and operator tokens (newline too)."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _segments(tokens: List[str]) -> List[List[str]]:
    segments: List[List[str]] = [[]]
    for token in tokens:
        if token in _SEPARATORS:
            segments.append([])
        else:
            segments[-1].append(token)
    return [s for s in segments if s]


@dataclass
class _Wrapped:
    words: List[str]
    assignments: List[str] = field(default_factory=list)
    chdir: Optional[str] = None
    opaque: Optional[str] = None


def _strip_wrappers(words: List[str]) -> _Wrapped:
    """Drops commands that only run another one, and variable assignments.

    Keeps what can change what git does: the assignments (GIT_CONFIG_*,
    GIT_DIR), `env -C <dir>`, and options the guard cannot follow.
    """
    wrapped = _Wrapped(words)
    while wrapped.words:
        word = wrapped.words[0]
        name = Path(word).name
        if _ASSIGNMENT.match(word):
            wrapped.assignments.append(word)
            wrapped.words = wrapped.words[1:]
            continue
        if name not in _WRAPPERS:
            break
        if name == "sudo":  # not followed: jump to git, and always ask
            wrapped.opaque = "sudo"
            rest = wrapped.words[1:]
            git_at = [i for i, w in enumerate(rest) if Path(w).name == "git"]
            wrapped.words = rest[git_at[0] :] if git_at else []
            continue
        rest = wrapped.words[1:]
        while rest and (rest[0].startswith("-") or _ASSIGNMENT.match(rest[0])):
            option = rest.pop(0)
            flag, has_value, value = option.partition("=")
            if _ASSIGNMENT.match(option):
                wrapped.assignments.append(option)
            elif name == "env" and flag in ("-S", "--split-string"):
                if not has_value and rest:
                    value = rest.pop(0)
                rest = shlex.split(value) + rest
            elif flag in _WRAPPER_VALUES.get(name, ()):
                if not has_value and rest:
                    value = rest.pop(0)
                if name == "env" and flag in ("-C", "--chdir"):
                    wrapped.chdir = value
        wrapped.words = rest
    return wrapped


def find_git_invocations(
    command: str, cwd: Path, depth: int = 0
) -> List[GitInvocation]:
    """Returns every git invocation in a command, with the directory it runs in.

    Follows `cd <dir>` between commands and `git -C <dir>`, looks through
    wrappers such as `env` or `command`, and into `bash -c '<script>'`.
    Raises ValueError when the command cannot be tokenized.
    """
    stripped, _ = split_heredocs(command)
    directory = cwd
    exported: List[str] = []
    invocations: List[GitInvocation] = []
    for words in _segments(tokenize(stripped)):
        if words[0] == "export":
            exported += [w for w in words[1:] if _ASSIGNMENT.match(w)]
            continue
        wrapped = _strip_wrappers(words)
        words = wrapped.words
        if not words:
            continue
        name = Path(words[0]).name
        if name == "cd" and len(words) > 1:
            directory = (directory / os.path.expanduser(words[1])).resolve()
            continue
        if name in _SHELLS and "-c" in words and depth < 3:
            script = words[words.index("-c") + 1 : words.index("-c") + 2]
            if script:
                invocations += find_git_invocations(script[0], directory, depth + 1)
            continue
        if name != "git":
            continue
        invocation = GitInvocation(
            directory,
            "",
            [],
            environment=exported + wrapped.assignments,
            opaque_wrapper=wrapped.opaque,
        )
        if wrapped.chdir:
            invocation.directory = (
                directory / os.path.expanduser(wrapped.chdir)
            ).resolve()
        rest = words[1:]
        while rest and rest[0].startswith("-"):
            option = rest.pop(0)
            if option == "-C" and rest:
                invocation.directory = (
                    invocation.directory / os.path.expanduser(rest.pop(0))
                ).resolve()
            elif option == "-c" and rest:
                invocation.config.append(rest.pop(0))
            elif option.startswith("--config-env"):
                # --config-env=<key>=<envvar>: the value comes from the
                # environment, so only the key is known.
                value = option.partition("=")[2] or (rest.pop(0) if rest else "")
                invocation.config.append(value)
            elif option.split("=")[0] in _GIT_GLOBAL_WITH_VALUE:
                invocation.repository_override = True
                if "=" not in option and rest:
                    rest.pop(0)
        if rest:
            invocation.verb, invocation.args = rest[0], rest[1:]
            invocations += _expand_alias(invocation, depth)
    return invocations


def _alias(invocation: GitInvocation) -> Optional[str]:
    # git never lets an alias shadow a built-in command, so built-ins need no
    # lookup; -c alias.<verb>=... on the command line wins over the config.
    if invocation.verb in _BUILTINS:
        return None
    for setting in reversed(invocation.config):
        key, _, value = setting.partition("=")
        if key.lower() == f"alias.{invocation.verb.lower()}":
            return value
    return _git(invocation.directory, "config", "--get", f"alias.{invocation.verb}")


def _expand_alias(invocation: GitInvocation, depth: int) -> List[GitInvocation]:
    """Replaces a git alias by the command it runs (up to three levels)."""
    alias = _alias(invocation)
    if not alias or depth >= 3:
        return [invocation]
    if alias.startswith("!"):  # a shell alias: check the shell command
        script = " ".join([alias[1:], *map(shlex.quote, invocation.args)])
        return find_git_invocations(script, invocation.directory, depth + 1)
    words = shlex.split(alias)
    if not words:
        return [invocation]
    invocation.verb, invocation.args = words[0], words[1:] + invocation.args
    return _expand_alias(invocation, depth + 1)


def _git(directory: Path, *args: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _gerrit_hostnames() -> List[str]:
    path = Path(os.environ.get("GERRIT_CONFIG_PATH") or CONFIG_FILE_PATH)
    try:
        config = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    hosts = []
    for host in config.get("gerrit_hosts", []):
        for key in ("external_url", "internal_url"):
            url = host.get(key)
            if url:
                hostname = urlparse(url if "://" in url else f"https://{url}").hostname
                if hostname:
                    hosts.append(hostname)
    return hosts


def _remote_hostname(url: str) -> Optional[str]:
    if "://" in url:
        return urlparse(url).hostname
    match = re.match(r"^(?:[^@/]+@)?([^:/]+):", url)  # scp-like user@host:path
    return match.group(1) if match else None


def _same_gerrit_host(a: str, b: str) -> bool:
    # googlesource.com serves git at <name>.googlesource.com and the review
    # UI and REST API at <name>-review.googlesource.com.
    def canonical(hostname: str) -> str:
        first, _, rest = hostname.lower().partition(".")
        return f"{first.removesuffix('-review')}.{rest}"

    return canonical(a) == canonical(b)


def _commit_msg_hook(directory: Path) -> Optional[Path]:
    path = _git(directory, "rev-parse", "--git-path", "hooks/commit-msg")
    if not path:
        return None
    hook = Path(path)
    return hook if hook.is_absolute() else directory / hook


def has_change_id_hook(directory: Path) -> bool:
    """Whether the Gerrit commit-msg hook (or one that adds Change-Ids) is set."""
    hook = _commit_msg_hook(directory)
    if not hook or not hook.is_file() or not os.access(hook, os.X_OK):
        return False
    try:
        return "Change-Id" in hook.read_text(errors="replace")
    except OSError:
        return False


def is_gerrit_repo(directory: Path) -> bool:
    """Whether a directory is in a repository whose reviews happen on Gerrit.

    True when the repository has a .gitreview file, when a remote points at a
    host from gerrit_config.json, or when the Gerrit commit-msg hook is set.
    """
    toplevel = _git(directory, "rev-parse", "--show-toplevel")
    if not toplevel:
        return False
    if (Path(toplevel) / ".gitreview").is_file():
        return True
    remotes = _git(directory, "config", "--get-regexp", r"^remote\..*\.(push)?url$")
    configured = _gerrit_hostnames()
    for line in (remotes or "").splitlines():
        _, _, url = line.partition(" ")
        hostname = _remote_hostname(url)
        if hostname and any(_same_gerrit_host(hostname, h) for h in configured):
            return True
    return has_change_id_hook(directory)


@dataclass
class CommitOptions:
    amend: bool = False
    no_verify: bool = False
    message: bool = False
    messages: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    trailers: List[str] = field(default_factory=list)


def _long_options(name: str, known: Set[str]) -> Set[str]:
    """Resolves a long option the way git does: a unique prefix is enough.

    Returns every known option the name can stand for, so an ambiguous
    abbreviation (which git rejects anyway) is checked as all of them.
    """
    if name in known:
        return {name}
    if len(name) < 3:
        return set()
    return {option for option in known if option.startswith(name)}


def parse_commit_args(args: List[str]) -> CommitOptions:
    options = CommitOptions()
    i = 0
    while i < len(args):
        arg = args[i]
        i += 1
        if arg == "--":
            break
        if arg.startswith("--"):
            name, has_value, value = arg.partition("=")
            names = _long_options(name, _COMMIT_LONG_WITH_VALUE | _COMMIT_LONG_FLAGS)
            if names & _COMMIT_LONG_WITH_VALUE and not has_value and i < len(args):
                value = args[i]
                i += 1
            if "--amend" in names:
                options.amend = True
            if "--no-verify" in names:
                options.no_verify = True
            if "--message" in names:
                options.message = True
                options.messages.append(value)
            if "--file" in names:
                options.files.append(value)
            if "--trailer" in names:
                options.trailers.append(value)
            continue
        if not arg.startswith("-") or arg == "-":
            continue
        for position, flag in enumerate(arg[1:], start=1):
            if flag in _COMMIT_SHORT_WITH_VALUE:
                value = arg[position + 1 :]
                if not value and i < len(args):
                    value = args[i]
                    i += 1
                if flag == "m":
                    options.message = True
                    options.messages.append(value)
                elif flag == "F":
                    options.files.append(value)
                break
            if flag in _COMMIT_SHORT_ATTACHED_VALUE:
                break
            if flag == "n":
                options.no_verify = True
    return options


def _read_message_file(directory: Path, name: str) -> Optional[str]:
    path = Path(os.path.expanduser(name))
    if not path.is_absolute():
        path = directory / path
    try:
        # A FIFO or a device such as /dev/zero would block or never end.
        if not path.is_file():
            return None
        with path.open("rb") as message_file:
            return message_file.read(_MAX_MESSAGE_FILE_BYTES).decode(errors="replace")
    except OSError:
        return None


def _ask_on_repository_override(invocation: GitInvocation, decision: Decision) -> bool:
    """Asks when git would not use the repository or config the guard checks."""
    variables = [
        a.partition("=")[0]
        for a in invocation.environment
        if a.startswith(_GIT_ENVIRONMENT_OVERRIDES)
    ]
    if invocation.repository_override or variables or invocation.opaque_wrapper:
        what = (
            ", ".join(variables)
            or invocation.opaque_wrapper
            or "--git-dir, --work-tree or --namespace"
        )
        decision.ask.append(
            f"git {invocation.verb} with {what}: the guard cannot check the "
            "repository and config git will use. Confirm the command."
        )
        return True
    return False


def _check_typed_change_ids(
    directory: Path, heredocs: List[str], decision: Decision
) -> None:
    """Compares a Change-Id typed in a heredoc with HEAD's on --amend -F."""
    typed = [i for h in heredocs for i in _CHANGE_ID_VALUE.findall(h)]
    if not typed:
        return
    # --no-show-signature: log.showSignature would run gpg.program before the
    # user approved anything.
    trailers = _git(
        directory,
        "log",
        "-1",
        "--no-show-signature",
        "--format=%(trailers:key=Change-Id,valueonly)",
    )
    head = (trailers or "").split()
    if not head:
        return
    if any(i not in head for i in typed):
        decision.deny.append(
            f"git commit --amend -F: this Change-Id differs from HEAD's "
            f"({', '.join(head)}); Gerrit would open a NEW change instead of a new "
            "patch set. Keep HEAD's: 'git log -1 --format=%B > <file>', edit "
            "<file>, 'git commit --amend -F <file>'. If Gerrit shows a different "
            "Change-Id for this change, HEAD's was lost: show both ids to the "
            "user instead of retrying."
        )
    else:
        decision.notes.append(
            "Change-Id matches HEAD's, so this is fine; next time start the file "
            "with 'git log -1 --format=%B > <file>' instead of typing the trailer."
        )


def check_commit(
    invocation: GitInvocation, heredocs: List[str], decision: Decision
) -> None:
    if _ask_on_repository_override(invocation, decision):
        return
    options = parse_commit_args(invocation.args)
    directory = invocation.directory

    if options.no_verify:
        decision.deny.append(
            "git commit --no-verify (-n) skips the commit-msg hook, so the commit "
            "gets no Change-Id and Gerrit cannot track it. Commit without it."
        )
    if any(c.split("=")[0].lower() == "core.hookspath" for c in invocation.config):
        decision.deny.append(
            "git -c core.hooksPath=... moves the hooks away from the commit-msg "
            "hook, so the commit would get no Change-Id. Commit without it."
        )
    if not has_change_id_hook(directory):
        decision.deny.append(
            "The Gerrit commit-msg hook is not installed, so this commit would "
            "get no Change-Id. Install it first (gerrit-workflow skill, 'The "
            "commit-msg Hook'), then commit again."
        )

    if options.amend and options.message:
        decision.deny.append(
            "git commit --amend -m replaces the whole message and drops the "
            "Change-Id, so Gerrit would open a NEW change instead of a new patch "
            "set. Use 'git commit --amend --no-edit', or write the message with "
            "'git log -1 --format=%B > <file>', edit it, and 'git commit --amend "
            "-F <file>'."
        )
        return

    if any(_CHANGE_ID_TRAILER.match(t) for t in options.trailers):
        decision.deny.append(
            "git commit --trailer adds a hand-written Change-Id. The commit-msg "
            "hook adds it; drop that --trailer and commit again."
        )
        return

    texts = list(options.messages)
    texts += heredocs
    file_texts = [_read_message_file(directory, f) for f in options.files if f != "-"]

    if options.amend and options.files:
        # Only a file the guard can read now is checked: stdin, or a file that
        # does not exist yet (the same command writes it), is let through. Any
        # Change-Id passes, so re-applying the one Gerrit shows works. A
        # Change-Id typed in a heredoc must be HEAD's.
        if any(t is not None and not _CHANGE_ID_LINE.search(t) for t in file_texts):
            decision.deny.append(
                "git commit --amend -F: the message has no Change-Id line, so the "
                "hook adds a new one and Gerrit opens a NEW change instead of a "
                "new patch set. Keep the line: 'git log -1 --format=%B > <file>' "
                "starts the file with it. For a new change on purpose: "
                "'git reset --soft HEAD~1', then 'git commit -F <file>'."
            )
        _check_typed_change_ids(directory, heredocs, decision)
        return

    if not options.amend:
        typed = [t for t in texts + file_texts if t and _CHANGE_ID_LINE.search(t)]
        if typed:
            decision.deny.append(
                "The commit message carries a hand-written Change-Id trailer. The "
                "commit-msg hook adds it; remove the Change-Id line and commit "
                "again."
            )


@dataclass
class PushOptions:
    remote: Optional[str] = None
    refspecs: List[str] = field(default_factory=list)
    force: bool = False
    delete: bool = False
    all_branches: bool = False
    tags_only: bool = False
    push_options: List[str] = field(default_factory=list)


_PUSH_LONG_WITH_VALUE = {"--repo", "--receive-pack", "--exec", "--push-option"}
_PUSH_FORCE = {"--force", "--force-with-lease", "--force-if-includes"}
_PUSH_ALL = {"--all", "--branches", "--mirror"}
_PUSH_LONG = _PUSH_LONG_WITH_VALUE | _PUSH_FORCE | _PUSH_ALL | {"--delete", "--tags"}


def _may_expand(word: str, patterns: str) -> bool:
    """Whether the shell may still turn a word into something else.

    shlex keeps $VAR, `cmd`, braces and globs as literal text, so the guard
    sees a different word than git would.
    """
    return any(c in word for c in "$`" + patterns) or word.startswith("~")


def parse_push_args(args: List[str]) -> PushOptions:
    options = PushOptions()
    positional: List[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        i += 1
        if arg == "--":
            positional += args[i:]
            break
        if arg.startswith("--"):
            name, has_value, value = arg.partition("=")
            names = _long_options(name, _PUSH_LONG)
            if names & _PUSH_LONG_WITH_VALUE and not has_value and i < len(args):
                value = args[i]
                i += 1
            if names & _PUSH_FORCE:
                options.force = True
            if "--delete" in names:
                options.delete = True
            if names & _PUSH_ALL:
                options.all_branches = True
            if names == {"--tags"}:
                options.tags_only = True
            if "--push-option" in names:
                options.push_options.append(value)
            if "--repo" in names and not options.remote:
                options.remote = value
            continue
        if arg.startswith("-") and arg != "-":
            for position, flag in enumerate(arg[1:], start=1):
                if flag == "o":
                    value = arg[position + 1 :]
                    if not value and i < len(args):
                        value = args[i]
                        i += 1
                    options.push_options.append(value)
                    break
                if flag == "f":
                    options.force = True
                elif flag == "d":
                    options.delete = True
            continue
        positional.append(arg)
    if positional:
        options.remote = options.remote or positional[0]
        options.refspecs = positional[1:]
    return options


def _current_branch(directory: Path) -> Optional[str]:
    return _git(directory, "symbolic-ref", "-q", "--short", "HEAD")


def _push_remote(directory: Path, options: PushOptions) -> str:
    if options.remote:
        return options.remote
    branch = _current_branch(directory)
    keys = [f"branch.{branch}.pushRemote", "remote.pushDefault"] if branch else []
    keys += [f"branch.{branch}.remote"] if branch else []
    for key in keys:
        value = _git(directory, "config", "--get", key)
        if value:
            return value
    return "origin"


def _push_refspecs(directory: Path, remote: str, options: PushOptions) -> List[str]:
    if options.refspecs:
        return options.refspecs
    if options.all_branches:
        return ["refs/heads/*:refs/heads/*"]
    if options.tags_only:
        return []
    configured = _git(directory, "config", "--get-all", f"remote.{remote}.push")
    if configured:
        return configured.splitlines()
    # push.default (simple, current, upstream) pushes the current branch to a
    # branch of the same or the upstream name: a direct push.
    return [_current_branch(directory) or "HEAD"]


def _is_tag(directory: Path, name: str) -> bool:
    return (
        _git(directory, "rev-parse", "-q", "--verify", f"refs/tags/{name}") is not None
    )


def _destination_kind(
    directory: Path, source: str, destination: str, explicit: bool
) -> str:
    """Classifies a push destination as "for", "branch", "tag" or "ref"."""
    if destination.startswith("refs/for/"):
        return "for"
    if destination.startswith("refs/heads/"):
        return "branch"
    if destination.startswith("refs/tags/"):
        return "tag"
    if destination.startswith("refs/"):
        return "ref"  # refs/meta/config, refs/changes/*, notes, ...
    if not destination or destination == "HEAD":
        return "branch"
    # git pushes a bare "<tag>" to refs/tags/<tag>; an unqualified
    # destination written after a colon is taken as a branch.
    if not explicit and _is_tag(directory, source):
        return "tag"
    return "branch"


def _chain(directory: Path, remote: str, branch: str, source: str) -> List[str]:
    base = f"refs/remotes/{remote}/{branch}"
    if _git(directory, "rev-parse", "-q", "--verify", base) is None:
        return []
    out = _git(
        directory,
        "log",
        "--reverse",
        "--no-show-signature",  # see _check_typed_change_ids
        "--format=%h %s",
        f"{base}..{source or 'HEAD'}",
    )
    return [line for line in (out or "").splitlines() if line]


def _configured_push_options(directory: Path) -> List[str]:
    """push.pushOption values, used when no -o is given; an empty one resets."""
    values: List[str] = []
    out = _git(directory, "config", "--get-all", "push.pushOption")
    for value in (out or "").split("\n"):
        values = values + [value] if value else []
    return values


# Push options that vote or submit on upload (%submit, %l=Code-Review+2, ...).
_REVIEW_BYPASS = re.compile(r"\s*(submit|merged|l|label)\s*(=|$)", re.IGNORECASE)


def check_push(invocation: GitInvocation, decision: Decision) -> None:
    if _ask_on_repository_override(invocation, decision):
        return
    directory = invocation.directory
    if invocation.config:
        decision.ask.append(
            f"git push with -c {', '.join(invocation.config)}: the guard checks "
            "the push against the repository's own config, which this "
            "overrides. Confirm the push."
        )
        return
    if any(
        _may_expand(a, "{?[")
        or ("*" in a and not a.startswith(("refs/", "+refs/", "HEAD")))
        for a in invocation.args
    ):
        decision.ask.append(
            "git push with a shell expansion in its arguments: the guard cannot "
            "tell where it pushes. Confirm the push."
        )
        return
    options = parse_push_args(invocation.args)
    remote = _push_remote(directory, options)
    if _git(directory, "config", "--bool", "--get", f"remote.{remote}.mirror") == (
        "true"
    ):
        options.all_branches = options.force = True
    allow_direct = (
        # Only the clone's own .git/config counts (no global, system or
        # included files), so the setting stays a per-clone choice.
        _git(
            directory,
            "config",
            "--local",
            "--bool",
            "--get",
            "gerrit-mcp.allowDirectPush",
        )
        == "true"
    )
    confirm = (
        _git(
            directory, "config", "--local", "--bool", "--get", "gerrit-mcp.confirmPush"
        )
        != "false"
    )

    for refspec in _push_refspecs(directory, remote, options):
        force = options.force or refspec.startswith("+")
        refspec = refspec.removeprefix("+")
        if options.delete:
            source, destination, explicit = "", refspec, True
        else:
            source, explicit, destination = refspec.partition(":")
            destination = destination or source
        destination, _, suffix = destination.partition("%")
        kind = _destination_kind(directory, source, destination, bool(explicit))

        if kind == "branch" and not allow_direct:
            branch = destination.removeprefix("refs/heads/")
            if branch in ("", "HEAD") or "*" in branch:
                branch = _current_branch(directory) or "<branch>"
            decision.deny.append(
                f"'git push {remote} {refspec}' pushes straight to branch "
                f"'{branch}' and bypasses Gerrit review. Push for review instead: "
                f"git push {remote} HEAD:refs/for/{branch}. Only the user can "
                "allow direct pushes, per clone (docs/claude-code.md, 'Git "
                "guard')."
            )
        if kind == "ref":
            decision.ask.append(
                f"'git push {remote} {refspec}' updates {destination} directly, "
                "outside review. Confirm the push; a change for review goes to "
                "refs/for/<branch>."
            )
        if kind != "for":
            continue

        branch = destination.removeprefix("refs/for/")
        if force:
            decision.deny.append(
                f"Force-pushing to refs/for/{branch} has no effect on Gerrit: a "
                "push to refs/for creates patch sets from the Change-Ids and "
                "never rewrites anything. Push without --force, -f or '+'."
            )
            continue
        chain = _chain(directory, remote, branch, source)
        pending = [
            line for line in chain if re.match(r"^\S+ (fixup|squash|amend)!", line)
        ]
        if pending:
            decision.deny.append(
                f"The chain to refs/for/{branch} still contains fixup commits "
                f"({'; '.join(pending)}); Gerrit would upload them as changes of "
                "their own. Squash them first: git -c sequence.editor=true rebase "
                f"-i --autosquash {remote}/{branch}"
            )
            continue

        push_options = suffix.split(",") if suffix else []
        push_options += options.push_options or _configured_push_options(directory)
        bypass = [o for o in push_options if _REVIEW_BYPASS.match(o)]
        if bypass:
            decision.deny.append(
                f"Push option {', '.join(bypass)} votes or submits on upload; "
                "votes and submit are the user's. Push without it."
            )
            continue
        if not confirm:
            continue
        topic = next((o for o in push_options if o.startswith("topic=")), None)
        reason = (
            f"Push {len(chain) or 'the'} change(s) to refs/for/{branch} on {remote}"
        )
        if chain:
            shown = chain[:10] + (
                [f"… {len(chain) - 10} more"] if len(chain) > 10 else []
            )
            reason += ":\n  " + "\n  ".join(shown)
        if topic:
            reason += (
                f"\nWith {topic}: if the server has submitWholeTopic enabled, every "
                "change in the topic is submitted together. Intended?"
            )
        decision.ask.append(reason)


_CONFIG_READ_ACTIONS = {"--get", "--get-all", "--get-regexp", "get"}
_CONFIG_READ_FLAGS = {
    "--local",
    "--global",
    "--system",
    "--worktree",
    "--bool",
    "--int",
    "--show-origin",
    "--show-scope",
    "--null",
    "-z",
    "--name-only",
}


def _is_plain_read(args: List[str]) -> bool:
    """`git config [flags] --get <key>`: one read action and only the key."""
    actions = [a for a in args if a in _CONFIG_READ_ACTIONS]
    others = [a for a in args if a not in _CONFIG_READ_ACTIONS]
    positional = [a for a in others if not a.startswith("-")]
    flags = [a for a in others if a.startswith("-")]
    return (
        len(actions) == 1
        and len(positional) == 1
        and all(f in _CONFIG_READ_FLAGS for f in flags)
    )


def _is_config_edit(args: List[str]) -> bool:
    """`git config edit`, `--edit` or an abbreviation of it, or `-e` in a bundle."""
    positional = [a for a in args if not a.startswith("-")]
    return (
        positional[:1] == ["edit"]
        or any(len(a) >= 3 and "--edit".startswith(a) for a in args)
        or any(re.match(r"^-[A-Za-z]*e", a) for a in args)
    )


# The guard's config section as a whole word, so "gerrit-mcp-server" in a path
# does not count.
_GUARD_SECTION = re.compile(r"gerrit-mcp(?![\w-])", re.IGNORECASE)


def _clone_config(args: List[str]) -> List[str]:
    """The key=value settings `git clone -c` writes into the new clone."""
    values = []
    for i, arg in enumerate(args):
        name, has_value, value = arg.partition("=")
        if arg == "-c" or (len(name) >= 6 and "--config".startswith(name)):
            if has_value:
                values.append(value)
            elif i + 1 < len(args):
                values.append(args[i + 1])
        elif arg.startswith("-c"):
            values.append(arg[2:])
    return values


def check_config(invocation: GitInvocation, decision: Decision) -> None:
    """Keeps the guard's own settings (gerrit-mcp.*) the user's to change."""
    args = invocation.args
    names_guard = any(
        _GUARD_SECTION.search(a) or ("gerrit" in a.lower() and _may_expand(a, "{*?["))
        for a in args
    )
    if (names_guard and not _is_plain_read(args)) or _is_config_edit(args):
        decision.deny.append(
            "gerrit-mcp.* settings relax the git guard, so only the user changes "
            "them, and git config --edit can change them without naming them. "
            "Ask the user to run the git config command themselves."
        )
        return
    if any(_may_expand(a, "{*?[") for a in args):
        decision.ask.append(
            "git config with a shell expansion in its arguments: the guard "
            "cannot tell which setting it changes. Confirm the command."
        )


def evaluate(payload: Dict) -> Decision:
    """Applies the guard rules to a PreToolUse payload of the Bash tool."""
    decision = Decision()
    command = (payload.get("tool_input") or {}).get("command") or ""
    cwd = payload.get("cwd")
    if "git" not in command or not cwd:
        return decision
    _, heredocs = split_heredocs(command)
    try:
        invocations = find_git_invocations(command, Path(cwd))
    except ValueError:
        return decision
    for invocation in invocations:
        settings = list(invocation.config)
        if invocation.verb == "clone":
            settings += _clone_config(invocation.args)
        if invocation.verb != "config" and any(
            _GUARD_SECTION.search(s) for s in settings
        ):
            decision.deny.append(
                "gerrit-mcp.* settings relax the git guard, so only the user "
                "changes them."
            )
            continue
        if invocation.verb in ("send-pack", "http-push"):
            decision.ask.append(
                f"git {invocation.verb} sends refs without the push checks. "
                "Confirm the command; a change for review goes to refs/for/<branch>."
            )
            continue
        if invocation.verb == "config":
            # Checked in every repository: a global or system setting could
            # otherwise be written from anywhere.
            check_config(invocation, decision)
            continue
        if invocation.verb not in ("commit", "push"):
            continue
        if not invocation.directory.is_dir() or not is_gerrit_repo(
            invocation.directory
        ):
            continue
        if invocation.verb == "commit":
            check_commit(invocation, heredocs, decision)
        else:
            check_push(invocation, decision)
    return decision


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        output = evaluate(payload).to_hook_output()
    except Exception:  # never block git because the guard itself failed
        output = None
    if output:
        print(json.dumps(output))
    sys.exit(0)
