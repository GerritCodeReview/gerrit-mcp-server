# Change Size

Size warns when a change asks more of a reviewer than one sitting; it never
decides where to cut.

| Setting                 | Default | Over it                                             |
| ----------------------- | ------- | --------------------------------------------------- |
| Production-line warning | 400     | one-line justification in the commit message        |
| Hard cap                | none    | cut along concern boundaries only, or raise the cap |

Teams set other values in `AGENTS.md`, `CONTRIBUTING` or `CLAUDE.md`.

## Counting

Production lines are insertions + deletions in files that are neither:

- **tests**: a `test/` or `tests/` path component; `*Test.*`, `*_test.*`,
  `test_*.*`, `*.spec.*`;
- **docs or lock files**: `*.md`, `*.rst`, `*.txt`, a `docs/` or
  `Documentation/` component; `*.lock`, `package-lock.json`, `go.sum`.

```bash
git diff --numstat --cached          # the next commit
git diff --numstat HEAD              # everything uncommitted
git show --numstat --format= <rev>   # one commit
```

For a plan, estimate new files and the hunks of existing ones; `wc -l` of an
existing file is only an upper bound.

## Evidence

- SmartBear/Cisco: one reviewer reads 200–400 lines per sitting well; defect
  detection drops beyond that. This is the source of the 400.
  https://smartbear.com/learn/code-review/best-practices-for-peer-code-review/
- Google (median change 24 lines) and Graphite (~50-line PRs merge fastest) are
  medians over all changes, not targets.
  https://research.google/pubs/modern-code-review-a-case-study-at-google/ ·
  https://graphite.com/blog/the-ideal-pr-is-50-lines-long
