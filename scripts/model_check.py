"""Show that the model client works with every model slot (build piece 2, "done when").

Usage:
  .venv\\Scripts\\python scripts\\model_check.py               every slot in model-connection.yaml
  .venv\\Scripts\\python scripts\\model_check.py --slot default

It clicks nothing. Each case sends a saved probe screenshot (probe/screens/)
with a real step, rule or capture from the quotation-creator persona, through
the same prompt builder, checker and client the step loop will use.

Two questions are answered separately:

1. Does every call return a checked answer? This is the "done when" check: it
   passes when every call for every slot ends "ok", and the forced re-ask case
   was re-asked and recovered. The forced re-ask replaces the model's first
   answer with a fixed bad one, so the real model has to read the error and
   answer again.
2. Is the answer the right one? Each case has an expected answer, for example
   a click inside the Customer Name filter box. This is evidence for piece 3,
   not part of the pass.

Output goes to output/model-check/<date-time>/:
  calls.jsonl   one line per call, as the client logs it, with durations
  summary.md    one row per call, the durations, and the result
  overlays/     each act answer with a point drawn on its screenshot, the
                expected box in green and a wrong box in red

The key is read from the environment variable named in model-connection.yaml.
"""

import argparse
import csv
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from harness.model import connection as conn  # noqa: E402
from harness.model import prompts  # noqa: E402
from harness.model.answers import check_act, check_judgment, check_read, check_verify  # noqa: E402
from harness.model.client import ModelClient  # noqa: E402
from harness.screen.grid import grid_to_pixel  # noqa: E402

CONFIG_DIR = ROOT_DIR / "config"
PERSONA_DIR = CONFIG_DIR / "personas" / "quotation-creator"
SCREENS_DIR = ROOT_DIR / "probe" / "screens"
LABELS_FILE = ROOT_DIR / "probe" / "labels.yaml"
OUTPUT_DIR = ROOT_DIR / "output" / "model-check"
PARALLEL_CALLS = 4
FORCED_BAD_ANSWER = "click at 912, 54"
SLOT_COLOURS = ["#1e6fff", "#ff7a00", "#c000c0", "#00a0a0"]

# The "Create a new Customer" entry on the quotation_suggestions screenshot, in pixels.
# Not in probe/labels.yaml; measured on that screenshot for this check only.
CREATE_NEW_CUSTOMER_BOX = [347, 612, 724, 642]

# A hand-written step for the "already done" case: the procedure has no screen
# step whose intent is already met on a saved screenshot.
EMPTY_NOTEPAD_STEP = {"id": "show-empty-notepad", "app": "notepad", "intent": "Show an empty Notepad document.",
                      "inputs": [], "irreversible": False}

CAPTURED = {"quotation_id": "SAL-QTN-2026-00001"}  # a capture an earlier step would have made


def cases(steps, rules):
    """The calls to make for each slot. "expect" says what the right answer is."""
    return [
        {"id": "filter-customer-list", "call": "act", "screen": "customer_list", "step": steps["check-customer"],
         "expect": {"click_in": ["customer_name_filter"]}},
        {"id": "forced-reask", "call": "act", "screen": "customer_list", "step": steps["check-customer"],
         "force_bad_first": True, "expect": {"click_in": ["customer_name_filter"]}},
        {"id": "new-customer-first-field", "call": "act", "screen": "new_customer", "step": steps["create-customer"],
         "expect": {"click_in": ["customer_name_field", "customer_type_field", "customer_group_field",
                                 "territory_field"]}},
        {"id": "quotation-customer-field", "call": "act", "screen": "new_quotation", "step": steps["fill-quotation"],
         "expect": {"click_in": ["customer_field"]}},
        {"id": "pick-matching-suggestion", "call": "act", "screen": "quotation_suggestions",
         "step": steps["fill-quotation"], "values": {"customer_name": "Acme Industries"},
         "expect": {"click_in": ["first_suggestion"], "wrong_box": CREATE_NEW_CUSTOMER_BOX}},
        {"id": "already-done", "call": "act", "screen": "notepad", "step": EMPTY_NOTEPAD_STEP,
         "expect": {"action": "step_done"}},
        {"id": "wrong-app-on-screen", "call": "act", "screen": "customer_list", "step": steps["write-note"],
         "expect": {"action": "cannot_proceed"}},
        {"id": "notepad-new-document", "call": "act", "screen": "notepad", "step": steps["write-note"],
         "expect": {"any_of": [{"action": "key", "keys": "ctrl+n"}, {"action": "type", "value_ref": "reference"}]}},
        {"id": "save-as-file-name", "call": "act", "screen": "notepad_save_as", "step": steps["save-note"],
         "expect": {"click_in": ["file_name_box"], "or": {"action": "type", "value_ref": "note_file"}}},
        {"id": "verify-home-showing", "call": "verify", "screen": "home",
         "condition": steps["open-erpnext"]["done_when"], "expect": {"result": "true"}},
        {"id": "verify-filter-not-applied", "call": "verify", "screen": "customer_list",
         "condition": steps["check-customer"]["done_when"], "expect": {"result": "false"}},
        {"id": "read-total", "call": "read", "screen": "new_quotation",
         "capture": capture(steps["read-total"], "quotation_total"), "expect": {"converted": 0.0}},
        {"id": "read-customer-exists", "call": "read", "screen": "customer_list",
         "capture": capture(steps["check-customer"], "customer_exists"), "values": {"customer_name": "Acme Industries"},
         "expect": {"converted": "yes"}},
        {"id": "judge-customer-matches", "call": "judgment", "screen": "new_quotation",
         "question": rules["customer-on-quotation-matches"]["question"], "expect": {"answer": "no"}},
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", help="only this model slot")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # answers can hold ₹, which the Windows console code page lacks

    connection = conn.load()
    slots = [args.slot] if args.slot else list(connection["models"])
    config = load_config()
    labels = yaml.safe_load(LABELS_FILE.read_text(encoding="utf-8"))

    out_dir = OUTPUT_DIR / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    (out_dir / "overlays").mkdir(parents=True)
    log_path = out_dir / "calls.jsonl"
    real_client = ModelClient(connection, log_path=log_path)

    jobs = [(slot, case) for slot in slots for case in cases(config["steps"], config["rules"])]
    print(f"{len(jobs)} calls to make ({len(slots)} slot(s))...")

    def run(job):
        slot, case = job
        client = forced_bad_client(connection, real_client, log_path) if case.get("force_bad_first") else real_client
        result = run_case(client, slot, case, config, connection["coordinate_grid"])
        print(f"  {slot:10} {case['id']:28} {result.outcome}")
        return slot, case, result

    with ThreadPoolExecutor(max_workers=PARALLEL_CALLS) as pool:
        rows = list(pool.map(run, jobs))

    rows = [(slot, case, result, judge(case, result, labels, connection["coordinate_grid"]))
            for slot, case, result in rows]
    draw_overlays(out_dir / "overlays", rows, labels, slots, connection["coordinate_grid"])
    summary, passed = write_summary(out_dir / "summary.md", rows, slots, connection)
    print()
    print(summary)
    print(f"Results in {out_dir}")
    sys.exit(0 if passed else 1)


# ---- Loading the persona's files (piece 4 replaces this with checked loading) ----

def load_config():
    def load_yaml(path):
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    persona = load_yaml(PERSONA_DIR / "persona.yaml")
    guardrails = load_yaml(PERSONA_DIR / "guardrails.yaml")
    procedure = load_yaml(PERSONA_DIR / "procedure.yaml")
    rules = load_yaml(PERSONA_DIR / "rules.yaml")
    apps = {}
    for app_id in persona["apps"]:
        text = (CONFIG_DIR / "apps" / f"{app_id}.md").read_text(encoding="utf-8")
        match = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.DOTALL)
        apps[app_id] = {"header": yaml.safe_load(match.group(1)), "body": match.group(2)}
    with open(ROOT_DIR / "input" / "quotation-requests.csv", newline="", encoding="utf-8") as f:
        work_item = next(csv.DictReader(f))  # REQ-0001
    return {
        "overall_context": (CONFIG_DIR / "overall-context.md").read_text(encoding="utf-8"),
        "guidance": persona.get("guidance", {}),
        "never": guardrails.get("guidance", {}).get("never", []),
        "steps": {step["id"]: step for step in procedure["steps"]},
        "rules": {rule["id"]: rule for rule in rules["rules"]},
        "apps": apps,
        "work_item": {name: work_item[name] for name in procedure["work_item"]["fields"]},
    }


def capture(step, name):
    return next(c for c in step["captures"] if c["name"] == name)


# ---- Running one case ----

def run_case(client, slot, case, config, grid):
    png = (SCREENS_DIR / f"{case['screen']}.png").read_bytes()
    values = {**config["work_item"], **CAPTURED, **case.get("values", {})}
    step_id = case["step"]["id"] if "step" in case else None
    if case["call"] == "act":
        app = config["apps"][case["step"]["app"]]
        messages, rules = prompts.build_act(
            overall_context=config["overall_context"], guidance=config["guidance"], never=config["never"],
            app_name=app["header"]["name"], app_body=app["body"], step=case["step"], values=values,
            history=[], screenshot_png=png, grid=grid)
        check = lambda raw: check_act(raw, rules)  # noqa: E731
    elif case["call"] == "verify":
        messages = prompts.build_verify(overall_context=config["overall_context"], condition=case["condition"],
                                        values=values, screenshot_png=png)
        check = check_verify
    elif case["call"] == "read":
        messages = prompts.build_read(overall_context=config["overall_context"], capture=case["capture"],
                                      values=values, screenshot_png=png)
        check = lambda raw: check_read(raw, case["capture"])  # noqa: E731
    else:
        messages = prompts.build_judgment(overall_context=config["overall_context"], question=case["question"],
                                          values=values, screenshot_png=png)
        check = check_judgment
    return client.ask(case["call"], slot, messages, check, step=step_id, label=case["id"])


def forced_bad_client(connection, real_client, log_path):
    """A client whose first answer is FORCED_BAD_ANSWER; the re-ask goes to the real model."""
    state = {"first": True}

    def send(model, temperature, messages):
        if state["first"]:
            state["first"] = False
            return FORCED_BAD_ANSWER
        return real_client._send(model, temperature, messages)

    return ModelClient(connection, send=send, log_path=log_path)


# ---- Judging the answers ----

def judge(case, result, labels, grid):
    """Return (as_expected, detail) for one call. as_expected is None when there is no checked answer."""
    if result.outcome != "ok":
        return None, result.problem or result.outcome
    answer, expect = result.answer, case["expect"]
    if "click_in" in expect:
        if answer["action"] in ("click", "double_click"):
            px, py = to_pixel(case["screen"], answer["x"], answer["y"], grid)
            for element in expect["click_in"]:
                if inside(labels[case["screen"]][element], px, py):
                    return True, f"inside {element}"
            if "wrong_box" in expect and inside(expect["wrong_box"], px, py):
                return False, "clicked the wrong entry (Create a new Customer)"
            return False, f"click at pixel ({px}, {py}) is outside {', '.join(expect['click_in'])}"
        if "or" in expect and all(answer.get(k) == v for k, v in expect["or"].items()):
            return True, "accepted alternative"
        return False, f"expected a click in {', '.join(expect['click_in'])}"
    if "any_of" in expect:
        ok = any(all(answer.get(k) == v for k, v in option.items()) for option in expect["any_of"])
        return ok, "" if ok else "expected one of: " + "; ".join(json.dumps(o) for o in expect["any_of"])
    key, wanted = next(iter(expect.items()))
    got = answer.get(key)
    return got == wanted, "" if got == wanted else f"expected {key} {wanted!r}, got {got!r}"


def to_pixel(screen, gx, gy, grid):
    with Image.open(SCREENS_DIR / f"{screen}.png") as image:
        width, height = image.size
    return grid_to_pixel(gx, gy, width, height, grid)


def inside(box, x, y):
    left, top, right, bottom = box
    return left <= x <= right and top <= y <= bottom


# ---- Writing the results ----

def write_summary(path, rows, slots, connection):
    lines = [f"# Model check, {datetime.now():%Y-%m-%d %H:%M}", "",
             "Saved probe screenshots, real steps from the quotation-creator persona. Nothing was clicked.", "",
             "| Slot | Case | Call | Outcome | Re-asked | Seconds | Answer | As expected | Detail |",
             "|---|---|---|---|---|---|---|---|---|"]
    for slot, case, result, (expected, detail) in rows:
        answer = json.dumps(result.answer, ensure_ascii=False) if result.answer else ""
        lines.append(f"| {slot} | {case['id']} | {case['call']} | {result.outcome} | "
                     f"{'yes' if result.reasked else 'no'} | {result.seconds:.1f} | {cell(answer)} | "
                     f"{ {True: 'yes', False: 'NO', None: '-'}[expected] } | {cell(detail)} |")

    lines += ["", "| Slot | Model | Checked answers | Forced re-ask recovered | As expected | "
                  "Seconds per call (mean / max) |", "|---|---|---|---|---|---|"]
    passed = True
    for slot in slots:
        mine = [r for r in rows if r[0] == slot]
        ok = sum(1 for r in mine if r[2].outcome == "ok")
        forced = [r[2] for r in mine if r[1].get("force_bad_first")]
        recovered = all(r.reasked and r.outcome == "ok" and r.attempts[0]["raw"] == FORCED_BAD_ANSWER for r in forced)
        expected = sum(1 for r in mine if r[3][0])
        seconds = [r[2].seconds for r in mine]
        lines.append(f"| {slot} | {connection['models'][slot]['model']} | {ok} of {len(mine)} | "
                     f"{'yes' if recovered else 'NO'} | {expected} of {len(mine)} | "
                     f"{sum(seconds) / len(seconds):.1f} / {max(seconds):.1f} |")
        passed = passed and ok == len(mine) and recovered

    lines += ["", ("**PASS**: every call returned a checked answer for every slot, and the forced re-ask recovered."
                   if passed else "**FAIL**: see the rows above whose outcome is not ok, or the forced re-ask."),
              "", "\"As expected\" is evidence for piece 3 and not part of the pass."]
    text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")
    return text, passed


def cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def draw_overlays(out_dir, rows, labels, slots, grid):
    colours = {slot: SLOT_COLOURS[i % len(SLOT_COLOURS)] for i, slot in enumerate(slots)}
    for slot, case, result, (expected, _) in rows:
        if case["call"] != "act" or not result.answer:
            continue
        image = Image.open(SCREENS_DIR / f"{case['screen']}.png").convert("RGB")
        draw = ImageDraw.Draw(image)
        for element in case["expect"].get("click_in", []):
            draw.rectangle(labels[case["screen"]][element], outline="#00c000", width=3)
        if "wrong_box" in case["expect"]:
            draw.rectangle(case["expect"]["wrong_box"], outline="#e00000", width=3)
        caption = f"{slot} / {case['id']}: {json.dumps(result.answer, ensure_ascii=False)}"
        if "x" in result.answer:
            x, y = to_pixel(case["screen"], result.answer["x"], result.answer["y"], grid)
            draw.ellipse([x - 8, y - 8, x + 8, y + 8], fill=colours[slot], outline="#000000")
        draw.rectangle([0, 0, min(image.width, 12 + 7 * len(caption)), 22], fill="#ffffff")
        draw.text((6, 5), caption, fill=colours[slot])
        image.save(out_dir / f"{case['id']}__{slot}.png")


if __name__ == "__main__":
    main()
