"""Tests for building model prompts (harness/model/prompts.py)."""

import pytest

from harness.model import prompts
from harness.model.prompts import PromptError, build_act, build_judgment, build_read, build_verify, fill

PNG = b"\x89PNG fake"
STEP = {
    "intent": "Show the Customer list filtered to the customer name {customer_name}.",
    "inputs": ["customer_name"],
    "hints": ['Type "Customer List" into the search box.'],
    "irreversible": False,
}
VALUES = {"customer_name": "Acme Robotics 1118", "reference": "REQ-0001"}


def act(**changes):
    args = dict(overall_context="OVERALL", guidance={"do": ["Do this."], "do_not": ["Not that."]},
                never=["Never submit."], app_name="ERPNext", app_body='Open "New Quotation" from search.',
                step=STEP, values=VALUES, history=[], screenshot_png=PNG, grid=1000)
    args.update(changes)
    return build_act(**args)


def texts(messages):
    return messages[0]["content"], messages[1]["content"][0]["text"]


def test_act_prompt_holds_every_part_in_order_with_the_screenshot_last():
    messages, _ = act()
    system, user = texts(messages)
    assert system.index("OVERALL") < system.index("next action") < system.index("Never submit.")
    for part in ["App context: ERPNext", "Acme Robotics 1118.", "## Hints", "- customer_name: Acme Robotics 1118",
                 "None yet."]:
        assert part in user
    assert user.index("App context") < user.index("Current step") < user.index("Values you may type") \
        < user.index("Actions so far")
    assert messages[1]["content"][-1]["type"] == "image_url"


def test_act_rules_come_from_the_raw_template_text():
    _, rules = act()
    assert rules.inputs == ["customer_name"]
    assert rules.literals == ["Customer List", "New Quotation"]
    assert rules.values == VALUES


def test_only_the_act_call_gets_persona_guidance():
    for messages in [
        build_verify(overall_context="OVERALL", condition="The list shows {customer_name}.", values=VALUES,
                     screenshot_png=PNG),
        build_read(overall_context="OVERALL", capture={"question": "Shown?", "allowed_values": ["yes", "no"]},
                   values=VALUES, screenshot_png=PNG),
        build_judgment(overall_context="OVERALL", question="Same as {customer_name}?", values=VALUES,
                       screenshot_png=PNG),
    ]:
        system, user = texts(messages)
        assert "OVERALL" in system and "Never submit." not in system and "next action" not in system
        assert "App context" not in user and "Actions so far" not in user


def test_verify_fills_real_values():
    _, user = texts(build_verify(overall_context="O", condition="The list shows {customer_name}.", values=VALUES,
                                 screenshot_png=PNG))
    assert "The list shows Acme Robotics 1118." in user


def test_irreversible_step_is_marked():
    _, user = texts(act(step={**STEP, "irreversible": True})[0])
    assert "This step is irreversible" in user


def test_history_lines_say_sent_and_never_show_typed_values():
    history = [({"action": "click", "x": 400, "y": 120, "target": "Customer Name filter"}, "sent"),
               ({"action": "type", "value_ref": "customer_name"}, "sent"),
               ({"action": "key", "keys": "alt+f4"}, "refused: blocked key")]
    _, user = texts(act(history=history)[0])
    assert '1. click (400, 120) "Customer Name filter" → sent' in user
    assert "2. type value_ref=customer_name → sent" in user
    assert "3. key alt+f4 → refused: blocked key" in user


def test_a_missing_value_is_an_error_not_left_in_the_prompt():
    with pytest.raises(PromptError):
        fill("Set {quotation_id}", VALUES)
    with pytest.raises(PromptError):
        act(step={**STEP, "inputs": ["quotation_id"]})


def test_history_is_cut_oldest_first_and_the_last_five_are_kept(monkeypatch):
    lines = [f"{n}. wait {n} s → sent" for n in range(1, 16)]
    fixed = {"a": "x" * 1000}
    full = prompts._fit_history(lines, fixed, {})
    monkeypatch.setattr(prompts, "TEXT_BUDGET_CHARS", 1000 + len(full) - 1)  # one character too small
    section = prompts._fit_history(lines, fixed, {})
    assert "earlier actions not shown" in section
    assert "15. wait 15 s" in section and "1. wait 1 s →" not in section

    monkeypatch.setattr(prompts, "TEXT_BUDGET_CHARS", 1001)  # far too small: the last five stay, then it stops
    with pytest.raises(PromptError):
        prompts._fit_history(lines, fixed, {})


def test_a_too_long_app_file_stops_with_its_name(monkeypatch):
    monkeypatch.setattr(prompts, "TEXT_BUDGET_CHARS", 5_000)
    with pytest.raises(PromptError) as caught:
        act(app_body="x" * 6_000)
    assert "app context" in str(caught.value)
