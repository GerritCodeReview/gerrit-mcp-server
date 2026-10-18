# Conventional Comments

Source: https://conventionalcomments.org. Write labels when the team's
documented convention is Conventional Comments; read reviewers' labels always.

## Format

```
<label> [decorations]: <subject>

[discussion]
```

- **label**: one word that says what kind of comment this is.
- **decorations**: optional, in parentheses, comma-separated: `(non-blocking)`,
  `(blocking)`, `(if-minor)`; free-form tags such as `(security)`, `(test)`,
  `(ux)` are allowed too.
- **subject**: the message itself, one line.
- **discussion**: optional paragraphs with the reasoning, context and next
  steps.

## Labels

| Label        | Spec meaning                                                                                               | Blocking by default?            |
| ------------ | ---------------------------------------------------------------------------------------------------------- | ------------------------------- |
| `praise`     | "highlight something positive"                                                                             | no                              |
| `nitpick`    | "trivial preference-based requests"; non-blocking by nature                                                | no                              |
| `suggestion` | "propose improvements to the current subject"; be explicit about what and why                              | depends: the reviewer decorates |
| `issue`      | "highlight specific problems with the subject under review"; ideally paired with a suggestion              | yes, unless `(non-blocking)`    |
| `todo`       | "small, trivial, but necessary changes"                                                                    | yes                             |
| `question`   | "a potential concern but are not quite sure if it's relevant or not"                                       | no, but needs an answer         |
| `thought`    | "an idea that popped up from reviewing"; non-blocking by nature                                            | no                              |
| `chore`      | "simple tasks that must be done before the subject can be 'officially' accepted" (run a job, update a doc) | yes                             |
| `note`       | "always non-blocking and simply highlight something the reader should take note of"                        | no                              |

## Decorations

| Decoration       | Spec meaning                                                                        |
| ---------------- | ----------------------------------------------------------------------------------- |
| `(non-blocking)` | "should not prevent the subject under review from being accepted"                   |
| `(blocking)`     | "should prevent the subject under review from being accepted, until it is resolved" |
| `(if-minor)`     | resolve "only if the changes end up being minor or trivial"                         |

## Reviewer Label → Expected Author Action

| Reviewer wrote               | Author does                                                                      | Thread ends unresolved?                                     |
| ---------------------------- | -------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `praise`                     | Nothing, or a one-line thanks                                                    | no (usually already resolved)                               |
| `nitpick`                    | Fix if trivial; otherwise reply why not                                          | no after a fix; yes if declined and not marked non-blocking |
| `suggestion`                 | Fix, or reply with the reason to keep the current form                           | no after a fix; yes if declined                             |
| `suggestion (if-minor)`      | Fix only if the change is small; say which way you went                          | no, once you replied                                        |
| `issue` / `issue (blocking)` | Fix in a new patch set, or explain with a cited principle why it is not an issue | no only after the fix is pushed                             |
| `issue (non-blocking)`       | Fix now or defer to a follow-up change; name it                                  | no when fixed or deferred with a reference                  |
| `todo`                       | Do it in the new patch set                                                       | no after the fix                                            |
| `question`                   | Answer it; if it uncovers a real problem, treat it as an `issue`                 | no when answered                                            |
| `thought`                    | Optional reply; no code change expected                                          | no when answered, or leave as is                            |
| `chore`                      | Do the task (run the job, update the doc) and say so                             | no after it is done                                         |
| `note`                       | Read it; no reply needed                                                         | unchanged                                                   |

## Reply Examples

At most 3 sentences, threaded with `in_reply_to`; labels optional.

```
Done. Falls back to "" when greeting.prefix is unset (PS2).
```

```
thought: reading the file keeps greeting.prefix hot-reloadable, which the design doc requires; PluginConfigFactory caches. Happy to switch if reload is not needed.
```

```
note: agreed, but it touches the SSH command too; that is the next change in the chain, so this one stays REST only.
```

```
note (non-blocking): this change only moves code; behaviour is unchanged.
```

The last one is an author note: a new top-level comment, so labelled when the
team opted in.
