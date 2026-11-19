# Computer use harness: decision record

Last updated: 2026-11-19 (model client and action format, section 9)

Status: **design complete. Template set version 1 and the build brief are written and reviewed.** No code starts until Preet explicitly asks for it. The harness itself will be built in Claude Code on Windows, not in the planning chat.

Related documents: `template-reference.md` (every template, the action format, the state machine) and `BUILD-PLAN.md` (the build brief).

Working agreements: ask questions instead of assuming; critique every proposal; treat this as a brand-new initiative, not merged with earlier work.

## 1. The concept

An unattended agent that is configured with a persona, looks for work on its own, and completes that work by following a known procedure. It interacts with desktop and web apps mainly through computer use (screenshot in, mouse and keyboard out), and uses API or database tools where the procedure says so.

A **persona** is the scope of work for one agent: the context, guardrails, and tools that make it, for example, a credit card onboarding agent. It is not a personality.

## 2. Agreed decisions

### Harness and model

- This is a **harness**: deterministic code that finds work, assembles context, calls the model, executes actions, verifies, logs, and escalates. The model is a stateless call inside that loop.
- The harness owns the procedure and tracks the current step. The agent always follows a known procedure and never plans freely.
- Models are reached through OpenAI-compatible APIs. Models named for the build: **Gemma 4 31B** and **Gemini 3.8 Flash**.
- The build uses **OpenRouter**. The model connection lives in its own separate file, so others can switch to their own API or a localhost model without touching the harness.
- Computer use is a hard constraint as the default way to act. Reason: DOM structures in legacy bank web apps are unreliable, and apps launch from inside each other.
- Where an API or database tool exists, the **step declares** whether to use the tool or the screen. The model does not choose.
- The harness may use operating-system facts (active window title, process name) alongside screenshots, for example for the allowed-app check.

### Build environment and formats

- Operating system: **Windows**, always. Language: **Python**.
- **YAML** for structured templates (persona, procedure, rules, guardrails, tools, model connection).
- **Markdown** for prose templates (overall context, app context).
- Every file is checked against a schema when the harness loads it.
- The **state** is JSON written only by the harness. The **state machine** (work item and step statuses) is fixed in the harness and is not a template.

### Where the work happens

- **Planning chat (no code):** decision record, build brief, template set version 1, action format, state machine.
- **Claude Code on Windows:** all Python, the pointing probe, tests, the end-to-end run, and revising the templates once the step loop has run.
- Templates are drafted first, before the loop exists, and are expected to be revised.
- The templates are also the format the separate converter system must generate. The unit it generates is four persona files plus an app file; this is accepted for now.
- The repository carries a `CLAUDE.md` with standing instructions for Claude Code.
- The repository carries a change guide (`docs/CHANGE-GUIDE.md`) for making changes after the harness is built. Claude Code completes its code-dependent sections as the last piece of the build.

### The step loop

1. The harness captures a screenshot.
2. It sends the model the step intent, the app context, the screenshot, and the actions already taken in this step.
3. The model returns one action, or "step done", or "cannot proceed".
4. The harness checks the action is allowed, executes it, and captures a new screenshot.
5. This repeats until the model says the step is done, or an action limit is reached and the item escalates.
6. A verifier call checks the "done when" condition.

- **Own action format:** a small fixed action set (click, double-click, type, key press, scroll, drag, wait, step done, cannot proceed) defined by us, independent of any model vendor.
- **Coordinates:** the action format uses a 0 to 1000 grid, and the harness converts to pixels.
- **Typed values come from the harness:** the model says "type the customer ID" and the harness inserts the real value.
- **Verifier is a fresh call:** it sees only the screenshot and the "done when" condition, with no action history.
- For the demo, the verifier uses the same model as the actor. The model choice stays configurable, with a note recommending a different model.

### Persona

- One persona handles **one work type**, to limit blast radius.
- Finding work is part of the same persona and the same procedure as doing the work ("think of it as a human"). The procedure starts with the steps for looking for work, then the steps for doing it. If there is no work, the harness notes "no work" and sleeps.
- Each persona polls for its own work. The intake method is per persona: an API, a mailbox, a folder, or opening an app and reading its queue.
- Agents do not wait. If work continues after an external event (for example an email reply), a different persona can pick it up.

### Procedure structure

- **Pickup point:** one step is the point where an item has been identified and its key (for example a reference number) is known. Steps before it may end in "no work".
- **Claim step:** every procedure includes a step that takes the item out of the queue (mark as read, move, assign to self), so the next poll does not pick it up again.
- **`role` on every step** (find work, pickup, claim, work, complete), so the harness recognises the pickup, claim and completion points.
- **`captures`:** a step can define values to read off the screen, each by a stated question. Rules and `skip_if` use these values.
- **`skip_if`:** a step can carry a flat condition that makes the harness skip it. The model answers the question that produces the value; the harness decides whether to skip.

### Framework pattern

A separate converter, with human review and certification, turns business procedures into this pattern. The converter is assumed to exist and is outside this work.

Layers:

| Layer | What it holds | Who changes it |
|---|---|---|
| Overall context | Rules common to every agent | Platform team |
| Persona | Work type, where to find work, which procedure, apps, and tools | Platform team |
| Procedure | The known steps for the work type | Process owner |
| Business rules | Thresholds and decisions, versioned | Business users |
| App context | Per-app knowledge, reusable across personas | Whoever knows the app |
| Tools | Computer use, API and database calls, credential login, escalation | Platform team |
| Guardrails | What must never happen | Risk and platform |

- **Progressive loading:** procedure, rules, and app context load only when needed, for accuracy and not cost.
- **Home-screen entry:** every app context includes how to get back to the app's home screen, so steps work after a restart.

Step format (option B, agreed): **intent and outcome, with optional plain-language hints**. The full field list is in the template set.

- Hints are words, never coordinates or selectors. The harness passes them to the model and never executes them.
- A hint about an app in general goes in the app context. A hint specific to one step goes in that step.

Business rules (option B, agreed): **flat computed rules in code, judgment rules to the model**.

- A computed rule is one line: a named value, a comparison, and an outcome (continue, stop, send to a human). The harness evaluates it; the model only reads the value off the screen.
- A judgment rule goes to the model with the rule text as context. The model can answer "not sure", which always goes to a human.
- Business users own the rules and follow the pattern, so the harness never deduces.
- When a rule cannot be written in the flat shape, a selector decides whether it becomes a judgment rule or goes to a human. Business decides, based on impact. The persona sets the default and a single rule can override it.
- A value read off the screen that feeds a computed rule is read twice independently. If the reads disagree, the item escalates.

### Guardrails

Enforced in three places, strongest first:

1. **Environment:** the service account's entitlements and the apps available on the desktop.
2. **Harness checks:** allowed-app check before each action; escalation rules applied in code before irreversible steps.
3. **Prompt:** the persona's dos and don'ts, treated as guidance only.

Business hard stops (such as the $100k limit) are computed rules. The agent must not complete such an item even when everything else looks correct.

### Credentials

- The agent runs under a service account, one per persona, for traceability.
- App credentials come from a vault (CyberArk) through a tool.
- Passwords never reach the model. A "log in to app X" tool fetches and types the secret.

### State

- **Shared state (option A, agreed):** one record per piece of work, carried across personas, so each persona knows what is complete and what is pending. It has to be built.
- At the pickup point the harness creates a new record under the item's key, or loads the existing one. This is one read by key done by the harness, not a step the agent performs. No match where one is expected goes to a human.
- The harness writes state automatically after each verified step.
- The agent may add notes in a separate field labelled as model-written. No computed rule or harness decision reads the notes; another persona's model may see them as context only.

### Screens that are not as expected

- **Layout or label drift** (a field moved or is labelled differently): the model handles it automatically.
- **Data mapping** between differently shaped fields (first name versus full name): the model may do it only where the step's "done when" check can confirm the result.
- **A screen that does not belong** (error page, unexpected dialog, wrong app): bounded recovery. The model may try safe actions (close, go back) within the step's action limit, never on an irreversible step, then the item escalates.

### Failure, resume, and escalation

- Resume rule, with no extra flag: on resume, the harness runs the interrupted step's "done when" check before acting.

| Check result | Step type | What happens |
|---|---|---|
| Already true | Any | Mark it done and move on |
| False | Not irreversible | Redo the step |
| False or unclear | Irreversible | Send to a human |

- Where an escalated item goes, and who handles it, is defined by business rules and context, not harness logic.
- Escalation is carried out through a tool, not through computer use.
- Floor: the harness always marks the item "needs a human" in the state, with the reason, whatever the configuration says.

### Audit and evidence

- The audit trail is facts logged by the harness (step, action, window title, verification result, rule evaluated, input values, rule version), not a model-written summary.
- Screenshot retention in normal runs:
  - Successful item: only the screenshot of the last step is kept; everything else is deleted.
  - Failed or escalated item: the last successful step and the failure step are kept.
- Debug mode captures all screenshots. A debug run is for the same process, never a rerun of the same item.

### Example for the build

- App: the public ERPNext demo, https://erpnext-demo.frappe.cloud/api/method/erpnext_demo.erpnext_demo.auth.login_demo. It logs straight in with no password.
- Process: **create a sales quotation for a new customer**, across three screens (Customer, Item, Quotation).
- The 10% discount is **dropped** from the example.
- Work source: a simple **CSV file**. A harness tool reads the next row and updates the row's status (started, working, completed). One reference column is the work item's key.
- Irreversible steps in the example: saving the customer and saving the quotation.
- Computed rule in the example: Claude's choice, since it is a demo and the templates matter more. Chosen: quotation total above 500,000 INR goes to a human.
- After the quotation is saved, the agent records the request reference and quotation ID in **Notepad** and saves the file through the **Save As dialog**. This puts one desktop app in the first build.
- The demo environment (machine, session, accounts) is set aside for now.

### Desktop apps

- The harness handles desktop apps with the same step loop as web apps. It acts on the screen and does not know which kind of window it is driving. No separate tool is needed.
- Two things differ, and both live in the app file's header: how the app is launched (an executable instead of a browser address) and how its window is recognised (by process, which also covers the app's own dialogs).
- **No administrator rights.** Nothing is designed on the premise that the harness or an app runs elevated. It can be added later if it becomes a bottleneck.
- **Excel** is for a future build, through tools built on libraries, not screen automation.

## 3. Findings from documentation and the demo site (2026-11-18)

- Gemini 3.8 Flash has an OpenAI-compatible chat endpoint. Google's built-in computer-use tool for it is shown on Google's native API, not on the OpenAI-compatible path.
- Gemini's computer-use tool returns coordinates on a normalised 0 to 1000 grid, not pixels.
- Gemma 4 31B accepts images and can output bounding boxes for interface elements, also relative to a 1000 by 1000 grid.
- Not verified: how accurately either model points at elements on ERPNext screens, and whether both models are offered on OpenRouter. (Both since measured and checked; see section 7.)
- The ERPNext demo was viewed in Chrome. What was seen is recorded in the ERPNext app context inside the template set.

## 4. Template additions accepted on review

These came out of writing the example. Preet reviewed and accepted all of them.

1. `verify_with`, so a tool step can still be checked on screen.
2. `freeform` rules, as the home of the "rule does not fit" selector.
3. The allowed-app check for web apps recognises the window the harness launched, because a page title cannot prove which site is showing.
4. A list of blocked keys.
5. A stated gate before irreversible steps: every earlier rule must have passed.
6. Model slots (actor, verifier, reader).

## 5. Parked until after the demo

- Session or VM isolation per agent. Direction: one agent per session.
- Service account provisioning. The demo runs under Preet's login, so the harness's allowed-app check is the only guardrail in force.
- Sign-off for sending screenshots with customer data to models. No screenshot masking engine will be built.
- Retention period and ownership for kept screenshots, including debug runs.
- Several instances of one persona polling the same queue.
- Excel, through library-based tools.
- Apps that need administrator rights.

## 6. Out of scope

- The converter from business procedures to the pattern.
- Fine-tuning computer-use models, and where its training data comes from.

## 7. Pointing probe (build piece 0), 2026-11-19

### What was measured

Each model was asked to point at 34 named elements on 8 screenshots taken on the build machine (Chrome and Notepad maximised on a 1920 x 1080 monitor at 100% display scaling, ERPNext in its light theme), 3 runs per element. A run counts as a hit when the point lands inside the element's true box, drawn by hand. The screens: ERPNext Home, Customer list, New Customer, Item list, New Quotation, New Quotation with the Customer suggestion list open, Notepad, and Notepad's Save As dialog. Both model names were confirmed on OpenRouter before the run.

| | Gemini 3.8 Flash | Gemma 4 31B |
|---|---|---|
| Elements located in every run | 34 of 34 | 20 of 34 |
| Elements located in at least one run | 34 of 34 | 26 of 34 |
| Hits, all runs | 102 of 102 | 70 of 102 |

Gemma failed every run on: the user badge, the Customer Name, ID and Item Name filter boxes, the first row's name and checkbox on the Customer list, the "Not Saved" label, and the edit icon on an Items row. Gemma also gave different answers between runs at temperature 0. The full table and overlays are in `probe/results/2026-11-19_011945/`.

The planned 35th element (the second suggestion in the Customer list) was skipped: only one customer matched, and the entry after it was "Create a new Customer".

An earlier run scored six elements 0 of 3 for both models. They were labelling errors: boxes swapped between elements, and a "Template" box drawn around an "Enabled" label. The boxes were corrected and the probe rerun. The results folders from before 01:19 on 2026-11-19 use the wrong boxes and should not be used. To catch this earlier, the labeller now saves a review image per screen with every box drawn and named.

### Decisions

- **Gemini 3.8 Flash is the actor.**
- **No separate "where is it" call.** One act call decides the action and gives its coordinates. This removes the item from the parked list.
- **All three model slots (`actor`, `verifier`, `reader`) stay on Gemini.** The probe measured pointing only, not reading, so it gives no reason to split them. The recommendation to use a different model for the verifier still stands as a note and can be revisited.
- **Gemma is not used as the actor.** It stays in `config/model-connection.yaml` as the `alternate` slot.

### Limits of this evidence

- The probe gave the model the element's name. In the step loop the model must also decide which element to act on, so pointing in the step loop may be less accurate. Piece 3 is the first test of that.
- All screenshots were at 100% display scaling. Piece 1 must still prove that positions are correct above 100%.

## 8. Screen input and output (build piece 1), 2026-11-19

### Decisions

- **The harness runs DPI aware** ("per-monitor aware v2", set on its own process when the screen code loads). Screen size, cursor positions and screenshots are then all in real pixels, so display scaling never enters the grid-to-pixel conversion. Every screenshot is checked against the screen size, and a mismatch stops the harness.
- **One grid-to-pixel conversion**, in `harness/screen/grid.py`: grid 0 is the first pixel and grid 1000 the last (`round(grid x (width - 1) / 1000)`). The pointing probe uses the same function. Re-scoring the piece 0 answers with it changed no hit.
- **The harness acts on the primary monitor only.** The target machine will have one monitor; the demo machine may have more. Screenshots, clicks and the grid cover the primary monitor and nothing else. Two later pieces depend on this:
  - **Piece 5:** the app launcher (`launch_app`) must place each app's window on the primary monitor and maximise it, both when it opens an app and when it brings an already open one to the front.
  - **Piece 8:** the allowed-app check must refuse a foreground window that is not on the primary monitor, even when it belongs to an allowed app. The model would be pointing at a screenshot that does not show that window.
- **Input through Windows' own calls (`SendInput`, via `ctypes`), not a library such as `pyautogui`.** Text is sent as characters rather than as keys on a keyboard layout, so any character arrives as written whatever the layout. No new dependency.
- **Emergency stop: Ctrl+Alt+Q in any window.** It sets a flag checked before every input event, releases every held mouse button and modifier key, and ends the process at once with exit code 3. The mouse and keyboard refuse to act unless the hotkey registered, and the harness never sends the combination itself. No separate "stop if the mouse moved" check for now.
- **Pauses** are constants in code, overridable per call and on the command line: 20 ms between typed characters, 100 ms after a click, scroll, drag, key combination or typed text, and 50 ms between moving the cursor and pressing. They are not template fields; making them one would need agreement first.
- `double_click`, `scroll` (up, down, left, right) and `drag` are built now, because all three are in the action format.

### Requirement on the environment

- **The harness needs an unlocked, active desktop session.** In a locked, disconnected or minimised Remote Desktop session the harness sees the wrong screen or no screen, and its input does not reach the apps. Before every screenshot the harness asks Windows whether its session is active and unlocked, and whether the desktop receiving input is its own. A screenshot that Windows refuses, or that is one flat colour, also stops the harness. Each case stops it with a message saying which.
- The first version checked only the desktop receiving input, and the test with Win+L showed that was not enough: the Windows 11 lock screen (`LockApp.exe`) is drawn on the user's own desktop until someone starts to sign in, so the lock screen picture was captured as a normal screenshot. The session lock state from Windows (`WTSQuerySessionInformation`) is now the main check. Retested with Win+L: the screenshot was refused with "This Windows session is locked". This matters for the parked session isolation work (section 5): an unattended agent needs a session that stays unlocked and connected.

### Known limitation, nothing built

- **Some legacy and remote-desktop apps may ignore direct character input.** Characters are sent as Unicode characters, not as key presses. Most apps accept them, but some older apps and some remote-desktop or virtualised clients only accept real key presses. The likely fallback is to put the value on the clipboard and paste it with Ctrl+V. That needs care because the clipboard is shared and would briefly hold work item data, so it must never be used for passwords. Nothing is built for this until an app needs it.

### Evidence

- `scripts\screen.py check` opens a harmless full-screen test window in its own process and checks clicks at the corners, middle and between, each click's position in a screenshot, double-click, right-click, scrolling, drag, typing (including é, ₹ and Indian digit grouping), key combinations, and the foreground window's title and process. Reports are saved to `output/screen-check/`.
- At 100% scaling every check passed. The stop hotkey, pressed mid-check, ended the run with exit code 3 and left no key or button held.
- At 125% and 150% scaling every check also passed, with identical pixel positions (reports `output/screen-check/2026-11-19_015520_scale125.txt` and `2026-11-19_015548_scale150.txt`). Positions are correct above 100%.
- **Notepad's Save As dialog belongs to the Notepad process.** With the dialog in front, the foreground window was titled "Save as" and its process was `notepad.exe` (the Microsoft Store Notepad, version 11.2609). The allowed-app check by process therefore accepts it as part of Notepad, as `config/apps/notepad.md` assumes.

## 9. Model client and action format (build piece 2), 2026-11-19

### Decisions

- **The act call's intent has real values filled in**, and "Values you may type" lists each of the step's `inputs` with its name and value. The model needs the real value to recognise it on screen, for example the right entry in a suggestion list. It still types it only by name.
- **Literal text must be in double quotes.** A `type` with `text` is accepted only if that exact text appears in double quotes in the step's raw intent (before values are filled in), its hints, or the body of the step's app file. It is refused if it equals any work item or capture value, or contains one of three characters or more, even when the value is quoted somewhere. The templates were checked: the only literals they expect the model to type are the screen names in `config/apps/erpnext.md` ("Customer List", "Item List", "New Quotation"), which were already quoted. Every other typed value is a work item value or a capture, typed with `value_ref`. A quoted label the model only needs to recognise (such as "Not Saved") becomes an allowed literal; that is harmless.
- **A `value_ref` that is not one of the step's inputs, or `text` that is not allowed, is a malformed answer**, not a guardrail breach: one re-ask, with an error naming the `value_ref` names the step allows. Every refused answer is logged with its kind (`format`, `value_ref` or `literal_text`).
- **Parsing is strict.** One JSON object; a single ```` ```json ```` fence around it is allowed; unknown fields are refused. An answer to a read call that does not convert to the capture's type (for a number: an optional `₹` or `INR`, then digits, commas and at most one dot) is malformed too.
- **Secret register.** Code that handles a secret registers it; the client searches every text of every call for every registered secret and refuses to send, without naming it. The register is empty in this build, because nothing in it handles passwords; the vault login tool will register its secrets when it is built. Values typed with `value_ref` go from the harness to the keyboard and never into a prompt.
- **`config/overall-context.md` holds only guidance true of every kind of call.** It used to tell the model to return one action, which is wrong for verify, read and judgment calls. The step mechanics (one action at a time, `step_done`, `cannot_proceed`, staying in bounds, no recovery on irreversible steps) moved into the act instructions, which are fixed text in `harness/model/prompts.py` written from `docs/action-format.md`.
- **Persona guidance and the guardrails' "never" list go on act calls only.** Verify, read and judgment calls get the overall context, their own instructions, the condition or question with real values, and the screenshot.
- **Three outcomes for a call:** `ok`, `failed_attempt` (malformed twice; counts against the step's `on_fail` retries) and `unavailable`. Unavailable means a connection error, timeout, rate limit or server error that survived the OpenAI library's own two retries. **It is not a failed attempt: a provider outage pauses the run with its state intact. Piece 3 implements the pause.** A provider that refuses the settings (bad key, unknown model: any other 4xx) stops the run with a message, because waiting will not fix it.
- **Action history lines say `sent`**, or `refused` with the reason, never "done": the harness knows it sent the input, not that it worked.
- **Prompt size:** a budget of 60,000 characters of text, a constant in code. Only the history is cut, oldest first, keeping the last five lines. If the prompt is still too long, the harness stops and names the biggest part, usually an app file, for a person to shorten. Nothing is cut silently from the app context.
- **Screenshots are sent as full-resolution PNG**, as in the pointing probe, so its accuracy figures still apply.
- **No provider "JSON mode" or structured output.** Not every OpenAI-compatible endpoint supports it, and using it would need a new field in `model-connection.yaml`. Revisit if malformed answers become frequent.
- **The wait cap clamps** a `wait` to `max_wait_seconds_per_action` and logs it, rather than refusing it. Built in piece 8 with the other guardrails.

### Evidence

- `pytest`: 98 tests pass, including a fake secret that stops the call before anything is sent, a bad-then-good answer (one re-ask carrying the error), bad twice (a failed attempt, no third call), an unknown `value_ref` (re-asked naming the allowed names, and logged), and unavailable as its own outcome.
- `scripts\model_check.py`, run `output/model-check/2026-11-19_022248`: 14 calls per model on saved probe screenshots with real steps, rules and captures, including a forced re-ask.

| | Gemini 3.8 Flash (`default`) | Gemma 4 31B (`alternate`) |
|---|---|---|
| Calls ending with a checked answer | 14 of 14 | 14 of 14 |
| Forced re-ask recovered | yes | yes |
| Answer as expected | 14 of 14 | 10 of 14 |
| Seconds per call, mean / max | 5.6 / 13.8 | 1.4 / 3.2 |

- Gemini picked the matching customer and not "Create a new Customer", returned `step_done` when the intent was already met, and `cannot_proceed` for a Notepad step with ERPNext on screen.
- An earlier run (`2026-11-19_022135`) failed for Gemma: after the forced bad answer, its corrected answer added `target` to a `type` action, so it counted as a failed attempt, as designed. Two reruns of Gemma alone passed. Gemma adds `target` to `type` actions often; in the final run the re-ask fixed it once without being forced.

### Observations for later pieces

- **Gemma types into a field without clicking it first** (all 3 cases in the final run where a click on the field was expected). Another reason it is not the actor.
- **In the failed run Gemma answered `ctrl+n` for the Notepad step while ERPNext was on screen.** The allowed-app check as written ("the foreground window belongs to one of the persona's allowed apps") would not stop that, because the Chrome window is allowed for ERPNext; Ctrl+N would open a new Chrome window. Piece 8 should consider checking the foreground window against the current step's app, not only the persona's list. To be decided with Preet.
- Gemini act calls took up to about 16 seconds. Fine for this persona; worth watching in piece 10.
