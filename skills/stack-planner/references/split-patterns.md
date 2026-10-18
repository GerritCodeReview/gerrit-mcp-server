# Split Patterns

Each pattern yields steps a reviewer can approve without reading the next one.

## Patterns

**Vertical slice.** One step = one user-visible behaviour across the layers it
needs.

```
# Horizontal: nothing is verifiable until step 4
Step 3 — Add all REST endpoints (GET, PUT, DELETE)
Step 4 — Add the settings UI

# Vertical: each step is a complete behaviour with its test
Step 3 — Save the token (PUT endpoint + save button)
Step 4 — Show the stored token (GET endpoint + load on open)
Step 5 — Delete the token (DELETE endpoint + delete button)
```

**Infra first.** Build wiring, a dependency or a test harness gets its own step
only when it is verifiable alone; otherwise it goes with its first user.

**Mechanical change.** One change however large, first; behaviour on top. Split
by module only when each part builds and is complete.

```
# Wrong: arbitrary batches, behaviour mixed in
Step 1 — Migrate files A–M to the v5 client
Step 2 — Migrate files N–Z to the v5 client and add retries

# Right
Step 1 — Migrate to the v5 HTTP client   (mechanical: vendor codemod)
Step 2 — Retry idempotent requests on 503
```

**Migration alone.** A schema or data migration is its own step, compatible with
the code before and after it, ahead of the feature that needs it.

**Refactor before feature.** Behaviour-preserving, at the bottom, existing tests
unchanged, with its existing callers.

**Tests and docs with code.** Every step carries its tests; a test-only step
only covers code that already exists. Docs travel with the step whose behaviour
they describe, so a page covering two steps is split between them. A docs-only
step only for docs no single step owns: an overview spanning the chain, or a
reorganisation of existing docs.

**API then caller.** Two steps when the API is meaningful alone (other
consumers, a public surface); one slice when the caller is its only consumer.

**Feature flag.** For a chain that lands in stages, put the behaviour behind a
flag that defaults to off; the flag flip is the last step.

## Signals

Split when the subject needs "and", concerns mix (feature + migration,
mechanical + behaviour), acceptance criteria test different behaviours, or
reverting the step alone would break something unrelated. Size alone is not a
signal.

Merge into the neighbour when a step cannot be verified alone ("add an import"),
is "part 1" of something, or is half of one file's change.

## Worked Example

A plugin greets by project: a config prefix, a REST endpoint, an SSH command.
The config read alone would be a class without a caller, so it travels with
REST; SSH reuses it. Two steps, shown in `plan-template.md`. Three (config,
REST, SSH) would also be valid; the plan states which and why.
