# Computer use harness

A Python harness for Windows that runs one persona unattended: it finds work, follows a known procedure step by step, acts through screenshots, mouse and keyboard, enforces guardrails in code, and records what it did.

## Read before doing anything

1. `README.md`: what every file and folder is.
2. `docs/BUILD-PLAN.md`: the pieces to build, in order, and how to tell each is done.
3. `docs/decision-record.md`: what was agreed and why. Do not reopen a decision without asking.
4. `docs/action-format.md` and `docs/state-machine.md`: the two specifications the code implements.
5. `docs/template-reference.md`: every field in the templates under `config/`.

## How to work with Preet

- Ask questions instead of assuming. If something is not in the docs, ask.
- Critique a proposal before agreeing with it. Push back on over-engineering.
- Explain the design reasoning before writing code.
- Build one piece from the build plan at a time. Show that its "done when" check passes before starting the next.
- Preet's Python is limited. Keep code plain and readable, and say what each new module is for.

## Fixed constraints

- Windows and Python only.
- No administrator rights. Nothing may require the harness, or an app it drives, to run elevated. If that blocks progress, stop and ask.
- Web apps and desktop apps go through the same step loop. Do not build a separate path for either.
- Models are called through the OpenAI chat-completions format. Every connection detail stays in `config/model-connection.yaml`. The key comes from an environment variable and is never written to a file or a log.
- Acting is screen only: screenshots in, mouse and keyboard out. No DOM, no browser automation library, no accessibility tree for acting. Operating-system facts such as the foreground window and its process are allowed for checks.
- The harness owns the procedure. The model never sees the whole procedure and never chooses the next step.
- The model returns one action per call, in the format in `docs/action-format.md`, on a 0 to 1000 coordinate grid.
- Guardrails are enforced in code. Text in a prompt is guidance, never a guardrail.
- Passwords never reach the model.
- The harness is the only writer of state. Computed rules are evaluated in code, never by the model.

## Rules for changing things

- The templates under `config/` are a contract with a separate converter system. Do not add, rename or remove a template field without asking first. When a change is agreed, update `docs/template-reference.md` and the schema in the same change.
- Do not add a status to the state machine without asking.
- When a decision changes, update `docs/decision-record.md`.
- Mark anything in an app file under `config/apps/` as "seen" only after observing it on the build machine.
- Keep `docs/CHANGE-GUIDE.md` current. Its "after the build" sections are yours to complete in piece 11.

## Not in this build

The converter, the vault login tool, session isolation, service accounts, screenshot masking, several agents on one queue, and Excel (planned later, through library-based tools). See `docs/BUILD-PLAN.md`.

## Commands

Add the commands to run a persona, run the tests and run the schema check here as each one comes into existence.

Setup (once): `python -m venv .venv` then `.venv\Scripts\python -m pip install -r requirements.txt`.

Pointing probe (piece 0), see the docstring at the top of each script:

- `.venv\Scripts\python probe\capture.py <screen_id>`: screenshot of the primary monitor
- `.venv\Scripts\python probe\label.py [screen_id]`: draw the true box around each element, then check the images it writes to `probe/review/` (`--review` writes them only)
- `.venv\Scripts\python probe\run_probe.py [--repeats N] [--screen id]`: ask the models and write the table to `probe/results/`

Screen input and output (piece 1), see the docstring at the top of `scripts\screen.py`. Press Ctrl+Alt+Q at any time to stop:

- `.venv\Scripts\python scripts\screen.py check`: the automatic check in a harmless test window; the report goes to `output/screen-check/`
- `.venv\Scripts\python scripts\screen.py shot | click X Y | scroll X Y DIR N | drag FX FY TX TY | type TEXT | key KEYS | window`: one action on the grid, after a 3-second countdown, then report the window in front

Tests: `.venv\Scripts\python -m pytest`
