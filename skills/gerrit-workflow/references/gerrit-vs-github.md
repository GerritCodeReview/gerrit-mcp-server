# Gerrit vs GitHub/GitLab: Workflow Comparison

This reference maps common GitHub/GitLab operations to their Gerrit equivalents.

## Creating a Change for Review

| GitHub/GitLab               | Gerrit                                                    |
| --------------------------- | --------------------------------------------------------- |
| Push a branch, open a PR/MR | Push commits to `refs/for/<branch>`                       |
| `git push origin my-branch` | `git push origin HEAD:refs/for/master`                    |
| Open PR in the web UI       | Gerrit change is created automatically on push            |
| Branch stays in the remote  | No branch is created; the change lives in `refs/changes/` |

## Updating a Change

| GitHub/GitLab                      | Gerrit                                                        |
| ---------------------------------- | ------------------------------------------------------------- |
| Push more commits to the PR branch | Amend the commit, push to `refs/for/<branch>` again           |
| Force-push the branch              | `git commit --amend` + `git push origin HEAD:refs/for/master` |
| PR is updated with new commits     | Gerrit adds a new patch set to the same change                |

**Critical difference:** GitHub tracks changes by branch name; Gerrit tracks
them by `Change-Id` trailer in the commit message. Changing the `Change-Id`
creates an entirely new change.

## Merging / Submitting

| GitHub/GitLab                        | Gerrit                                                                   |
| ------------------------------------ | ------------------------------------------------------------------------ |
| Merge button in the web UI           | Submit button in the Gerrit web UI (after approvals)                     |
| Merge commit or squash merge         | Configured per-project (fast-forward, merge, rebase, cherry-pick)        |
| PR branch can be deleted after merge | No branch to delete — the commit lands directly in `refs/heads/<branch>` |

## Reviewing Others' Work

| GitHub/GitLab                  | Gerrit                                                                |
| ------------------------------ | --------------------------------------------------------------------- |
| Fetch the PR branch            | `git fetch origin refs/changes/45/12345/3 && git checkout FETCH_HEAD` |
| Comment on lines in the UI     | Same in Gerrit's web UI                                               |
| "Approve" or "Request changes" | Vote on labels (e.g., `Code-Review +2` to approve, `-2` to block)     |

## Fetching the Latest Branch

```bash
# Same in both:
git fetch origin
git rebase origin/master
```

## Working With Multiple Changes

**GitHub/GitLab:** A PR can have many commits; reviewers see all of them.

**Gerrit:** Each commit is its own change. For a feature that spans multiple
commits:

- Each commit gets its own change number and is reviewed independently.
- The relation chain is shown in the Gerrit UI.
- Changes can be submitted individually or together (via topics).

## Topics (Grouping Related Changes)

Gerrit topics group related changes across one or more repositories:

```bash
git push origin HEAD:refs/for/master%topic=my-feature-name
```

Changes with the same topic appear together in search results and the "Submitted
Together" section of the review screen.

## No Pull, No Merge Commits From Branches

In a Gerrit workflow:

- **Don't** create merge commits to incorporate remote changes — rebase instead.
- **Don't** create long-lived feature branches — each change is a single commit.
- **Don't** `git pull` (which merges) — use `git fetch` + `git rebase`.

```bash
# Update your local work on top of origin:
git fetch origin
git rebase origin/master

# If you have a stacked series:
git rebase origin/master  # rebases the whole stack; Change-Ids are preserved
git push origin HEAD:refs/for/master  # updates all changes in the stack
```
