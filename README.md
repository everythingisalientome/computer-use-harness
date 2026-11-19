# Computer use harness: what is in this folder

This folder is the starting point for building the computer use harness. It holds the design, the templates, and one worked example. **It contains no code yet.** The code is built later in Claude Code, on Windows.

The worked example is one persona, `quotation-creator`. It creates a draft sales quotation on the public ERPNext demo site, then records the result in Notepad and saves the file. It uses one web app and one desktop app on purpose, so both are proven.

## The three kinds of file

Every file here is one of three kinds. Knowing which kind a file is tells you how the harness treats it.

| Kind | What the harness does with it | Where it lives |
|---|---|---|
| **Read and acted on** | The harness parses the file, and its behaviour changes with the content | `config/` (the YAML files and the header of each app file), `input/` |
| **Passed to the model as text** | The harness does not understand the content. It pastes the text into the model's prompt | `config/overall-context.md`, and the body of each file in `config/apps/` |
| **For people and Claude Code only** | The harness never opens it | `docs/`, `examples/`, this README, `CLAUDE.md` |

## The folder as it is now

```
computer-use-harness/
├── README.md                     this file
├── CLAUDE.md                     standing instructions for Claude Code
├── docs/                         for people and Claude Code
│   ├── BUILD-PLAN.md               the brief for building the harness
│   ├── CHANGE-GUIDE.md             how to change things after the build
│   ├── decision-record.md          what was agreed, and why
│   ├── template-reference.md       every field in every template
│   ├── action-format.md            specification: what the model may return
│   └── state-machine.md            specification: statuses and step order
├── config/                       what the harness loads
│   ├── overall-context.md
│   ├── model-connection.yaml
│   ├── tools.yaml
│   ├── apps/
│   │   ├── erpnext.md              a web app
│   │   └── notepad.md              a desktop app
│   └── personas/
│       └── quotation-creator/
│           ├── persona.yaml
│           ├── procedure.yaml
│           ├── rules.yaml
│           └── guardrails.yaml
├── input/
│   └── quotation-requests.csv    the work queue
└── examples/
    └── work-item.example.json    a sample of what the harness will write
```

## File by file

### Top level

| File | What it is |
|---|---|
| `README.md` | This file |
| `CLAUDE.md` | Standing instructions that Claude Code reads at the start of every session in this folder: what to read first, the fixed constraints, and the rules for changing things |

### `docs/`

| File | What it is | When to read it |
|---|---|---|
| `BUILD-PLAN.md` | The brief for Claude Code: fixed constraints, the 12 pieces to build in order, and how to tell each one is done | First, before building |
| `CHANGE-GUIDE.md` | Which file to edit for which change, what else to update, and how to check the change. Its code-dependent sections are completed at the end of the build | After the build, whenever something needs changing |
| `decision-record.md` | Every decision from the design discussion, plus what was parked and what is out of scope | When you want to know why something is the way it is |
| `template-reference.md` | The field-by-field reference for every template, and the list of fields added while writing the example | When writing or generating a template |
| `action-format.md` | A specification. The exact shape of what the model may return on each of the four kinds of model call | When building the model client and step loop |
| `state-machine.md` | A specification. The statuses a work item and a step can have, the order of events inside one step, and the resume rules | When building the procedure runner and state store |

### `config/`: shared by every persona

| File | What it is | Who changes it |
|---|---|---|
| `overall-context.md` | Text given to the model on every call: how to act, how to handle values, how to treat what is on screen | Platform team, rarely |
| `model-connection.yaml` | Where the models are and which model each named slot uses. The only file to change when switching provider or pointing at a localhost model | Platform team |
| `tools.yaml` | The list of tools the harness can run, with each tool's operations and arguments | Platform team, when a new tool is built |

### `config/apps/`: one file per application

| File | What it is | Who changes it |
|---|---|---|
| `erpnext.md` | What is known about ERPNext, a web app. A structured header, then free text | Whoever knows the app |
| `notepad.md` | What is known about Notepad, a desktop app, including its Save As dialog. Same shape as the ERPNext file | Whoever knows the app |

### `config/personas/quotation-creator/`: one folder per persona

| File | What it is | Who changes it |
|---|---|---|
| `persona.yaml` | The entry point. The agent's work type, the apps and tools it may use, which models it uses, where escalations go | Platform team |
| `procedure.yaml` | The steps, in order, including how work is found, claimed and completed | Process owner |
| `rules.yaml` | The business rules: computed rules the harness evaluates, and judgment rules the model answers | Business users |
| `guardrails.yaml` | The limits the harness enforces in code, and the guidance that is only told to the model | Risk and platform |

### `input/` and `examples/`

| File | What it is |
|---|---|
| `input/quotation-requests.csv` | The work queue. One row per request. The harness reads the next unstarted row and writes the row's status back |
| `examples/work-item.example.json` | A hand-written sample of a state record. It shows the shape of what the harness will write for each work item |

## Questions and answers

**Can the `quotation-creator` folder be generated from a business procedure?**
Yes. Those four files are what a converter would produce from a business procedure, with a human reviewing and certifying the result. The harness then runs them as they are.

**`tools.yaml` lists tools such as `launch_app` and `escalate`. Do those tools exist yet?**
No. `tools.yaml` only declares that a tool exists and what arguments it takes. The Python code that opens the app, updates the CSV or sends an escalation is built later, in Claude Code.

**Is `work-item.example.json` a real record? Has the agent already worked on something?**
No. It is a sample written by hand. Nothing has run. It imagines a run that stopped partway through request `REQ-0001`, so you can see what a record looks like mid-run. The harness never reads this file. Once the harness exists, it writes real records to `output/state/`.

**Are the sections in an app file, such as `apps/erpnext.md`, the exact sections every app file must have?**
No. The file has two parts:

- **The header**, between the two `---` lines, is structured. The harness reads it to know how to launch the app, how to recognise its window, and how to get back to its home screen. These fields are required and are the same for every app.
- **The body**, everything below the header, is free text. Its sections are not fixed. You can add, rename or remove them. Keeping the same section names across apps is a convention that helps the converter and reviewers; the harness does not depend on it.

**If the body is free text, how does a deterministic harness understand it?**
It does not need to. The harness is deterministic about what it does: which step runs, which rule is evaluated, whether an action is allowed. The body of an app file is not instructions to the harness. The harness passes that text to the model whenever a step uses that app, and the model uses it to find its way around the screen.

**Can the harness handle desktop apps as well as web apps? Does that need another tool?**
Yes, and no new tool is needed. The harness acts on the screen: a screenshot in, mouse and keyboard out. It does not know whether the window is a browser or a desktop app, so the step loop is the same for both. Two things differ, and both are in the app file's header: how the app is launched (an executable instead of a browser address), and how its window is recognised (by process, which also covers the app's own dialogs such as Save As). The example uses Notepad to prove this.

**Does anything need administrator rights?**
No. Nothing is designed on the premise that the harness or an app runs as administrator. That can be revisited later if it becomes a bottleneck.

**What about Excel?**
Not in this build. It is planned for a later build through tools built on libraries, not through screen automation.

**Is `overall-context.md` per persona, per agent, per app, or per desktop?**
None of those. There is one for the whole harness, shared by every persona, every app and every desktop.

**Should `overall-context.md` stay unchanged?**
Yes, when adding a persona or an app. Change it only when you learn something that applies to every agent. Anything specific to one persona goes in that persona's `guidance`. Anything specific to one app goes in that app's file.

**What are the two specification files for?**
They are build instructions. Claude Code reads them to write the code. The harness never loads them.

- `action-format.md` defines what the model may return, so the code that builds prompts and checks answers is written from it.
- `state-machine.md` defines the statuses and the order of events inside a step, so the procedure runner and state store are written from it.

**Where is the state machine configured?**
It is not configured. The statuses are fixed in the harness and are the same for every persona. If each persona could define its own statuses, two personas could not share one work item record.

**Where is the state stored, and in what format?**
One JSON file per work item, written only by the harness. It is not a template and nobody edits it by hand.

**What is `CLAUDE.md` for?**
Claude Code reads it automatically at the start of every session in this folder. It holds the rules that should always apply: what to read first, the fixed constraints, and that template fields are not to be changed without asking.

## The folder after the harness is built

Three things are added: the code, the checks, and a folder the harness writes into. The names inside `harness/` are a sketch; Claude Code may organise the code differently.

```
computer-use-harness/
├── README.md
├── CLAUDE.md                     now also lists the commands
├── docs/                         unchanged, with CHANGE-GUIDE.md completed
├── config/                       unchanged, revised as we learn
├── input/                        unchanged
├── examples/                     unchanged
├── harness/                      NEW: the Python code
│   ├── run.py                      starts one persona
│   ├── screen/                     screenshot, mouse, keyboard, window facts
│   ├── model/                      model client, action checking
│   ├── loop/                       the step loop, verify and read calls
│   ├── runner/                     procedure runner and polling
│   ├── rules/                      computed-rule evaluator
│   ├── state/                      state store and resume
│   ├── guardrails/                 allowed-app check, blocked keys
│   ├── audit/                      the fact log and screenshot retention
│   └── tools/                      work_queue_csv.py, launch_app.py, escalate.py
├── schemas/                      NEW: the checks each config file must pass
├── probe/                        NEW: the pointing-accuracy test
├── scripts/                      NEW: command-line tools, such as screen.py for screen input and output
├── tests/                        NEW
└── output/                       NEW: written by the harness at run time
    ├── state/REQ-0001.json         one record per work item
    ├── evidence/REQ-0001/          the kept screenshots
    ├── logs/                       the audit log
    └── needs-human.csv             escalated items
```

## Adding to it later

`docs/CHANGE-GUIDE.md` has the full list of changes, including the ones that need code. The common additions are:

| To add | What you create | Code changes |
|---|---|---|
| A second persona on an app already described | One folder under `config/personas/` with the four files | None |
| A persona on a new app, web or desktop | The persona folder, plus one file under `config/apps/` | None |
| A new kind of work source or destination | An entry in `config/tools.yaml` | The tool's Python code |
| A different model or provider | An edit to `config/model-connection.yaml` | None |

## Where to start

1. Read this file.
2. Read `config/personas/quotation-creator/persona.yaml`, then `procedure.yaml` in the same folder. Together they show what an agent is and what it does.
3. Use `docs/template-reference.md` to look up any field you do not recognise.
4. When ready to build, open this folder in Claude Code and point it at `docs/BUILD-PLAN.md`.

## Status

Template set version 1, written before any code exists. Some fields will change once a real step has run against a real screen. Parts of the example are not yet verified; `docs/template-reference.md` lists them.
