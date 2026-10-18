---
name: stack-planner
description: Split a feature, refactor, or bugfix into an ordered chain of single-concern changes, each building and tested on its own. Size is a reviewer-load warning on production lines, not a quota; mechanical changes (rename, migration, formatter, codemod) stay one change. Use before writing code for any multi-file change, when asked to "plan", "break this down", "split this", "stack this", "make it reviewable", "plan the chain", or when a commit or dirty worktree mixes several concerns (retro-split). VCS-agnostic (Gerrit relation chains, GitHub stacked PRs).
allowed-tools: Bash, Read
---

# Stack Planner

Turn a request into an ordered chain of changes, one concern each, and **stop at
the approved plan**: no edits, no `git add`, no `git commit` before the user
says yes. A step becomes one commit; on Gerrit the chain is a relation chain
(`gerrit-workflow` skill), on GitHub a set of stacked PRs.

Not for a single-concern edit (just make it) or a mechanical change (one change
by design).

## The Concern Is the Unit

A step belongs in the chain when a reviewer can approve it without reading the
next one:

- one behaviour or one mechanical transformation, stated without "and";
- builds and passes with only the earlier steps present;
- carries its tests, and the docs for the behaviour it adds (no final "add
  tests" or "docs" step);
- is used: no class without a caller, no scaffolding, no "part 1/2";
- revertable alone.

How fine to cut beyond that is a judgement call: follow the repository's habits
(`git log --stat`) and state the choice in the plan. Patterns:
`references/split-patterns.md`.

**Mechanical changes** (rename, migration, API move, formatter, codemod) are one
step however large, before any behaviour change, marked "mechanical" with how
they were produced. Split by module only if each part builds alone.

**Size** is a warning: above ~400 production lines (insertions + deletions;
tests, docs and lock files not counted) a step gets a one-line justification.
Never split a concern to get under it, never merge concerns to shorten the
chain. A team may set other values in `AGENTS.md`, `CONTRIBUTING` or
`CLAUDE.md`. Counting and evidence: `references/budget.md`.

## Process

1. **Collect inputs**; ask for what is missing: goal and acceptance criteria,
   verify command (from `AGENTS.md`, `CONTRIBUTING`, `CLAUDE.md`, Makefile or
   CI), subject style (the documented commit conventions, else
   `git log --format=%s -20`), target (Gerrit branch or stacked PRs).
2. **Map** every file to create or modify and its layer (`git grep <symbol>`,
   `git ls-files <dir>`).
3. **Find the concerns** and make each a step.
4. **Order** infra → data/migration → API → caller; refactors and mechanical
   changes first.
5. **Estimate** production and test lines per step; say which figures are
   guesses.
6. **Emit the plan** with `references/plan-template.md`.
7. **Ask and stop.** Continue without asking only if the request explicitly
   pre-approved the plan.

## Retro-split

When a commit or worktree already mixes concerns (not merely when it is large):
measure it (`git diff --numstat HEAD`, or `git show --numstat --format= HEAD`),
plan the split as above (hunks per step where a file is shared), ask, then
follow `references/retro-split.md`.

## Pre-flight Checklist

- [ ] Each step: one concern, no "and", repository subject style.
- [ ] Each step builds, is tested and is used on its own.
- [ ] No blank cells; new files marked `(new)`; guesses stated.
- [ ] Steps over the warning are justified, not split; mechanical steps are
  marked and first.
- [ ] `Chain summary:` line present; the approval question is last.
- [ ] Nothing edited, staged or committed; no `Change-Id:` written.
