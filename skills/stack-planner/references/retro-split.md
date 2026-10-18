# Retro-split

Turns an uncommitted worktree, or one commit mixing concerns, into one commit
per concern with the same final tree. Never write a `Change-Id`; never
`--amend -m`, `--no-verify` or `git add -p` (interactive). `--hard` only in the
recovery step.

## 1. Snapshot

Uncommitted worktree:

```bash
git add -A                 # stash create sees untracked files only in the index
git stash create           # prints <orig>; HEAD, index and files are unchanged
git reset
git tag retro-split/orig <orig>
git rev-parse HEAD         # <base>
```

Not `git add -N`: `git stash create` rejects intent-to-add entries. Go to step
3\.

A mixed commit:

```bash
git tag retro-split/orig HEAD
git rev-parse HEAD~1       # <base>
```

## 2. Move HEAD Back

```bash
git reset <base>           # changes stay in the worktree, unstaged
```

## 3. One Commit per Concern, in Plan Order

```bash
git add <path>...
git diff --cached --stat
git commit -F <msg-file>   # never a bare `git commit`: the editor hangs
```

For a file shared between concerns, copy this concern's hunks from
`git diff -- <path>` into a patch file (keep the `diff --git`, `---`, `+++`
headers; stale `@@` counts are fine), then:

```bash
git apply --cached --recount <patch-file>
git diff --cached -- <path>
```

## 4. Verify Each Commit

```bash
git -c sequence.editor=true rebase -i --exec '<verify cmd>' <base>
```

At a failure: fix, `git add <path>...`, `git commit --amend --no-edit`,
`git rebase --continue`. A fix that belongs to another commit:
`git commit --fixup=<sha>`, then
`git -c sequence.editor=true rebase -i --autosquash <base>`.

## 5. Prove Equivalence

```bash
git status --porcelain                   # empty
git diff retro-split/orig..HEAD --stat   # empty: same tree as the original
git tag -d retro-split/orig
```

If the diff is not empty: leftover worktree lines go in with `--fixup` and
autosquash; a wrong hand-cut hunk means `git reset --hard retro-split/orig` and
start again at step 2.

## A Commit Already Pushed

- **New chain (default):** split as above; every commit becomes a new change.
  Write `Supersedes change <number>` in the commit carrying the original
  behaviour; the user abandons the old change.
- **Keep the change as the tip:** commit the other concerns fresh, then the last
  one with `git commit -C retro-split/orig`, which keeps the original message
  and `Change-Id`. Explain what moved in a review reply.

Either way, push the whole chain.
