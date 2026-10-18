# Relation Chains

A relation chain is a series of commits on one branch, each its own change,
linked by their parents. Every commit in `origin/master..HEAD` is a future
change, pushed or not, so each must be reviewable on its own.

## One Concern per Change

Plan the cut with the `stack-planner` skill. A commit belongs in the chain when
it:

- states one behaviour or one mechanical transformation, with no "and";
- builds and passes with only the earlier commits present;
- carries its tests;
- is used: no class without a caller, no "part 1/2";
- can be reverted without breaking its neighbours.

A mechanical change (rename, migration, formatter run) is one change however
large; say "mechanical" and how it was produced in the message. Never bundle
concerns to shorten the chain.

Verify every commit on its own before pushing, and after any rewrite:

```bash
git -c sequence.editor=true rebase -i --exec '<verify command>' origin/master
```

At a failure: fix, `git add <paths>`, `git commit --amend --no-edit`,
`git rebase --continue`.

## Change-Id

The `commit-msg` hook adds it. Never type one, never copy one from another
change, never commit with `--no-verify`. A commit without one: install the hook,
then `git commit --amend --no-edit`.

Exception: re-applying the Change-Id that Gerrit already shows for **this**
change, after the commit was recreated.

List the Change-Ids, oldest first; every row has exactly one:

```bash
git log --reverse --format='%h %(trailers:key=Change-Id,valueonly,separator=%x2C) %s' origin/master..HEAD
```

## Amending

| Goal           | Command                                                                          |
| -------------- | -------------------------------------------------------------------------------- |
| Change code    | `git commit --amend --no-edit`                                                   |
| Change message | `git log -1 --format=%B > <file>`, edit `<file>`, `git commit --amend -F <file>` |
| Never          | `git commit --amend -m <msg>`: drops the Change-Id, so Gerrit opens a new change |

Keep the `Change-Id` line in `<file>`. A bare `git commit --amend` opens an
editor and hangs the shell.

## Commit Messages

Follow the commit conventions the repository documents in `AGENTS.md`,
`CLAUDE.md` or `CONTRIBUTING`, including any check they name: run it over the
chain before pushing and reword failing commits, keeping each `Change-Id` line.
Without documented conventions, match `git log --format=%s -20`.

## Editing a Middle Change

```bash
git add <paths>
git commit --fixup=<sha>
git -c sequence.editor=true rebase -i --autosquash origin/master
```

Not `--fixup=amend:` or `--fixup=reword:`: they open an editor.

Reword a middle commit:

```bash
git -c sequence.editor="perl -pi -e 's/^pick <sha7> /edit <sha7> /'" rebase -i origin/master
git log -1 --format=%B > <file>   # edit <file>, keep the Change-Id line
git commit --amend -F <file>
git rebase --continue
```

After the rewrite, the Change-Id list must match the one from before, and every
commit must pass the verify command again.

## Re-push the Whole Chain

After editing any commit, push the whole chain; unchanged commits get no new
patch set:

```bash
git push origin HEAD:refs/for/master
```

To land the bottom of the chain first, push only up to `<sha>`:
`git push origin <sha>:refs/for/master`.

## Grouping Is Opt-in

Default: none. Add a hashtag or topic only when the user asks, or the
repository's `AGENTS.md`, `CONTRIBUTING` or `CLAUDE.md` says so.

| Grouping        | At push time                        | After the push                                  |
| --------------- | ----------------------------------- | ----------------------------------------------- |
| hashtag `<tag>` | `HEAD:refs/for/master%t=<tag>`      | `set_hashtags(change_id, add=[...])` per change |
| topic `<name>`  | `HEAD:refs/for/master%topic=<name>` | `set_topic(change_id, topic)` per change        |

With `submitWholeTopic` a topic submits all its changes at once; say so when a
topic is chosen.

## Rebasing

```bash
git fetch origin
git rebase origin/master
```

Then check the Change-Id list, verify every commit, and re-push.

## Status on the Server

- `get_related_changes(change_id=<newest change>)`: the chain with status and
  patch sets.
- `changes_submitted_together(change_id=<change>)`: what submits with it.

Votes and submit are the user's.
