"""Check a model's answer against docs/action-format.md.

Each check_* function takes the model's reply text and either returns a clean
dict or raises AnswerError with one plain sentence saying what is wrong. That
sentence is sent back to the model on the re-ask, so it must say how to fix
the answer. This module makes no network calls and touches nothing on screen.

AnswerError.kind says what sort of mistake it was, so the log can count them:
  "format"        not one JSON object, an unknown action, a missing or bad field
  "value_ref"     a value_ref that is not one of the step's inputs
  "literal_text"  a "type" with "text" that is not allowed as literal text

Guardrails (blocked keys, the wait cap) are not checked here. A refused action
goes to a human, not to a re-ask; that is piece 8.
"""

import json
import re
from dataclasses import dataclass, field

from harness.screen.keyboard import parse_keys


class AnswerError(Exception):
    def __init__(self, message, kind="format"):
        super().__init__(message)
        self.kind = kind


# The fields each action needs, besides "action". Every action may also carry "note".
ACTION_FIELDS = {
    "click": ["x", "y", "target"],
    "double_click": ["x", "y", "target"],
    "type": [],  # exactly one of value_ref or text, checked separately
    "key": ["keys"],
    "scroll": ["x", "y", "direction", "amount"],
    "drag": ["from_x", "from_y", "to_x", "to_y"],
    "wait": ["seconds"],
    "step_done": [],
    "cannot_proceed": ["reason"],
}
SCROLL_DIRECTIONS = ["up", "down", "left", "right"]
MIN_CONTAINED_VALUE_LENGTH = 3  # shorter values (a quantity of 5) are refused only on an exact match


@dataclass
class ActRules:
    """What an act answer is checked against. prompts.build_act makes it from the same step data as the prompt."""
    grid: int
    inputs: list = field(default_factory=list)    # names the model may use with value_ref
    literals: list = field(default_factory=list)  # texts in double quotes it may type with "text"
    values: dict = field(default_factory=dict)    # every known work item and capture value, by name


# ---- Parsing ----------------------------------------------------------------

def parse_object(raw):
    """Return the one JSON object in the reply. A single ```json fence around it is allowed."""
    text = (raw or "").strip()
    if not text:
        raise AnswerError("The answer was empty. Reply with one JSON object.")
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        answer = json.loads(text)
    except json.JSONDecodeError as error:
        raise AnswerError(f"The answer is not one JSON object ({error.msg}). Reply with the JSON object only, no other text.")
    if not isinstance(answer, dict):
        raise AnswerError("The answer must be one JSON object, in curly braces.")
    return answer


def _check_fields(answer, required, optional=(), what="The answer"):
    missing = [name for name in required if name not in answer]
    if missing:
        raise AnswerError(f"{what} is missing: {', '.join(missing)}.")
    unknown = [name for name in answer if name not in required and name not in optional]
    if unknown:
        raise AnswerError(f"{what} has fields that are not allowed: {', '.join(unknown)}.")


def _text_field(answer, name):
    value = answer[name]
    if not isinstance(value, str) or not value.strip():
        raise AnswerError(f'"{name}" must be a non-empty string.')
    return value


def _whole_number(answer, name, low, high):
    value = answer[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value):
        raise AnswerError(f'"{name}" must be a whole number from {low} to {high}.')
    value = int(value)
    if not low <= value <= high:
        raise AnswerError(f'"{name}" must be a whole number from {low} to {high}; it was {value}.')
    return value


# ---- Act call ---------------------------------------------------------------

def check_act(raw, rules):
    """Return the checked action as a dict, or raise AnswerError."""
    answer = parse_object(raw)
    action = answer.get("action")
    if action not in ACTION_FIELDS:
        raise AnswerError(f'"action" must be one of: {", ".join(ACTION_FIELDS)}.')
    what = f'A "{action}" action'
    if action == "type":
        _check_fields(answer, ["action"], ["value_ref", "text", "note"], what)
    else:
        _check_fields(answer, ["action", *ACTION_FIELDS[action]], ["note"], what)
    if "note" in answer and not isinstance(answer["note"], str):
        raise AnswerError('"note" must be a string.')

    checked = {"action": action}
    if action in ("click", "double_click"):
        checked["x"] = _whole_number(answer, "x", 0, rules.grid)
        checked["y"] = _whole_number(answer, "y", 0, rules.grid)
        checked["target"] = _text_field(answer, "target")
    elif action == "type":
        checked.update(_check_type(answer, rules))
    elif action == "key":
        keys = _text_field(answer, "keys")
        try:
            parse_keys(keys)
        except ValueError as error:
            raise AnswerError(f"{error} Use lower-case key names joined with '+', such as ctrl+s.")
        checked["keys"] = keys
    elif action == "scroll":
        checked["x"] = _whole_number(answer, "x", 0, rules.grid)
        checked["y"] = _whole_number(answer, "y", 0, rules.grid)
        if answer["direction"] not in SCROLL_DIRECTIONS:
            raise AnswerError(f'"direction" must be one of: {", ".join(SCROLL_DIRECTIONS)}.')
        checked["direction"] = answer["direction"]
        checked["amount"] = _whole_number(answer, "amount", 1, 100)
    elif action == "drag":
        for name in ACTION_FIELDS["drag"]:
            checked[name] = _whole_number(answer, name, 0, rules.grid)
    elif action == "wait":
        seconds = answer["seconds"]
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds <= 0:
            raise AnswerError('"seconds" must be a number above 0.')
        checked["seconds"] = seconds
    elif action == "cannot_proceed":
        checked["reason"] = _text_field(answer, "reason")

    if "note" in answer:
        checked["note"] = answer["note"]
    return checked


def _check_type(answer, rules):
    has_ref, has_text = "value_ref" in answer, "text" in answer
    if has_ref == has_text:
        raise AnswerError('A "type" action needs exactly one of "value_ref" or "text".')
    if has_ref:
        name = answer["value_ref"]
        if name not in rules.inputs:
            raise AnswerError(f'"value_ref" must name a value this step may type. {_allowed_refs(rules)}', kind="value_ref")
        return {"value_ref": name}

    text = _text_field(answer, "text")
    # Work item data is typed only through value_ref, even when it also appears in quotes somewhere.
    for name, value in rules.values.items():
        value = show_value(value).casefold()
        if not value:
            continue
        if text.casefold() == value or (len(value) >= MIN_CONTAINED_VALUE_LENGTH and value in text.casefold()):
            raise AnswerError(f'The text contains the value "{name}". Work item values are typed only with '
                              f'value_ref, never as text. {_allowed_refs(rules)}', kind="literal_text")
    if text not in rules.literals:
        allowed = ", ".join(f'"{literal}"' for literal in rules.literals) or "none for this step"
        raise AnswerError(f'"text" may only be a text shown in double quotes in the step, its hints or the app '
                          f'context, typed exactly as quoted. Allowed: {allowed}. {_allowed_refs(rules)}',
                          kind="literal_text")
    return {"text": text}


def _allowed_refs(rules):
    if not rules.inputs:
        return "This step has no values to type with value_ref."
    return "The value_ref names this step allows are: " + ", ".join(rules.inputs) + "."


def show_value(value):
    """A value as the harness would type it: 5.0 becomes "5"."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def quoted_literals(*texts):
    """Return every text in double quotes ("..." or “...”) in the given texts, in order, without repeats."""
    found = []
    for text in texts:
        for match in re.finditer(r'"([^"\n]+)"|“([^”\n]+)”', text or ""):
            literal = match.group(1) or match.group(2)
            if literal not in found:
                found.append(literal)
    return found


# ---- Verify, read and judgment calls ---------------------------------------

def check_verify(raw):
    answer = parse_object(raw)
    _check_fields(answer, ["result", "evidence"])
    if answer["result"] not in ("true", "false", "unclear"):
        raise AnswerError('"result" must be the string "true", "false" or "unclear".')
    return {"result": answer["result"], "evidence": _text_field(answer, "evidence")}


def check_read(raw, capture):
    """capture is the capture's fields from the procedure: "type", and optionally "allowed_values"."""
    answer = parse_object(raw)
    _check_fields(answer, ["visible", "value"])
    if not isinstance(answer["visible"], bool):
        raise AnswerError('"visible" must be true or false, without quotes.')
    if not answer["visible"]:
        if answer["value"] is not None:
            raise AnswerError('When "visible" is false, "value" must be null.')
        return {"visible": False, "value": None, "converted": None}

    value = _text_field(answer, "value")
    allowed = capture.get("allowed_values")
    if allowed and value not in allowed:
        raise AnswerError(f'"value" must be exactly one of: {", ".join(allowed)}.')
    if capture.get("type") == "number":
        try:
            converted = to_number(value)
        except ValueError:
            raise AnswerError(f'"value" must be a number as displayed, such as 4,50,000.00; it was "{value}".')
    else:
        converted = value
    return {"visible": True, "value": value, "converted": converted}


def check_judgment(raw):
    answer = parse_object(raw)
    _check_fields(answer, ["answer", "evidence"])
    if answer["answer"] not in ("yes", "no", "not_sure"):
        raise AnswerError('"answer" must be "yes", "no" or "not_sure".')
    return {"answer": answer["answer"], "evidence": _text_field(answer, "evidence")}


def to_number(text):
    """Turn a displayed amount such as "₹ 4,50,000.00" into 450000.0. Raise ValueError if it is not one."""
    cleaned = text.strip()
    for prefix in ("₹", "INR"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    if not re.fullmatch(r"-?\d[\d,]*(\.\d+)?", cleaned):
        raise ValueError(f"'{text}' is not a number")
    return float(cleaned.replace(",", ""))
