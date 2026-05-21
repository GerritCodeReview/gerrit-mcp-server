---
name: find-dependencies
description: >-
  Find all dependencies of a Gerrit change or set of changes — both explicit
  Depends-on annotations (parsed by the depends-on plugin) and implicit git-chain
  parents. Use when asked: what does this change depend on, what is blocking this
  change, show me the dependency chain, are all dependencies merged, which changes
  depend on this one.
---

# find-dependencies

Find and interpret the full dependency picture for one or more Gerrit changes.

The tools `get_depends_on` and `get_dependents` are provided by the
`gerrit_mcp_server_depends_on` extension. They are available whenever
`gerrit-mcp-server` is running with the depends-on extension installed and a
configured Gerrit host that has the `depends-on` plugin enabled.

## Dependency types

| Type                 | Source                                                                                   | Tool                     |
| -------------------- | ---------------------------------------------------------------------------------------- | ------------------------ |
| **Depends-on**       | Explicit `Depends-on:` annotation in the change message, parsed by the depends-on plugin | `get_depends_on`         |
| **Git-chain parent** | Implicit: this change's commit has a parent commit that is also an open Gerrit change    | `get_git_parent_changes` |

A dependency can be **resolved** (mapped to a numeric change ID) or
**unresolved** (only has an `I...` change key that couldn't be matched to a
change in the configured deliverables).

## Quick reference

| Goal                          | What to do                                                    |
| ----------------------------- | ------------------------------------------------------------- |
| What does change X depend on? | `get_depends_on(X)` + `get_git_parent_changes(X)` in parallel |
| Which changes depend on X?    | `get_dependents(X)`                                           |
| Are all dependencies merged?  | Get deps, then `get_change_details` on each; check `status`   |
| Full dependency chain         | Recurse: get deps, then get deps-of-deps (track visited IDs)  |
| Set of changes                | Call both tools for each change ID in parallel, deduplicate   |

## Workflow: single change

1. Call `get_depends_on(change_id)` and `get_git_parent_changes(change_id)` in
   parallel.
2. Merge the results:
   - From `get_depends_on`: each entry with `resolved: true` has a
     `change_number`; unresolved entries have an I-hash in `unresolved`.
   - From `get_git_parent_changes`: each entry is an open parent change (or null
     if the parent commit is not a tracked Gerrit change, e.g. a merged branch
     tip).
3. For each resolved dependency, optionally call `get_change_details` to show
   its status (open / merged / abandoned) and subject.
4. Present as a structured list grouping Depends-on and git-chain deps
   separately.

## Workflow: set of changes

Call both tools for every change ID. Use parallel tool calls to avoid sequential
latency. Deduplicate by change number (the same upstream change may appear as a
git-chain parent of multiple changes in the set).

## Recursive traversal

To build a full dependency chain:

1. Start with the target change(s).
2. Maintain a visited set of change numbers.
3. For each unvisited dependency, call `get_depends_on` and
   `get_git_parent_changes`.
4. Add newly discovered deps to the queue; add the current change to visited.
5. Stop when: the queue is empty, all deps are merged/abandoned, or a
   configurable depth limit is reached (default: 5 levels).
6. Detect cycles: if a change appears as its own (transitive) dependency, flag
   it rather than looping.

## Interpreting unresolved deps

An `unresolved` entry means the plugin found a `Depends-on: I...` annotation but
could not match that I-hash to any change in the configured deliverables
(project/branch pairs). This happens when:

- The depended-on change is on a different project or branch not in the plugin's
  deliverables config.
- The change was abandoned or deleted.
- The I-hash is a typo.

Surface unresolved deps as-is with the raw key and note that the status cannot
be determined without manual lookup.

## Finding what depends on a change (reverse lookup)

Use `get_dependents(change_id)` to find changes that have declared
`Depends-on: <change_id>`. This uses the `in:dependsons()` query operator.

## Troubleshooting

| Symptom                                                          | Fix                                                                                                                                                           |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `get_depends_on` returns `"note": "plugin may not be installed"` | The depends-on Gerrit plugin is not installed on this instance. Only git-chain deps are available.                                                            |
| `get_depends_on` returns empty `depends_ons`                     | The change has no `Depends-on:` annotation, or the last `Depends-on:` line is blank (which clears all deps).                                                  |
| `get_git_parent_changes` returns empty list                      | The change's parent commit is not an open Gerrit change (e.g. it's the branch tip or already merged). This is normal for standalone changes.                  |
| Unresolved deps for known changes                                | The depended-on change may be on a project/branch not in the plugin's deliverables. Try looking up the I-hash directly with `query_changes(change:<I-hash>)`. |
