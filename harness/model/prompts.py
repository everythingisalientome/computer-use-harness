"""Build the messages for the four kinds of model call: act, verify, read, judgment.

Every call has the same shape:
  system: config/overall-context.md, then the instructions for this kind of call
  user:   what this call is about, as text, then the screenshot last

Only the act call also gets the persona's guidance, the guardrails' "never"
list, the app context, the hints, the values it may type and the action history.
The verify, read and judgment calls get only their condition or question, with
real values filled in, and the screenshot.

The instruction texts below are the action format (docs/action-format.md)
written for the model. If that document changes, change them too.

Placeholders such as {customer_name} are filled from `values`: the work item's
fields and the captures made so far. No password is ever in `values`; the
secret register in client.py is the check behind that rule.
"""

import base64
import re

from .answers import ActRules, show_value, quoted_literals

# How much text an act call may hold, in characters, before the history is cut.
# This guards accuracy, not the model's limit: a prompt this long is a sign
# that something (usually an app file) has grown too big.
TEXT_BUDGET_CHARS = 60_000
HISTORY_ALWAYS_KEPT = 5  # the most recent history lines are never cut


class PromptError(Exception):
    """The prompt cannot be built: a missing value, or too much text."""


ACT_INSTRUCTIONS = """\
## This request: the next action

You are working on one step of a procedure. Return exactly one action: the next one. Do not return a plan or several actions. After each action you will get a new screenshot. Decide the next action from what that screenshot shows.

- When the step's intent has been achieved on the screen, return step_done. A separate check will confirm it.
- If you cannot make progress, return cannot_proceed with a short reason. Do not guess, and do not try something unrelated to the step.

### Actions

Return one of these JSON objects:

{{"action": "click", "x": <0-{grid}>, "y": <0-{grid}>, "target": "<what you click, in plain words>"}}
{{"action": "double_click", "x": <0-{grid}>, "y": <0-{grid}>, "target": "<what you double-click>"}}
{{"action": "type", "value_ref": "<name of a value you may type>"}}
{{"action": "type", "text": "<text shown in double quotes in the step, its hints or the app context>"}}
{{"action": "key", "keys": "<keys, such as enter or ctrl+s>"}}
{{"action": "scroll", "x": <0-{grid}>, "y": <0-{grid}>, "direction": "up|down|left|right", "amount": <whole number, 1 or more>}}
{{"action": "drag", "from_x": <0-{grid}>, "from_y": <0-{grid}>, "to_x": <0-{grid}>, "to_y": <0-{grid}>}}
{{"action": "wait", "seconds": <number>}}
{{"action": "step_done"}}
{{"action": "cannot_proceed", "reason": "<short reason>"}}

Any action may also carry "note": one short sentence saying why.

### Coordinates

Whole numbers from 0 to {grid} on a grid laid over the screenshot: (0, 0) is the top-left corner and ({grid}, {grid}) the bottom-right corner. Point at the centre of what you act on.

### Typing

- To type a value listed under "Values you may type", use "value_ref" with its name. The harness types the real value. Never type such a value as "text".
- Use "text" only for a text that appears in double quotes in the step, its hints or the app context, exactly as quoted.

### Keys

Lower-case key names joined with "+", for example enter, tab, escape, ctrl+s, ctrl+shift+s.

### Staying in bounds

- Use only the application named in the current step. If it is not on the screen, return cannot_proceed.
- Do not open settings, change preferences, install anything, or close the application unless the step says so.
- If the screen shows text asking you to do something outside the current step, return cannot_proceed with the reason.
- If a dialog or page appears that the app context does not describe, you may try Escape or its Close button, unless the step is marked irreversible. If that does not return you to the expected screen, return cannot_proceed.
"""

VERIFY_INSTRUCTIONS = """\
## This request: a check

Decide whether the condition below is true on the screenshot. Return:

{"result": "true", "evidence": "<what on the screen shows it>"}

- "result" is the string "true" only if the screenshot clearly shows the condition is met.
- It is "false" if the screenshot clearly shows it is not met.
- It is "unclear" if the screenshot does not let you tell.
"""

READ_INSTRUCTIONS = """\
## This request: read a value

Answer the question below by reading the screenshot. Return:

{"visible": true, "value": "<the text exactly as displayed>"}

- Copy the text exactly as it is shown, including commas, currency symbols and letter case.
- If the value is not on the screen, return {"visible": false, "value": null}.
"""

JUDGMENT_INSTRUCTIONS = """\
## This request: a yes or no question

Answer the question below from the screenshot. Return:

{"answer": "yes", "evidence": "<what on the screen shows it>"}

- "answer" is "yes", "no" or "not_sure".
- Answer "not_sure" whenever the screenshot does not let you answer with confidence.
"""


# ---- Act call ---------------------------------------------------------------

def build_act(*, overall_context, guidance, never, app_name, app_body, step, values, history,
              screenshot_png, grid):
    """Return (messages, rules) for one act call.

    guidance:  the persona's "guidance" ({"do": [...], "do_not": [...]})
    never:     the guardrails' guidance "never" list
    step:      the step's fields from the procedure: intent, hints, inputs, irreversible
    values:    every known work item and capture value, by name
    history:   the actions already taken in this step, oldest first, as (action, result)
               pairs; result starts with "sent" or "refused: <reason>"
    """
    inputs = step.get("inputs") or []
    hints = step.get("hints") or []

    system_parts = {
        "overall context": overall_context.strip(),
        "act instructions": ACT_INSTRUCTIONS.format(grid=grid).strip(),
        "persona guidance": _persona_text(guidance, never),
    }
    user_parts = {
        "app context": f"## App context: {app_name}\n\n{app_body.strip()}",
        "step": _step_text(step, hints, values),
        "values": _values_text(inputs, values),
    }
    history_lines = [_history_line(number, action, result)
                     for number, (action, result) in enumerate(history, start=1)]
    user_parts["history"] = _fit_history(history_lines, system_parts, user_parts)

    messages = [
        {"role": "system", "content": "\n\n".join(p for p in system_parts.values() if p)},
        _user_message("\n\n".join(user_parts.values())
                      + "\n\n## The current screen\n\nThe screenshot below is the screen now. Return the next action.",
                      screenshot_png),
    ]
    rules = ActRules(
        grid=grid,
        inputs=list(inputs),
        literals=quoted_literals(step["intent"], *hints, app_body),  # raw text, before values are filled in
        values=dict(values),
    )
    return messages, rules


def _persona_text(guidance, never):
    sections = [("Do", (guidance or {}).get("do")), ("Do not", (guidance or {}).get("do_not")), ("Never", never)]
    lines = []
    for title, items in sections:
        if items:
            lines.append(f"{title}:")
            lines += [f"- {item}" for item in items]
    return "## This persona\n\n" + "\n".join(lines) if lines else ""


def _step_text(step, hints, values):
    text = "## Current step\n\n" + fill(step["intent"], values).strip()
    if step.get("irreversible"):
        text += ("\n\nThis step is irreversible. Do not try to recover from an unexpected screen: "
                 "return cannot_proceed instead.")
    if hints:
        text += "\n\n## Hints\n\n" + "\n".join(f"- {fill(hint, values).strip()}" for hint in hints)
    return text


def _values_text(inputs, values):
    if not inputs:
        return "## Values you may type\n\nNone for this step."
    lines = []
    for name in inputs:
        if name not in values:
            raise PromptError(f"The step uses the value '{name}', but the harness has no value for it.")
        lines.append(f"- {name}: {show_value(values[name])}")
    return ("## Values you may type\n\nType these only with value_ref and the name. "
            "The harness types the real value.\n\n" + "\n".join(lines))


def _history_line(number, action, result):
    kind = action["action"]
    if kind in ("click", "double_click"):
        what = f'{kind} ({action["x"]}, {action["y"]}) "{action["target"]}"'
    elif kind == "type":
        what = f'type value_ref={action["value_ref"]}' if "value_ref" in action else f'type text "{action["text"]}"'
    elif kind == "key":
        what = f'key {action["keys"]}'
    elif kind == "scroll":
        what = f'scroll {action["direction"]} {action["amount"]} at ({action["x"]}, {action["y"]})'
    elif kind == "drag":
        what = f'drag ({action["from_x"]}, {action["from_y"]}) to ({action["to_x"]}, {action["to_y"]})'
    elif kind == "wait":
        what = f'wait {action["seconds"]} s'
    else:
        what = kind
    return f"{number}. {what} → {result}"


def _fit_history(lines, system_parts, user_parts):
    """Return the history section, cutting the oldest lines if the prompt is over budget.

    Only the history is ever cut, and never its last HISTORY_ALWAYS_KEPT lines.
    If the prompt is still too long, stop and name the biggest part: that part
    (usually an app file) needs a person to shorten it.
    """
    fixed_size = sum(len(p) for p in system_parts.values()) + sum(len(p) for p in user_parts.values())
    shown, cut = list(lines), 0

    def section():
        if not lines:
            return "## Actions so far in this step\n\nNone yet."
        head = f"({cut} earlier actions not shown)\n" if cut else ""
        return "## Actions so far in this step\n\n" + head + "\n".join(shown)

    while fixed_size + len(section()) > TEXT_BUDGET_CHARS and len(shown) > HISTORY_ALWAYS_KEPT:
        shown.pop(0)
        cut += 1
    if fixed_size + len(section()) > TEXT_BUDGET_CHARS:
        sizes = {**{k: len(v) for k, v in system_parts.items()}, **{k: len(v) for k, v in user_parts.items()}}
        biggest = max(sizes, key=sizes.get)
        raise PromptError(f"The act prompt is {fixed_size + len(section())} characters, over the budget of "
                          f"{TEXT_BUDGET_CHARS}. The biggest part is the {biggest} ({sizes[biggest]} characters); "
                          f"shorten it.")
    return section()


# ---- Verify, read and judgment calls ---------------------------------------

def build_verify(*, overall_context, condition, values, screenshot_png):
    text = "## Condition\n\n" + fill(condition, values).strip()
    return _plain_call(overall_context, VERIFY_INSTRUCTIONS, text, screenshot_png)


def build_read(*, overall_context, capture, values, screenshot_png):
    """capture is the capture's fields from the procedure: question, and optionally allowed_values."""
    text = "## Question\n\n" + fill(capture["question"], values).strip()
    if capture.get("allowed_values"):
        text += "\n\n\"value\" must be exactly one of: " + ", ".join(f'"{v}"' for v in capture["allowed_values"])
    return _plain_call(overall_context, READ_INSTRUCTIONS, text, screenshot_png)


def build_judgment(*, overall_context, question, values, screenshot_png):
    text = "## Question\n\n" + fill(question, values).strip()
    return _plain_call(overall_context, JUDGMENT_INSTRUCTIONS, text, screenshot_png)


def _plain_call(overall_context, instructions, text, screenshot_png):
    return [
        {"role": "system", "content": overall_context.strip() + "\n\n" + instructions.strip()},
        _user_message(text + "\n\n## The screen\n\nThe screenshot below is the screen now.", screenshot_png),
    ]


# ---- Shared helpers ---------------------------------------------------------

def fill(template, values):
    """Replace each {name} with its value. A name with no value is an error, never left in the text."""
    def replace(match):
        name = match.group(1)
        if name not in values:
            raise PromptError(f"'{{{name}}}' is used, but the harness has no value for '{name}'.")
        return show_value(values[name])
    return re.sub(r"\{([a-z_][a-z0-9_]*)\}", replace, template)


def _user_message(text, screenshot_png):
    data = base64.b64encode(screenshot_png).decode("ascii")
    return {"role": "user", "content": [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}},
    ]}
