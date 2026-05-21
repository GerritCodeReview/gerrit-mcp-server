---
name: gerrit-workflow
description: This skill should be used when the user asks to "submit a change to Gerrit", "push for review", "upload a patch", "update a change in Gerrit", "add a patch set", "work with Gerrit", "push to refs/for", "fix a missing Change-Id", "amend a Gerrit change", or any task involving git operations in a repository hosted on Gerrit Code Review. Also use when the user encounters Gerrit push errors such as "missing Change-Id in commit message footer" or "prohibited by Gerrit".
allowed-tools: Bash, Read
---

# Gerrit Workflow

Gerrit is a code review system that sits in front of a git repository. The key
difference from GitHub/GitLab: **changes go through a review queue before
landing in the branch**. This changes several git workflows in important ways.

## Core Concepts

### Changes and Patch Sets

A **Change** is the unit of review in Gerrit — it corresponds to one logical
commit. Each change has:

- A numeric **Change number** (e.g., `12345`)
- A **Change-Id** trailer in the commit message (e.g.,
  `Change-Id: Ic8aaa0728a43936cd4c6e1ed590e01ba8f0fbf5b`)

When a commit is revised and re-uploaded, the new version becomes a new **patch
set** on the same change. Gerrit associates them via the `Change-Id` trailer —
this is what makes the `Change-Id` essential.

### The Magic `refs/for/<branch>` Ref

Gerrit intercepts pushes to `refs/for/<branch>`. These pushes never actually
create that ref; instead Gerrit creates or updates a Change for review. To land
code in `master`:

```
# NOT this (bypasses review):
git push origin HEAD:refs/heads/master

# This — submits for review:
git push origin HEAD:refs/for/master
```

### The commit-msg Hook

Gerrit provides a `commit-msg` hook that auto-inserts `Change-Id` trailers.
Without it, the `Change-Id` must be added manually. To install:

```bash
# Via curl (HTTP):
curl -Lo .git/hooks/commit-msg <gerrit-url>/tools/hooks/commit-msg
chmod u+x .git/hooks/commit-msg

# Via scp (SSH):
scp -p -P 29418 <user>@<gerrit-host>:hooks/commit-msg .git/hooks/
chmod u+x .git/hooks/commit-msg
```

Check if it is already installed:

```bash
ls -la .git/hooks/commit-msg
```

## Common Workflows

### 1. Create a New Change

```bash
# Make changes, then commit (hook adds Change-Id automatically)
git add <files>
git commit -m "Fix the foo widget"

# Verify Change-Id was added:
git log -1

# Push for review against a target branch:
git push origin HEAD:refs/for/master
```

The server prints the URL of the new change.

### 2. Update an Existing Change (New Patch Set)

After receiving review feedback, amend the commit. **Do not modify or remove the
`Change-Id` line** — Gerrit uses it to associate the new commit with the
existing change.

```bash
# Edit files, then:
git add <files>
git commit --amend   # keep Change-Id unchanged in the editor

# Push again — Gerrit creates patch set 2 on the same change:
git push origin HEAD:refs/for/master
```

### 3. Work on Multiple Independent Changes

Each change should be its own commit on its own local branch:

```bash
git checkout -b fix-foo origin/master
# make change A, commit, push for review

git checkout -b fix-bar origin/master
# make change B, commit, push for review
```

Do not stack unrelated changes on a single branch unless they are intentionally
dependent (see below).

### 4. Dependent / Stacked Changes

Gerrit supports chains of dependent changes. Push multiple commits in one push;
Gerrit creates one change per commit, linked in a relation chain:

```bash
git checkout -b feature origin/master
git commit -m "Step 1: add plumbing"       # Change-Id: I111...
git commit -m "Step 2: wire up the UI"     # Change-Id: I222...
git push origin HEAD:refs/for/master       # creates two linked changes
```

Each change can be reviewed and submitted independently, but Gerrit shows the
dependency chain.

### 5. Rebase and Re-push

When the target branch has moved on, rebase and re-push. Keep Change-Ids intact:

```bash
git fetch origin
git rebase origin/master   # Change-Ids are preserved automatically
git push origin HEAD:refs/for/master
```

### 6. Squashing Commits Before Push

When squashing several commits, keep exactly **one** `Change-Id` — prefer the
one already known to Gerrit (i.e., the one that was previously pushed, if any).
Remove the others:

```bash
git rebase -i origin/master   # squash commits
# In the resulting commit message, delete all but one Change-Id line
git push origin HEAD:refs/for/master
```

### 7. Cherry-pick to Another Branch

To propose the same fix on a maintenance branch, cherry-pick and **generate a
new Change-Id** (delete the old one so the hook creates a fresh one):

```bash
git checkout -b backport-3.10 origin/stable-3.10
git cherry-pick <commit-sha>
git commit --amend   # delete the Change-Id line; save
# hook regenerates a new Change-Id
git push origin HEAD:refs/for/stable-3.10
```

Or, keep the original Change-Id to have Gerrit treat it as a replacement for the
same change on that branch.

## Push Options

Additional metadata can be sent with the push via `%` options or `-o`:

```bash
# Add a topic (groups related changes):
git push origin HEAD:refs/for/master%topic=my-feature

# Request specific reviewers:
git push origin HEAD:refs/for/master%r=alice@example.com,cc=bob@example.com

# Mark as work-in-progress:
git push origin HEAD:refs/for/master%wip

# Mark ready for review:
git push origin HEAD:refs/for/master%ready

# Apply a review label on push:
git push origin HEAD:refs/for/master%l=Verified+1

# Suppress notifications:
git push origin HEAD:refs/for/master%notify=NONE

# Combine options with commas:
git push origin HEAD:refs/for/master%topic=my-feature,r=alice@example.com
```

## Fetching Changes

To check out an existing change locally (e.g., to test it):

```bash
# The change page shows a "Download" command; it looks like:
git fetch origin refs/changes/45/12345/3 && git checkout FETCH_HEAD

# Where: refs/changes/<last-two-digits-of-change-num>/<change-num>/<patch-set>
```

## Common Errors and Fixes

### `missing Change-Id in commit message footer`

The commit has no `Change-Id`. Fix:

```bash
# If hook is installed, amend will add it:
git commit --amend --no-edit

# If hook is NOT installed, add it manually:
# Copy the Change-Id from the Gerrit web UI change page, then:
git commit --amend   # paste "Change-Id: I..." into the footer
```

### `! [remote rejected] ... (prohibited by Gerrit)`

Direct push to `refs/heads/*` was rejected. Push to `refs/for/<branch>` instead.

### `Change xxx: patch set already exists`

The commit hash hasn't changed since the last push (no new patch set was made).
Amend the commit to create a distinct object, then push again.

### `! [remote rejected] ... (no new changes)`

All commits being pushed are already known to Gerrit. This often means the
branch is already up to date with the target.

## Critical Rules

- **Never push directly to `refs/heads/*`** unless intentionally bypassing
  review (requires special permissions).
- **Never change or remove the `Change-Id` trailer** when amending a commit that
  is already under review — doing so creates a second, orphaned change.
- **One logical change = one commit.** Gerrit reviews commits, not branches.
- **Always verify `Change-Id` is present** with `git log -1` before pushing.
- **Keep Change-Ids when rebasing** — git preserves them through rebase
  automatically.

## Additional Resources

- **`references/gerrit-vs-github.md`** — Side-by-side comparison of Gerrit and
  GitHub/GitLab workflows for common tasks
- **`references/change-id-details.md`** — Deep dive on Change-Id: creation,
  squashing, cherry-picks, and edge cases
