"""Tests for the model client (harness/model/client.py), with a fake model instead of the provider."""

import json

import pytest

from harness.model.answers import ActRules, check_act
from harness.model.client import ModelClient, ModelUnavailable, SecretInPrompt, forget_secrets, register_secret

CONNECTION = {"base_url": "http://fake", "api_key_env": "UNUSED", "timeout_seconds": 5, "coordinate_grid": 1000,
              "models": {"default": {"model": "fake/model", "temperature": 0}}}
RULES = ActRules(grid=1000, inputs=["customer_name"], literals=[], values={"customer_name": "Acme Robotics 1118"})
MESSAGES = [{"role": "system", "content": "context"},
            {"role": "user", "content": [{"type": "text", "text": "Show the Customer list."},
                                         {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}}]}]
GOOD = '{"action": "click", "x": 400, "y": 120, "target": "Customer Name filter"}'


class FakeModel:
    """Replies with the given answers in order, and remembers what it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.sent = []

    def __call__(self, model, temperature, messages):
        self.sent.append(messages)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def ask(fake, tmp_path=None):
    client = ModelClient(CONNECTION, send=fake, log_path=tmp_path / "calls.jsonl" if tmp_path else None)
    return client.ask("act", "default", MESSAGES, lambda raw: check_act(raw, RULES), step="check-customer")


def test_good_answer_first_time():
    fake = FakeModel(GOOD)
    result = ask(fake)
    assert result.outcome == "ok" and not result.reasked and result.answer["x"] == 400
    assert len(fake.sent) == 1


def test_bad_then_good_is_one_reask_carrying_the_error():
    fake = FakeModel("click at 912, 54", GOOD)
    result = ask(fake)
    assert result.outcome == "ok" and result.reasked
    reask = fake.sent[1]
    assert reask[-2] == {"role": "assistant", "content": "click at 912, 54"}
    assert "not accepted" in reask[-1]["content"] and "JSON" in reask[-1]["content"]


def test_bad_twice_is_a_failed_attempt_and_there_is_no_third_call():
    fake = FakeModel("click at 912, 54", '{"action": "hover"}')
    result = ask(fake)
    assert result.outcome == "failed_attempt" and result.answer is None
    assert len(fake.sent) == 2 and all(a["error"] for a in result.attempts)


def test_unknown_value_ref_is_reasked_naming_the_allowed_names_and_logged(tmp_path, caplog):
    fake = FakeModel('{"action": "type", "value_ref": "reference"}', '{"action": "type", "value_ref": "customer_name"}')
    result = ask(fake, tmp_path)
    assert result.outcome == "ok"
    assert "customer_name" in fake.sent[1][-1]["content"]
    assert "value_ref" in caplog.text
    line = json.loads((tmp_path / "calls.jsonl").read_text(encoding="utf-8"))
    assert line["attempts"][0]["error_kind"] == "value_ref"


def test_unavailable_is_its_own_outcome_and_not_a_failed_attempt():
    result = ask(FakeModel(ModelUnavailable("RateLimitError: busy")))
    assert result.outcome == "unavailable" and "busy" in result.problem


def test_every_call_is_logged_with_its_duration(tmp_path):
    ask(FakeModel("nonsense", GOOD), tmp_path)
    line = json.loads((tmp_path / "calls.jsonl").read_text(encoding="utf-8"))
    assert line["outcome"] == "ok" and line["step"] == "check-customer"
    assert isinstance(line["seconds"], float) and all("seconds" in a for a in line["attempts"])
    assert "messages" not in line  # the prompt is never logged


def test_a_registered_secret_stops_the_call_before_anything_is_sent():
    register_secret("hunter2-fake-secret")
    try:
        fake = FakeModel(GOOD)
        messages = [MESSAGES[0], {"role": "user", "content": [{"type": "text", "text": "Password: hunter2-fake-secret"}]}]
        client = ModelClient(CONNECTION, send=fake)
        with pytest.raises(SecretInPrompt) as caught:
            client.ask("act", "default", messages, lambda raw: check_act(raw, RULES))
        assert fake.sent == []
        assert "hunter2" not in str(caught.value)
    finally:
        forget_secrets()


def test_without_the_secret_the_same_client_sends():
    register_secret("hunter2-fake-secret")
    try:
        assert ask(FakeModel(GOOD)).outcome == "ok"
    finally:
        forget_secrets()
