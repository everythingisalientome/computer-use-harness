# State and state machine

The state is not a template. Nobody edits it by hand. The harness writes one JSON record per work item, and the statuses below are fixed in the harness, the same for every persona. An example record is in `examples/work-item.example.json`.

## Where it lives

- One file per work item: `output/state/<reference>.json`.
- The harness is the only writer. It writes after every verified step and on every status change.
- The model can add a note. Notes sit in their own list, marked `written_by: model`. The harness and the computed rules never read them.

## Work item statuses

| Status | Meaning |
|---|---|
| `claimed` | A persona has taken the item out of its queue |
| `in_progress` | At least one work step has started |
| `completed` | Every step is verified. Final |
| `needs_human` | The item was sent to a human, with a reason. Final for the agent |

"No work" is not a status. It means no item was found, so no record exists.

Allowed moves:

| From | To | When |
|---|---|---|
| (no record) | `claimed` | The claim step is verified |
| `claimed` | `in_progress` | The first work step starts |
| `in_progress` | `completed` | The last step is verified |
| `claimed` or `in_progress` | `needs_human` | A rule says so, a step fails beyond its retries, a guardrail is broken, two reads disagree, or resume cannot confirm an irreversible step |

A different persona may pick up an item in `in_progress` when its own procedure's pickup step finds the item's key. It loads the existing record and adds its steps to the same history.

## Step statuses

| Status | Meaning |
|---|---|
| `pending` | Not started |
| `attempting` | Started and not yet verified. Written before the first action |
| `verified` | The "done when" check passed, or the tool reported success |
| `skipped` | The step's `skip_if` condition was true |
| `failed` | Retries are used up, or the action limit was reached |

`attempting` is written before the first action so that a crash leaves evidence the step had started.

## What happens inside one step

1. If `skip_if` is true, mark the step `skipped` and move on.
2. If the step is irreversible, check the gate: every rule on earlier steps ended in "continue".
3. Mark the step `attempting`.
4. Run it: the tool, or the screen loop up to the action limit.
5. Verify: the "done when" check on a fresh screenshot, or the tool's result.
6. Read each capture. A capture with `double_read` is read twice; if the two reads differ, the item goes to a human.
7. Evaluate the step's rules, in the order listed.
8. Mark the step `verified` and write the state.

## Resume after a stop

For the step found in `attempting`, run its "done when" check before acting.

| Check result | Step type | What happens |
|---|---|---|
| Already true | Any | Read captures, evaluate rules, mark `verified`, move on |
| False | Not irreversible | Redo the step |
| False or unclear | Irreversible | Send to a human |

## What goes to the queue

The CSV row's status column mirrors the work item status (`claimed`, `in_progress`, `completed`, `needs_human`). An empty status means nobody has started the row.
