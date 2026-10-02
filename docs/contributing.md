# How to contribute

We'd love to accept your patches and contributions to this project.

## Before you begin

### Sign our Contributor License Agreement

Contributions to this project must be accompanied by a
[Contributor License Agreement](https://cla.developers.google.com/about) (CLA).
You (or your employer) retain the copyright to your contribution; this simply
gives us permission to use and redistribute your contributions as part of the
project.

If you or your current employer have already signed the Google CLA (even if it
was for a different project), you probably don't need to do it again.

Visit <https://cla.developers.google.com/> to see your current agreements or to
sign a new one.

### Review our community guidelines

This project follows
[Google's Open Source Community Guidelines](https://opensource.google/conduct/).

## Contribution process

### Code style

This project uses `ruff` for linting and formatting. Before submitting, ensure
your changes pass:

```bash
uv run ruff check .    # lint
uv run ruff format .   # format
```

### Code reviews

All submissions, including submissions by project members, require review.

### Submit changes through Gerrit

The canonical repository is
[`gerrit.googlesource.com/gerrit-mcp-server`](https://gerrit.googlesource.com/gerrit-mcp-server).
This project does not accept GitHub pull requests. Submit changes through Gerrit
for review instead. Clone the canonical repository and install Gerrit's
`commit-msg` hook before creating your first commit:

```bash
git clone https://gerrit.googlesource.com/gerrit-mcp-server
cd gerrit-mcp-server
curl -Lo .git/hooks/commit-msg https://gerrit-review.googlesource.com/tools/hooks/commit-msg
chmod u+x .git/hooks/commit-msg
```

If you already cloned the GitHub mirror, point `origin` at Gerrit before pushing
and install the hook as shown above:

```bash
git remote set-url origin https://gerrit.googlesource.com/gerrit-mcp-server
```

The hook adds the required `Change-Id` trailer to commit messages. Keep this
trailer unchanged when amending a commit to upload another patch set of the same
change. If your commit predates the hook installation, run
`git commit --amend --no-edit` to add the trailer.

Before your first push, visit <https://gerrit.googlesource.com/new-password> and
sign in with the Google account you use for Gerrit. Follow the instructions on
that page to configure Git's authentication credentials. Keep these credentials
private; do not commit them to the repository.

Create a branch, make and stage your changes, then commit and push for review:

```bash
git checkout -b <your-feature-branch>
git commit -m "Your descriptive commit message"
git push origin HEAD:refs/for/master
```

Direct pushes to `master` are not permitted. See the
[development guide](../AGENTS.md) for local setup and testing instructions.
