# Change guide

How to change the harness after it is built: which file to edit for which change, what else to update, and how to check the change is safe.

Status: the sections on templates are complete. The sections marked **to be completed after the build** depend on code that does not exist yet. Claude Code fills them in as the last piece of the build plan.

## Before any change

Answer three questions first.

1. **Which kind of file is it?** A file the harness acts on, a file passed to the model as text, or a document for people. `README.md` explains the three kinds.
2. **Who owns it?** Business users own the rules. The process owner owns the procedure. The platform team owns everything shared.
3. **Does a version need raising?** `procedure.yaml` and `rules.yaml` each carry a `version`. Raise it on every change. The version is recorded against each work item, so an audit can tell which rules applied.

## Changes that need no code

| I want to | Change this | Also do this |
|---|---|---|
| Change a threshold, for example the quotation limit | `to` on the rule in `rules.yaml` | Raise the rules version |
| Change what a rule does when it fires | `outcome` on the rule in `rules.yaml` | Raise the rules version |
| Add a computed rule | A new entry in `rules.yaml`, and its id in the `rules` list of a step in `procedure.yaml` | Make sure the value it uses is a capture with `double_read: true` on that step or an earlier one. Raise both versions |
| Add a judgment rule | A new entry in `rules.yaml` with a yes or no question, and its id on a step | Raise both versions |
| Add a rule that fits neither shape | A `freeform` entry in `rules.yaml` with `handle_as` | Raise the rules version |
| Change where escalated items go | `escalation` in `persona.yaml`, or `destinations` under the `escalate` tool in `tools.yaml` | Send one test item and confirm it arrives |
| Change how often the agent looks for work | `polling.interval_seconds` in `persona.yaml` | Nothing |
| Add, remove or reword a step | `procedure.yaml` | Give the step a clear `done_when`. Decide `irreversible`. Raise the procedure version |
| Help the agent with a difficult screen | A hint. In the app file if it is true of the app in general, on the step if it is specific to that step | Write hints in words, never coordinates |
| Describe a new popup or interruption | "Known interruptions" in the app file | Say how to dismiss it |
| Record that a screen changed | The app file | Usually nothing else. The steps describe intent, so a moved or renamed field should not break them |
| Switch model provider, or use a localhost model | `config/model-connection.yaml` | Set the key in the named environment variable. Rerun the pointing probe |
| Use a different model for checking than for acting | `models.verifier` in `persona.yaml` | The slot name must exist in `model-connection.yaml` |
| Change the action limit, blocked keys or allowed apps | `guardrails.yaml` | Nothing |
| Change behaviour for every agent | `config/overall-context.md` | Rerun every persona once in debug mode. This file affects all of them |
| Add a persona on an app already described | A new folder under `config/personas/` with the four files | Add its apps and tools to `persona.yaml` |
| Add a persona on a new app, web or desktop | The persona folder, and a new file under `config/apps/` | The app file's header must have `kind`, `launch`, `allowed_window` and `home`. Use `erpnext.md` as the pattern for a web app and `notepad.md` for a desktop app |

## Changes that need code

These look like configuration changes and are not.

| I want to | Why it needs code | What must change together |
|---|---|---|
| Add a tool, for example a mailbox reader or an Excel tool | A tool is Python that the harness runs | The entry in `tools.yaml`, the tool's code, a test |
| Add a field to a template | The harness only acts on fields it knows | The code that reads the field, the schema, `docs/template-reference.md`, and the converter that generates templates |
| Add a comparison to computed rules | The evaluator supports a fixed list | The evaluator, the schema, `docs/template-reference.md` |
| Add an action the model may return | The harness refuses unknown actions | `docs/action-format.md`, the action check, the code that performs it |
| Add a status | Statuses are fixed so that personas can share one record | `docs/state-machine.md`, the state store, every persona's handling. Avoid this unless there is no alternative |
| Keep more or fewer screenshots | Retention is a harness rule | The audit code, `docs/decision-record.md` |
| Drive an app that needs administrator rights | The harness is designed to run without them | A decision first. Record it in `docs/decision-record.md` before changing anything |

## After any change

1. Run the schema check. A file that does not match is refused when the persona starts, so find out before then.
2. Run the persona in debug mode on one test item and watch it complete.
3. Read the audit log for that item. Check the step, rule or value you changed appears as you expect.
4. Add a line to the change log at the end of this file.

For a change to `rules.yaml` or to an irreversible step, have a second person review it before it is used on real work.

## To be completed after the build

Claude Code fills in each section below in piece 11 of the build plan.

### How to run a persona

_To be completed: the command, and what each option does._

### How to run the schema check

_To be completed: the command, and how to read a failure._

### How to run in debug mode

_To be completed: the command, and where the screenshots are kept._

### How to run the tests

_To be completed: the command, and which tests need the real site._

### Where each template field is handled in the code

_To be completed: one row per field, naming the module that reads it._

| Template field | Module |
|---|---|
| | |

### Troubleshooting

_To be completed: one row per failure seen during the build._

| What you see | Likely cause | What to do |
|---|---|---|
| | | |

## Change log

| Date | File | What changed | Why | Who |
|---|---|---|---|---|
| 2026-11-18 | All templates | Version 1 written | First draft, before any code | Preet and Claude |
| 2026-11-18 | Procedure, persona, guardrails, apps, CSV | Notepad steps and the Notepad app file added | To prove the desktop path alongside the web path | Preet and Claude |
