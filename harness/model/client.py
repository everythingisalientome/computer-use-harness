"""Send one model call, check the answer, and re-ask once if it is malformed.

ask() always returns a CallResult with one of three outcomes:

  "ok"              the answer passed its check (perhaps after the one re-ask)
  "failed_attempt"  the answer failed its check twice; the step loop counts it
                    against the step's on_fail retries
  "unavailable"     the provider could not be reached or was overloaded
                    (connection error, timeout, rate limit, server error) even
                    after the OpenAI library's own retries. This is not a
                    failed attempt: the run pauses with its state intact
                    (piece 3), and nothing is counted against the step.

Two things stop the call with an exception instead, because they are mistakes
in the set-up, not in the model's answer:

  SecretInPrompt     a registered secret is in the messages; nothing is sent
  ModelConfigError   the provider refused the settings (bad key, unknown model)

The secret register: any code that handles a secret (the vault login tool, in
a later build) registers it with register_secret(). Before every send, every
text in the messages is searched for every registered secret. The register is
empty in this build because nothing in it handles passwords.

Every call can be appended to a JSONL log, one line per ask(), with each
attempt's raw answer, the reason it was refused, and how long it took. The
prompt itself is never logged.
"""

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime

import openai

from . import connection as conn
from .answers import AnswerError

TRANSPORT_RETRIES = 2  # the OpenAI library's own retries on connection errors, 429 and 5xx

log = logging.getLogger("harness.model")

_secrets = set()
_log_lock = threading.Lock()  # several clients and threads may append to one log file


class SecretInPrompt(Exception):
    """A registered secret was found in the messages. The call was not sent."""


class ModelUnavailable(Exception):
    """The provider could not be reached or was overloaded."""


def register_secret(value):
    if value:
        _secrets.add(str(value))


def forget_secrets():
    _secrets.clear()


@dataclass
class CallResult:
    outcome: str                 # "ok", "failed_attempt" or "unavailable"
    call_type: str               # "act", "verify", "read" or "judgment"
    slot: str
    model: str
    answer: dict = None          # the checked answer when outcome is "ok"
    problem: str = None          # why the outcome is not "ok"
    attempts: list = field(default_factory=list)  # {"raw", "error", "error_kind", "seconds"} per send
    seconds: float = 0.0         # the whole call, both attempts included
    step: str = None
    label: str = None

    @property
    def reasked(self):
        return len(self.attempts) > 1


class ModelClient:
    def __init__(self, connection, send=None, log_path=None):
        """connection: the dict from connection.load().
        send: a function (model, temperature, messages) -> reply text. Leave it out to use
              the provider in the connection file; tests pass a fake.
        log_path: a JSONL file to append one line per call to, or None.
        """
        self.connection = connection
        self.log_path = log_path
        self._send = send or _openai_sender(connection)

    def ask(self, call_type, slot_name, messages, check, step=None, label=None):
        """Send the call, check the answer with check(raw) -> dict, and re-ask once if it raises AnswerError."""
        model = conn.slot(self.connection, slot_name)
        result = CallResult(outcome="failed_attempt", call_type=call_type, slot=slot_name,
                            model=model["model"], step=step, label=label)
        started = time.perf_counter()
        messages = list(messages)
        for attempt in (1, 2):
            _refuse_secrets(messages)
            sent_at = time.perf_counter()
            try:
                raw = self._send(model["model"], model["temperature"], messages)
            except ModelUnavailable as error:
                result.outcome, result.problem = "unavailable", str(error)
                result.attempts.append({"raw": None, "error": str(error), "error_kind": "unavailable",
                                        "seconds": round(time.perf_counter() - sent_at, 2)})
                break
            record = {"raw": raw, "error": None, "error_kind": None,
                      "seconds": round(time.perf_counter() - sent_at, 2)}
            result.attempts.append(record)
            try:
                result.answer = check(raw)
                result.outcome = "ok"
                break
            except AnswerError as error:
                record["error"], record["error_kind"] = str(error), error.kind
                log.warning("%s answer refused (%s), attempt %d: %s", call_type, error.kind, attempt, error)
                result.problem = f"Malformed answer twice. Last error: {error}"
                messages += [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": f"That answer was not accepted: {error} Reply again with "
                                                f"exactly one JSON object in the required format, and nothing else."},
                ]
        result.seconds = round(time.perf_counter() - started, 2)
        if result.outcome == "ok":
            result.problem = None
        self._write_log(result)
        return result

    def _write_log(self, result):
        if not self.log_path:
            return
        line = {"time": datetime.now().isoformat(timespec="seconds"), **asdict(result)}
        with _log_lock, open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def _refuse_secrets(messages):
    """Raise SecretInPrompt if any registered secret appears in any text of the messages."""
    if not _secrets:
        return
    for message in messages:
        content = message["content"]
        texts = [content] if isinstance(content, str) else [p.get("text", "") for p in content if p.get("type") == "text"]
        for text in texts:
            if any(secret in text for secret in _secrets):
                # Never say which secret, or show the text around it.
                raise SecretInPrompt("A registered secret is in the prompt. The call was not sent.")


def _openai_sender(connection):
    """Return send(model, temperature, messages) for the provider in the connection file."""
    client = openai.OpenAI(base_url=connection["base_url"], api_key=conn.api_key(connection),
                           timeout=connection["timeout_seconds"], max_retries=TRANSPORT_RETRIES)

    def send(model, temperature, messages):
        try:
            response = client.chat.completions.create(model=model, temperature=temperature, messages=messages)
        except (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError) as error:
            # APITimeoutError is a kind of APIConnectionError.
            raise ModelUnavailable(f"{type(error).__name__}: {error}")
        except openai.APIStatusError as error:
            raise conn.ModelConfigError(f"The provider refused the call ({error.status_code}): {error.message}")
        if not response.choices:
            # Some gateways answer 200 with an error body and no choices when the model behind them fails.
            raise ModelUnavailable("The provider returned no answer.")
        return response.choices[0].message.content or ""

    return send
