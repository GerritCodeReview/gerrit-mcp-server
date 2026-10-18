# Claude Code Configuration

You can use this MCP server with [Claude Code](https://claude.com/claude-code),
allowing you to interact with Gerrit directly from your terminal. This
repository ships as an installable **Claude Code plugin**.

## Claude Code Plugin

The plugin is defined by two files in the repository root:

- `.claude-plugin/plugin.json`: the plugin manifest (name and description)
  required by the Claude Code plugin system.

- `.mcp.json`: the MCP server configuration. It launches the server on-demand
  with `uv` and uses `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` so
  paths resolve correctly wherever the plugin is installed:

  ```json
  {
    "mcpServers": {
      "gerrit": {
        "command": "uv",
        "args": ["run", "--directory", "${CLAUDE_PLUGIN_ROOT}", "gerrit-mcp-server"],
        "env": {
          "UV_PROJECT_ENVIRONMENT": "${CLAUDE_PLUGIN_DATA}/.venv"
        }
      }
    }
  }
  ```

### Install from the marketplace

Register the Gerrit plugin marketplace and install the plugin:

```
/plugin marketplace add https://gerrit.googlesource.com/gerrit-mcp-server
/plugin install gerrit@gerrit-mcp
```

### Load locally

Load the plugin locally by pointing Claude Code at the project directory:

```bash
claude --plugin-dir <path-to-gerrit-mcp-server>
```

Because the server is launched with `uv run`, `uv` automatically creates the
environment at `${CLAUDE_PLUGIN_DATA}/.venv` and installs dependencies on first
launch. There is no need to run `./build-gerrit.sh` separately for the plugin.

The plugin starts the server on-demand, so no separate background process is
required. Once loaded, you can use the `gerrit` tools directly from `claude`.

## Prerequisites

Users must [configure](../README.md#3_configure-the-server) the server with the
`gerrit_config.json` file.

## Setup diagnostics

A `SessionStart` hook (`hooks/check-config.sh`, registered in
`hooks/hooks.json`) checks the server environment and configuration at the start
of every session, so a broken setup surfaces with clear guidance instead of MCP
tools failing silently.

The hook runs the `gerrit-check-config` console script, whose exit code reports
the setup state:

- `0`: config is valid — the hook stays quiet and reports that the tools are
  available.
- `1`: config file is missing — the normal first-run state. The hook asks the
  user to run `/gerrit:setup`.
- `2`: config is present but invalid (bad JSON or `default_gerrit_base_url`
  mismatch) — the hook asks the user to run `/gerrit:setup` to repair it.
- any other non-zero code: the Python environment is not built. The hook offers
  the exact `build-gerrit.sh` command to rebuild it.

It also warns when the git guard's console script is missing after the sync, as
the guard would otherwise do nothing without a word.

The hook emits JSON with a `systemMessage` (shown to the user) and
`additionalContext` (telling the model what to do), because `SessionStart`
stdout goes to the model's context rather than the user's terminal.

## Git guard

A `PreToolUse` hook (`hooks/git-guard.sh`) checks the `git` commands the model
runs in a Gerrit repository: one with a `.gitreview`, a remote on a host from
`gerrit_config.json`, or the Gerrit `commit-msg` hook. Elsewhere it does
nothing.

| Command                                                                              | Decision |
| ------------------------------------------------------------------------------------ | -------- |
| `git commit --no-verify`, without the `commit-msg` hook, or with `-c core.hooksPath` | deny     |
| `git commit` with a hand-written `Change-Id:` trailer                                | deny     |
| `git commit --amend -m`                                                              | deny     |
| `git commit --amend -F <file>` where the file has no `Change-Id`                     | deny     |
| `git commit --amend -F` with a heredoc `Change-Id` other than HEAD's                 | deny     |
| `git commit --amend -F` with a heredoc `Change-Id` equal to HEAD's (adds a note)     | allow    |
| `git push` to `refs/heads/*` or a bare branch name                                   | deny     |
| `git push --force` to `refs/for/*`                                                   | deny     |
| `git push` to `refs/for/*` with `fixup!`/`squash!` commits in the chain              | deny     |
| `git push` with a push option that votes or submits (`l=`, `submit`, `merged`)       | deny     |
| any other `git push` to `refs/for/*`; it lists the changes being pushed              | ask      |
| `git push` to another ref (`refs/meta/config`, ...), or with `-c` overrides          | ask      |
| `git config` writing a `gerrit-mcp.*` key                                            | deny     |

It sees through wrappers (`env`, `bash -c`), git aliases and abbreviated
options, and asks when `--git-dir`, `GIT_DIR` or `GIT_CONFIG_*` point git
elsewhere. It is a safety net, not a security boundary; enforce policy with
Gerrit's access rules. It allows what it cannot parse, and it does not see file
edits made outside the Bash tool, nor git commands run by git itself
(`git submodule foreach`, `git subtree push`). Change-Id checks on push are left
to Gerrit.

To allow direct pushes in one clone, run
`git config gerrit-mcp.allowDirectPush true` yourself. To push to `refs/for/*`
without the confirmation, for automation, run
`git config gerrit-mcp.confirmPush false`. Only the clone's `.git/config` counts
for either.

## `/gerrit:setup` skill

`skills/setup/SKILL.md` provides an interactive `/gerrit:setup` skill that
guides the user through creating or updating
`gerrit_mcp_server/gerrit_config.json`. The exit-code 1 and 2 states above ask
the user to run it. See
[Interactive Setup](configuration.md#interactive-setup-gerritsetup) in the
configuration guide for details.

## `gerrit-workflow` skill

`skills/gerrit-workflow/SKILL.md` drives the git side of Gerrit: pushing to
`refs/for/<branch>`, amending without losing the `Change-Id`, relation chains,
and common push errors. Claude Code invokes it automatically.

For relation chains, pushed or not: one concern per change, `Change-Id` from the
hook only, amend with `--no-edit` or `-F`, re-push the whole chain after editing
any change in it. Hashtags and topics only when you ask, or the repository's
`AGENTS.md`, `CONTRIBUTING` or `CLAUDE.md` says so.

Commit messages follow the conventions documented there, including any check
they name, for example:

```markdown
## Commit conventions

Subjects follow Conventional Commits. Before pushing, check the chain with
`npx commitlint --from origin/master --to HEAD`.
```

References: `relation-chains.md` (chain recipes), `gerrit-vs-github.md`,
`change-id-details.md`.

## `stack-planner` skill

`skills/stack-planner/SKILL.md` splits work into an ordered chain of changes,
one concern each, every one building and tested on its own, and stops until you
approve the plan.

- How fine to cut is a judgement call the plan states.
- Above ~400 production lines (tests and docs not counted) a change needs a
  one-line justification; it is never split only to get under the number. Set
  other values in `AGENTS.md`, `CONTRIBUTING` or `CLAUDE.md`.
- Mechanical changes (rename, migration, formatter) stay one change.
- Retro-split turns a commit or worktree that mixes concerns into one commit per
  concern, proven equal to the original by an empty `git diff`.

It works for Gerrit relation chains and stacked GitHub PRs alike. References:
`plan-template.md`, `split-patterns.md`, `retro-split.md`, `budget.md`.

## `gerrit-review` skill

`skills/gerrit-review/SKILL.md` answers review threads on your change or chain:
it lists unresolved threads, drafts the whole batch of replies, and posts them
only after you approve the batch, as threaded drafts with one `publish_drafts`
per change. The preview lists drafts already on each change, since they are
published too. It never votes, submits or changes WIP state.

Comments follow the review-comment convention your `AGENTS.md`, `CLAUDE.md` or
`CONTRIBUTING` documents, for example
[Conventional Comments](https://conventionalcomments.org); otherwise plain
sentences.
