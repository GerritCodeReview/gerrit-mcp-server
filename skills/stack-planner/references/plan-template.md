# Plan Template

Emit exactly this structure; the approval question is the last line.

```markdown
## Plan: <goal in one line>

**Base:** <remote>/<branch> at <sha7> · **Target:** <Gerrit relation chain | stacked PRs> · **Verify:** `<verify cmd>` · **Size warning:** <L> production lines<; hard cap <H> if the team set one>

| Step N — <subject> | files | est prod / test lines | verify cmd | depends on | reviewer note |
|---|---|---|---|---|---|
| Step 1 — <subject> | `<path>` (new), `<path>` | ~<p> / ~<t> | `<cmd>` | — | <what to look at; one-line size justification if over the warning; "mechanical: <how>" for a mechanical step> |
| Step 2 — <subject> | `<path>` | ~<p> / ~<t> | `<cmd>` | Step 1 | <…> |

Chain summary: <N> changes, ~<P> production / ~<T> test lines total, largest change ~<M> production lines, depth <N>, target <Gerrit relation chain on <remote>/<branch> | stacked PRs>.

Estimates: <what they are based on; list guessed figures and why, or "none guessed">

Out of scope / follow-ups: <bullets, or "none">

Approve this <N>-step plan? Reply **yes** to start Step 1, or name the step to change. No file is edited until you answer.
```

Rules for filling it in:

- *files*: every path, new ones marked `(new)`; for a retro-split, hunks as
  `path (hunks: 2, 4)`.
- *est prod / test lines*: insertions + deletions; docs and lock files left out.
- *verify cmd*: passes with only this and earlier steps present.
- *reviewer note*: what to look at, a size justification if over the warning, or
  "mechanical: <how>".

## Filled Example

```markdown
## Plan: config-driven greeting over REST and SSH

**Base:** origin/master at 3f2a9c1 · **Target:** Gerrit relation chain · **Verify:** `bash tools/quick-check.sh` · **Size warning:** 400 production lines

| Step N — <subject> | files | est prod / test lines | verify cmd | depends on | reviewer note |
|---|---|---|---|---|---|
| Step 1 — Serve a configurable greeting over REST | `src/main/java/com/example/demo/GreetingConfig.java` (new), `src/main/java/com/example/demo/Module.java`, `src/main/java/com/example/demo/GetGreeting.java` (new), `src/main/java/com/example/demo/HttpModule.java`, `src/test/java/com/example/demo/GreetingConfigTest.java` (new), `src/test/java/com/example/demo/GetGreetingTest.java` (new) | ~90 / ~50 | `bash tools/quick-check.sh` | — | Prefix from plugin config, default `"Hello"`; `GET /projects/{name}/demo-plugin~greeting` returns `{"greeting": "<prefix> <project>"}`. Check the missing-key path and the 404. |
| Step 2 — Serve the greeting over SSH | `src/main/java/com/example/demo/GreetCommand.java` (new), `src/main/java/com/example/demo/SshModule.java`, `src/test/java/com/example/demo/GreetCommandTest.java` (new) | ~35 / ~15 | `bash tools/quick-check.sh` | Step 1 | `demo-plugin greet <project>`; same config as REST; check argument parsing. |

Chain summary: 2 changes, ~125 production / ~65 test lines total, largest change ~90 production lines, depth 2, target Gerrit relation chain on origin/master.

Estimates: hunks in the two existing module files ~10 lines each; new files guessed (config ~35, REST ~45, SSH ~30, tests ~15–30 each).

Out of scope / follow-ups: none

Approve this 2-step plan? Reply **yes** to start Step 1, or name the step to change. No file is edited until you answer.
```
