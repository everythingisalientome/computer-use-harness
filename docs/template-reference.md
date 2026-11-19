# Computer use harness: template set, version 1

Last updated: 2026-11-18

Status: **version 1, drafted before any code exists**. Expect fields to change once a real step has run. The example is the ERPNext process "create a sales quotation for a new customer", followed by recording the result in Notepad. It uses one web app and one desktop app on purpose.

This set shows the format a converter must produce from a business procedure: what each file holds, which fields it has, and what a filled-in example looks like.

## The files

| File | Format | What it holds | Who changes it | Scope |
|---|---|---|---|---|
| `config/overall-context.md` | Markdown | How every agent behaves | Platform team | All personas |
| `config/model-connection.yaml` | YAML | Where the models are and which to use | Platform team | All personas |
| `config/tools.yaml` | YAML | The tools the harness can run | Platform team | All personas |
| `config/apps/<app>.md` | Markdown with a YAML header | What is known about one application | Whoever knows the app | Reused by every persona that uses the app |
| `config/personas/<id>/persona.yaml` | YAML | One agent's scope: work type, apps, tools, models, escalation | Platform team | One persona |
| `config/personas/<id>/procedure.yaml` | YAML | The steps, including how work is found | Process owner | One persona |
| `config/personas/<id>/rules.yaml` | YAML | The business rules | Business users | One persona |
| `config/personas/<id>/guardrails.yaml` | YAML | Limits the harness enforces | Risk and platform | One persona |
| `docs/action-format.md` | Markdown | What the model may return | Platform team | Fixed |
| `docs/state-machine.md` | Markdown | Work item and step statuses | Platform team | Fixed |
| `output/state/<reference>.json` | JSON | One work item's record | Written by the harness only | One work item |

A converter produces the four persona files and, for a new application, an app context. Everything else is written once.

Every YAML and JSON file is checked against a schema when the harness loads it. A file that does not match stops the persona from starting.

## App file header fields

The header is the part of an app file the harness reads. The same fields apply to every app.

| Field | Web app | Desktop app |
|---|---|---|
| `kind` | `web` | `desktop` |
| `launch` | `browser` and `url` | `executable` |
| `launch.wait_seconds` | How long to wait before the first screenshot | The same |
| `allowed_window.match` | `launched_window`: the window the harness opened | `process`: any window belonging to the listed processes, which includes the app's own dialogs |
| `allowed_window.processes` | The browser's process | The app's process, plus any app it opens |
| `home` | How to get back to the app's home screen, and what it looks like | The same |

The step loop is identical for both kinds. The harness acts on the screen and does not know whether a window is a browser or a desktop app.

Nothing in the templates may require administrator rights.

## Procedure step fields

| Field | Required | Meaning |
|---|---|---|
| `id` | Yes | Short name, unique in the procedure |
| `role` | Yes | `find_work`, `pickup`, `claim`, `work` or `complete` |
| `intent` | Yes | What the step must achieve, in plain words |
| `app` | For screen steps | Which app context applies |
| `via` | Yes | `screen` or `tool` |
| `tool`, `args` | For tool steps | The tool operation and its arguments |
| `inputs` | No | The named values this step may use |
| `done_when` | For screen steps | The condition that proves the step worked |
| `verify_with` | No | `screen` or `tool_result`. Defaults to `screen` for screen steps and `tool_result` for tool steps |
| `captures` | No | Values to read off the screen once the step is verified |
| `rules` | No | Rules to evaluate after the captures |
| `skip_if` | No | A condition that skips the step |
| `when_nothing_found` | For `find_work` and `pickup` | `no_work`: the harness sleeps and polls again |
| `irreversible` | Yes | `true` if repeating the step would cause harm |
| `on_fail` | Yes | How many retries, then what happens |
| `hints` | No | Plain-language help for the model. Never coordinates |

Roles:

- **`find_work`:** a step that looks for work before an item is known. Optional; used when finding work takes several screen steps.
- **`pickup`:** the step where an item is identified. The harness creates or loads the state record here, using the work item's key. Exactly one per procedure.
- **`claim`:** the step that takes the item out of its queue. Exactly one per procedure.
- **`work`:** an ordinary step.
- **`complete`:** the step that closes the item at its source.

Values in curly braces, such as `{customer_name}`, are filled in by the harness from the work item or from an earlier capture.

## Capture fields

| Field | Required | Meaning |
|---|---|---|
| `name` | Yes | The name later steps and rules use |
| `type` | Yes | `text` or `number` |
| `question` | Yes | What to read, asked of the screenshot |
| `double_read` | Yes | `true` reads it twice and sends the item to a human if the reads differ. Use it for every value that feeds a rule or a `skip_if` |
| `allowed_values` | No | The only answers accepted |

## Rule fields

| Kind | Fields | Decided by |
|---|---|---|
| `computed` | `value`, `compare`, `to`, `outcome`, `reason` | The harness |
| `judgment` | `question`, `outcomes` for yes and no | The model. "Not sure" always goes to a human |
| `freeform` | `text`, optional `handle_as` | A human, or the model, as `handle_as` or the persona default says |

- `compare` is one of `greater_than`, `less_than`, `equals`, `not_equals`, `in_list`, `is_empty`.
- `outcome` is one of `continue`, `stop`, `send_to_human`.
- A computed rule has one value and one comparison. A rule that needs more is a `freeform` rule.

## Added while writing the example

These fields were not in the original design discussion. Each one exists because the example needed it. All of them were reviewed and accepted on 2026-11-18.

| Addition | Why it is needed |
|---|---|
| `role` on a step | Marks the pickup, claim and completion points the harness must recognise |
| `captures` | A rule needs a value, and the value has to be read off the screen by a defined question |
| `skip_if` | "Create the customer only if it does not exist" must be decided by the harness, not the model |
| `verify_with` | A tool step that opens an app still needs a screen check |
| `freeform` rules | Gives the "rule does not fit" selector a place to live |
| `allowed_window: launched_window` | A web page's window title cannot prove which site is showing, so the harness checks it is the window it opened |
| `blocked_keys` | Stops key presses that would close the window or leave the app |
| `irreversible_gate` | States in one place what must be true before an irreversible step |
| Model slots (`actor`, `verifier`, `reader`) | Lets the verifier use a different model without touching the procedure |

## Not verified in the example

- The exact item code. The list showed `12345-BLA-128` cut short; `12345-BLA-128GB` is inferred from the item name.
- Whether the item has a selling price. With no price the total is zero and the total rule never fires.
- Whether the search box, list filters and suggestion fields behave as the app context says.
- The model names in `config/model-connection.yaml`.
- Everything in the Notepad app context. Notepad differs between Windows versions.
- Whether the Save As dialog belongs to the Notepad process on the build machine. The allowed-app check depends on it.
- Whether `C:\Users\Public\Documents` is writable on the build machine. The `note_file` column in the CSV points there.
