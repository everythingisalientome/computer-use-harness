# Computer use harness: build plan and handoff brief (draft 3)

Last updated: 2026-11-18

Status: **ready for review**. This is the brief for building the harness in Claude Code. No code starts until Preet says so.

## Read first

1. `docs/decision-record.md`: what was agreed and why.
2. `docs/template-reference.md`: what each template file is and every field in it.
3. `docs/action-format.md` and `docs/state-machine.md`: the two specifications the code must implement.
4. The `config` folder: the templates themselves, filled in for the example persona.

## What is being built

A Python harness for Windows that runs one persona unattended. It finds work, follows a known procedure step by step, acts through screenshots, mouse and keyboard, enforces guardrails in code, and records what it did.

The first target is the example persona `quotation-creator`. Requests arrive in a CSV file. The agent works three screens of the public ERPNext demo in a browser, then records the result in Notepad and saves it through the Save As dialog. The example uses one web app and one desktop app on purpose, so both paths are proven.

## Fixed constraints

- **Windows and Python.**
- **No administrator rights.** Nothing may require the harness, or an app it drives, to run elevated. If that ever blocks progress, stop and ask; do not design around it in advance.
- **Models through OpenRouter**, using the OpenAI chat-completions format. All connection details stay in `config/model-connection.yaml`, and the key comes from an environment variable.
- **Screen only.** No DOM, no browser automation library, no accessibility tree for acting. Operating-system facts such as the foreground window and its process are allowed for checks.
- **Our own action format** on a 0 to 1000 coordinate grid.
- **The harness owns the procedure.** The model never sees the whole procedure and never chooses the next step.
- **Passwords never reach the model.**
- **Templates are the contract.** Do not add, rename or remove a template field without recording the change and the reason in the template set.

## Build order

Build one thin slice end to end, then widen it. Each piece is done when its check passes.

| # | Piece | Done when |
|---|---|---|
| 0 | Pointing probe | For each model, a table shows how many of about 25 named ERPNext elements it located within the element's bounds, on screenshots taken on the build machine |
| 1 | Screen input and output | A script takes a screenshot, clicks a given grid position, types text, sends a key, and reports the foreground window's title and process. Positions are correct with Windows display scaling above 100% |
| 2 | Model client and action format | A screenshot and an intent go in, and one validated action comes out, for both models. A malformed answer triggers one re-ask |
| 3 | Step loop | One hand-written step ("show the Customer list filtered to a name") runs on the real site and passes its verify call |
| 4 | Template loading | Every file in the template set loads and passes its schema. A deliberately broken file is refused with a clear message |
| 5 | Procedure runner | The whole procedure runs for one CSV row, including pickup, claim, `skip_if`, captures, the Notepad steps and completion. `launch_app` opens a web app and a desktop app, and brings an already open one to the front. An empty CSV produces "no work" and a sleep |
| 6 | Rules | The total rule and the template rule each send a prepared row to a human. Two differing reads send the item to a human. The judgment rule returns yes, no or not sure |
| 7 | State store | A record is written after each verified step. Killing the run mid-step and restarting follows the resume table |
| 8 | Guardrails and escalation | An action aimed at a window the harness did not launch is refused. Notepad's Save As dialog is accepted as part of Notepad. A blocked key is refused. An escalated item appears in the review file and is marked `needs_human` in the state |
| 9 | Audit and evidence | The log has one line per model call. A successful item keeps one screenshot, a failed item keeps two, and debug mode keeps all |
| 10 | End-to-end run | All three CSV rows run unattended: one completes and leaves a saved Notepad file holding its reference and quotation ID, one stops on the total rule, one stops on the template rule |
| 11 | Change guide | The "to be completed after the build" sections of `docs/CHANGE-GUIDE.md` are filled in: how to run a persona, the schema check, debug mode and the tests; which module handles each template field; and the failures seen during the build. `CLAUDE.md` lists the commands |

After piece 3, revise the templates before going further. Piece 3 is the first evidence of whether the step fields are right.

## Decide from the probe

Decided on 2026-11-19: Gemini is the actor, there is no separate "where is it" call, and all three slots stay on Gemini. See `docs/decision-record.md`, section 7.

- If either model misses often, add a separate "where is it" call before piece 3: one call decides the action and names the target, a second call locates the target.
- If one model is clearly better at pointing and the other at reading, use the model slots (`actor`, `verifier`, `reader`) to split them.

## Check before relying on it

- The model names on OpenRouter.
- The exact item codes on the demo site, and whether items have a selling price. With no price, the total rule cannot fire and row 2 of the CSV needs another trigger.
- How ERPNext's search box, list filters and suggestion fields behave. Correct `config/apps/erpnext.md` from what is observed and mark each line as seen.
- Amounts use Indian digit grouping (4,50,000.00). The number conversion must handle it.
- The demo site is public and shared. Customer names in the CSV carry a suffix to avoid clashes; change it per run.
- How Notepad behaves on the build machine: whether it reopens earlier text, whether it has tabs, and the shortcut for Save As. Correct `config/apps/notepad.md` from what is observed.
- Whether the Save As dialog is a window of the Notepad process. The allowed-app check for desktop apps depends on it.
- Whether `C:\Users\Public\Documents` is writable. The `note_file` column in the CSV points there; change the path if it is not.

## Known weak points in the design

- **Submit cannot be blocked by the harness.** A click is a position, so the harness cannot tell that a click lands on Submit. It is guidance to the model, caught afterwards by the "done when" check on status Draft.
- **The allowed-app check proves the window, not the page.** If the site navigates somewhere unexpected inside the same window, only the verify call will notice.
- **Tool steps before pickup have no work item.** A failure there is logged and the harness sleeps; there is nothing to escalate.

## Not in this build

- The converter from business procedures to templates.
- The vault login tool. The demo site needs no password.
- Session or virtual machine isolation, and service accounts. The build runs under Preet's login.
- Screenshot masking.
- Several agents on one queue.
- Excel. It is planned for a later build through tools built on libraries, not through screen automation.
- Anything that needs administrator rights.

## What was done in the planning chat

The decision record, this brief, and the template set, version 1. No code.
