"""SessionStart hook: tells the model the chain rules, in Gerrit repositories only.

The skills that carry these rules are invoked by their descriptions, which match
requests such as "push for review" or "break this down" but not a plain "add a
flag" or "commit it". This context names the skills and the rules up front so
the model reaches for them on any change. Outside a Gerrit repository it prints
nothing.

Stdlib only, always exits 0, like the git guard.
"""

import json
import sys
from pathlib import Path
from typing import Optional

from gerrit_mcp_server.git_guard import _git, has_change_id_hook, is_gerrit_repo

_CONVENTION_DOCS = ("AGENTS.md", "CONTRIBUTING.md", "CONTRIBUTING", "CLAUDE.md")

RULES = (
    "This repository is reviewed on Gerrit. For any change that touches more "
    "than one file, invoke the gerrit-workflow skill and plan the chain with "
    "the stack-planner skill before editing: one concern per commit, each with "
    "the Change-Id the commit-msg hook adds. Push the chain to "
    "refs/for/<branch> only after the user confirms. For review feedback, use "
    "the gerrit-review skill.\n"
    "Even if the user asks otherwise: never write a Change-Id trailer, never "
    "use --no-verify or --amend -m, never push to refs/heads/*. Say why in one "
    "sentence and do it the supported way; the git guard denies these commands "
    "anyway."
)


def context_for(directory: Path) -> Optional[str]:
    """The context for a session started in a directory, None outside Gerrit."""
    if not directory.is_dir() or not is_gerrit_repo(directory):
        return None
    lines = [RULES]
    if not has_change_id_hook(directory):
        lines.append(
            "The commit-msg hook is not installed: install it before the first "
            "commit (gerrit-workflow skill)."
        )
    toplevel = _git(directory, "rev-parse", "--show-toplevel")
    docs = [
        name
        for name in _CONVENTION_DOCS
        if toplevel and (Path(toplevel) / name).is_file()
    ]
    if docs:
        listed = ", ".join(docs)
        lines.append(
            f"Commit and review-comment conventions of this repository: {listed}."
        )
    return "\n".join(lines)


def main() -> None:
    try:
        cwd = json.load(sys.stdin).get("cwd")
        text = context_for(Path(cwd)) if cwd else None
    except Exception:  # a broken context must never break the session
        text = None
    if text:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": text,
                    }
                }
            )
        )
    sys.exit(0)
