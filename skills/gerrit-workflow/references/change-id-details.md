# Change-Id: Deep Dive

## What Is a Change-Id?

A `Change-Id` is a SHA-1-like identifier prefixed with `I` (uppercase i), placed
as a git trailer in the commit message footer. Example:

```
Fix the foo widget

We want a bar, because it improves the foo by providing more
wizbangery to the dowhatimeanery.

Bug: #42
Change-Id: Ic8aaa0728a43936cd4c6e1ed590e01ba8f0fbf5b
Signed-off-by: A. U. Thor <author@example.com>
```

The `Change-Id` must be in the **last paragraph** of the commit message (the
"footer"). It can coexist with `Signed-off-by`, `Acked-by`, `Bug:`, `Fixes:`,
etc.

## How the commit-msg Hook Creates Change-Ids

The hook creates a virtual git commit object from the tree SHA, parent SHA,
author info, committer timestamp, and the proposed message. The SHA-1 of that
virtual object becomes the `Change-Id`. Because the committer timestamp and
parent SHA are included, the same message on two different commits produces two
different Change-Ids.

The hook **does nothing** if a `Change-Id` line is already present in the
footer.

## When to Keep the Same Change-Id

Keep the existing `Change-Id` unchanged when:

- **Amending a commit** to address review feedback — this adds a new patch set
  to the existing change.
- **Rebasing a commit** — git preserves trailers through rebase automatically.
- **Cherry-picking to the same branch** with the intention of updating the same
  review.
- **Updating the commit message** for any reason (spelling fix, adding a
  `Signed-off-by`, etc.).

## When to Generate a New Change-Id

Delete the `Change-Id` line (or the entire trailer) and let the hook regenerate
a fresh one when:

- **Backporting** to a different branch — the backport is a separate change on a
  separate branch.
- **Starting a completely new change** from an existing commit that happened to
  have a Change-Id.
- You want to split one change into two separate reviews.

To force a new `Change-Id` on an existing commit:

```bash
git commit --amend   # remove the Change-Id line, save
# hook runs and inserts a new Change-Id
git log -1           # verify the new Change-Id
```

## Squashing Commits

When squashing two or more commits that each have a `Change-Id`, keep exactly
**one**:

1. Prefer the one already uploaded to Gerrit (someone may have left comments on
   it).
2. If both were uploaded, keep either — then abandon the orphaned change in the
   Gerrit web UI.
3. If neither was uploaded, keep any one and delete the rest.

Interactive rebase example:

```bash
git rebase -i origin/master
# Mark commits as "squash" or "fixup"
# In the resulting commit message editor:
#   Keep ONE Change-Id line, delete the others
```

## The Link Footer Alternative

Some projects (e.g., the Linux kernel) use a `Link` footer instead of
`Change-Id`:

```
Link: https://gerrit-review.googlesource.com/id/Ic8aaa0728a43936cd4c6e1ed590e01ba8f0fbf5b
```

The hook generates this style when `gerrit.reviewUrl` is set in the git config:

```bash
git config gerrit.reviewUrl https://gerrit-review.googlesource.com/
```

Gerrit recognizes both styles. The base URL in the `Link` footer must match the
server's configured base URL.

## Disabling Change-Id Generation

To prevent the hook from adding a `Change-Id` (e.g., for fixup or squash
commits):

```bash
git config gerrit.createChangeId false
```

Or, create a commit whose subject begins with a lowercase word followed by `!`
(e.g., `nopush!`).

To force insertion even for such commits:

```bash
git config gerrit.createChangeId always
```

## Diagnosing Change-Id Problems

Check whether a commit has a `Change-Id`:

```bash
git log -1 --format='%B' | grep '^Change-Id:'
```

Check if the Change-Id is in the footer (last paragraph), not the body:

```bash
# The footer is separated from the body by a blank line.
# If Change-Id appears before the last blank-line-delimited paragraph, Gerrit rejects it.
git log -1 --format='%B'
```

Fix a `Change-Id` that landed in the wrong place:

```bash
git commit --amend
# Move the Change-Id line to the very end of the message (after a blank line)
```

## Uniqueness and Scope

A `Change-Id` is unique per (repository, branch) combination. The same
`Change-Id` **can** appear on different branches (e.g., when a commit is
cherry-picked to a maintenance branch). Gerrit distinguishes them by repository
and branch, so there is no conflict.
