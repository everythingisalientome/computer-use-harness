"""Tests for checking model answers (harness/model/answers.py)."""

import pytest

from harness.model.answers import (ActRules, AnswerError, check_act, check_judgment, check_read,
                                   check_verify, parse_object, quoted_literals, to_number)

RULES = ActRules(
    grid=1000,
    inputs=["customer_name", "quantity"],
    literals=["Customer List", "Add Customer"],
    values={"customer_name": "Acme Robotics 1118", "quantity": 5, "reference": "REQ-0001"},
)


def refused(raw, rules=RULES):
    with pytest.raises(AnswerError) as caught:
        check_act(raw, rules)
    return caught.value


# ---- Parsing ----

def test_plain_object_and_one_fence_are_accepted():
    assert parse_object('{"action": "step_done"}') == {"action": "step_done"}
    assert parse_object('```json\n{"action": "step_done"}\n```') == {"action": "step_done"}


@pytest.mark.parametrize("raw", ["", "click at 912, 54", '{"action": "step_done"} done', "[1, 2]",
                                 'Sure: {"action": "step_done"}'])
def test_anything_but_one_object_is_refused(raw):
    assert refused(raw).kind == "format"


# ---- Act: every action ----

@pytest.mark.parametrize("raw", [
    '{"action": "click", "x": 912, "y": 54, "target": "Save button"}',
    '{"action": "double_click", "x": 0, "y": 1000, "target": "first row"}',
    '{"action": "type", "value_ref": "customer_name"}',
    '{"action": "type", "text": "Customer List"}',
    '{"action": "key", "keys": "ctrl+s"}',
    '{"action": "scroll", "x": 500, "y": 600, "direction": "down", "amount": 3}',
    '{"action": "drag", "from_x": 200, "from_y": 300, "to_x": 600, "to_y": 300}',
    '{"action": "wait", "seconds": 2}',
    '{"action": "step_done"}',
    '{"action": "cannot_proceed", "reason": "A login page is showing."}',
    '{"action": "step_done", "note": "The list is filtered."}',
])
def test_every_action_in_the_format_is_accepted(raw):
    check_act(raw, RULES)


def test_whole_number_floats_become_ints():
    assert check_act('{"action": "click", "x": 500.0, "y": 20, "target": "t"}', RULES)["x"] == 500


@pytest.mark.parametrize("raw", [
    '{"action": "hover", "x": 1, "y": 1}',                                     # unknown action
    '{"action": "click", "x": 912, "y": 54}',                                  # missing target
    '{"action": "click", "x": 1001, "y": 54, "target": "t"}',                  # off the grid
    '{"action": "click", "x": 12.5, "y": 54, "target": "t"}',                  # not whole
    '{"action": "click", "x": "912", "y": 54, "target": "t"}',                 # a string
    '{"action": "click", "x": 9, "y": 5, "target": "t", "button": "right"}',   # unknown field
    '{"action": "key", "keys": "Ctrl+S"}',                                     # not lower case
    '{"action": "key", "keys": "ctrl+banana"}',                                # unknown key
    '{"action": "scroll", "x": 5, "y": 5, "direction": "sideways", "amount": 1}',
    '{"action": "scroll", "x": 5, "y": 5, "direction": "up", "amount": 0}',
    '{"action": "wait", "seconds": 0}',
    '{"action": "wait", "seconds": true}',
    '{"action": "cannot_proceed", "reason": "  "}',
    '{"action": "type"}',                                                      # neither
    '{"action": "type", "value_ref": "quantity", "text": "Customer List"}',   # both
])
def test_malformed_actions_are_refused(raw):
    assert refused(raw).kind == "format"


# ---- Act: value_ref and literal text ----

def test_value_ref_outside_the_step_inputs_is_refused_and_names_the_allowed_ones():
    error = refused('{"action": "type", "value_ref": "reference"}')
    assert error.kind == "value_ref"
    assert "customer_name, quantity" in str(error)


def test_text_not_in_quotes_anywhere_is_refused():
    error = refused('{"action": "type", "text": "Selling"}')
    assert error.kind == "literal_text"
    assert '"Customer List"' in str(error) and "customer_name, quantity" in str(error)


def test_a_work_item_value_typed_as_text_is_refused():
    error = refused('{"action": "type", "text": "Acme Robotics 1118"}')
    assert error.kind == "literal_text" and "value_ref" in str(error)


def test_text_containing_a_value_is_refused_even_when_quoted_and_whatever_the_case():
    rules = ActRules(grid=1000, inputs=["customer_name"], literals=["Find acme robotics 1118 now"],
                     values={"customer_name": "Acme Robotics 1118"})
    assert refused('{"action": "type", "text": "Find acme robotics 1118 now"}', rules).kind == "literal_text"


def test_a_short_value_is_refused_only_on_an_exact_match():
    rules = ActRules(grid=1000, inputs=["quantity"], literals=["5", "Add 5 rows"], values={"quantity": 5})
    assert refused('{"action": "type", "text": "5"}', rules).kind == "literal_text"
    assert check_act('{"action": "type", "text": "Add 5 rows"}', rules) == {"action": "type", "text": "Add 5 rows"}


def test_quoted_literals_are_found_in_straight_and_curly_quotes():
    found = quoted_literals('Type "Customer List" here', 'Then “New Quotation”.', 'Again "Customer List"', None)
    assert found == ["Customer List", "New Quotation"]


# ---- Verify, read, judgment ----

def test_verify():
    assert check_verify('{"result": "unclear", "evidence": "Covered by a dialog."}')["result"] == "unclear"
    with pytest.raises(AnswerError):
        check_verify('{"result": true, "evidence": "x"}')  # must be the string
    with pytest.raises(AnswerError):
        check_verify('{"result": "true"}')


def test_read_number_with_indian_grouping():
    answer = check_read('{"visible": true, "value": "₹ 4,50,000.00"}', {"type": "number"})
    assert answer == {"visible": True, "value": "₹ 4,50,000.00", "converted": 450000.0}


def test_read_not_visible():
    assert check_read('{"visible": false, "value": null}', {"type": "text"})["converted"] is None
    with pytest.raises(AnswerError):
        check_read('{"visible": false, "value": "x"}', {"type": "text"})


def test_read_refuses_a_number_that_does_not_convert_and_a_value_not_allowed():
    with pytest.raises(AnswerError):
        check_read('{"visible": true, "value": "about 4 lakh"}', {"type": "number"})
    with pytest.raises(AnswerError):
        check_read('{"visible": true, "value": "Yes"}', {"type": "text", "allowed_values": ["yes", "no"]})
    with pytest.raises(AnswerError):
        check_read('{"visible": "true", "value": "yes"}', {"type": "text"})


def test_judgment():
    assert check_judgment('{"answer": "not_sure", "evidence": "Hidden."}')["answer"] == "not_sure"
    with pytest.raises(AnswerError):
        check_judgment('{"answer": "maybe", "evidence": "x"}')


@pytest.mark.parametrize("text, number", [("0.00", 0.0), ("₹ 0.00", 0.0), ("INR 1,234.5", 1234.5),
                                          ("4,50,000.00", 450000.0), ("-12", -12.0)])
def test_to_number(text, number):
    assert to_number(text) == number


@pytest.mark.parametrize("text", ["", "1.2.3", "$5", "5 lakh", "₹"])
def test_to_number_refuses(text):
    with pytest.raises(ValueError):
        to_number(text)
