"""Ask each model to point at each labelled element, and score the answers.

Usage:
  .venv\\Scripts\\python probe\\run_probe.py                  all screens, 3 runs each
  .venv\\Scripts\\python probe\\run_probe.py --repeats 1      one run each
  .venv\\Scripts\\python probe\\run_probe.py --screen home    one screen only (a quick try)

Models and the connection come from config/model-connection.yaml: every slot
under "models" is tested. The key is read from the environment variable named
there and is never printed or saved.

Output goes to probe/results/<date-time>/:
  answers.csv    one line per model call
  summary.md     the table: hits per element per model, and totals
  overlays/      each screenshot with the true boxes and every answer drawn on it
"""

import argparse
import base64
import csv
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from openai import OpenAI
from PIL import Image, ImageDraw

from common import MODEL_CONNECTION_FILE, RESULTS_DIR, SCREENS_DIR, load_labels, load_screens, load_yaml
from harness.screen.grid import grid_to_pixel

PROMPT_VERSION = 1
SYSTEM_PROMPT = """You locate elements on a screenshot of a computer screen.

Answer with exactly one JSON object and nothing else: {"x": <whole number>, "y": <whole number>}

x and y are on a 0 to 1000 grid laid over the screenshot: (0, 0) is the top-left corner,
(1000, 1000) is the bottom-right corner. x runs left to right, y runs top to bottom.
Give the point you would click to act on the element: its centre.
If the element is not on the screen, answer {"x": null, "y": null}."""

PARALLEL_CALLS = 6
MODEL_COLOURS = ["#1e6fff", "#ff7a00", "#c000c0", "#00a0a0"]  # one per model slot, in order


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--screen", help="only this screen id")
    args = parser.parse_args()

    connection = load_yaml(MODEL_CONNECTION_FILE)
    api_key = os.environ.get(connection["api_key_env"])
    if not api_key:
        sys.exit(f"Set the environment variable {connection['api_key_env']} first.")
    client = OpenAI(base_url=connection["base_url"], api_key=api_key, timeout=connection["timeout_seconds"])
    grid = connection["coordinate_grid"]
    slots = connection["models"]  # {slot_name: {model, temperature}}

    check_model_names(client, slots)

    jobs = build_jobs(args, slots)
    if not jobs:
        sys.exit("Nothing to test. Capture screenshots and label them first.")
    print(f"{len(jobs)} model calls to make...")

    images = {job["screen_id"]: encode_image(job["screen_id"]) for job in jobs}

    def run(job):
        result = ask_model(client, slots[job["slot"]], images[job["screen_id"]]["data_url"], job["element_name"], grid)
        return score(job, result, images[job["screen_id"]]["size"], grid)

    rows = []
    with ThreadPoolExecutor(max_workers=PARALLEL_CALLS) as pool:
        for count, row in enumerate(pool.map(run, jobs), start=1):
            rows.append(row)
            if count % 10 == 0 or count == len(jobs):
                print(f"  {count}/{len(jobs)} done")

    out_dir = RESULTS_DIR / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    (out_dir / "overlays").mkdir(parents=True)
    write_answers_csv(out_dir / "answers.csv", rows)
    summary = write_summary(out_dir / "summary.md", rows, slots, args.repeats)
    draw_overlays(out_dir / "overlays", rows, slots)
    print()
    print(summary)
    print(f"Results in {out_dir}")


def check_model_names(client, slots):
    """Stop early if a configured model name is not offered by the provider."""
    try:
        offered = {model.id for model in client.models.list()}
    except Exception as error:  # some local servers have no model list
        print(f"Could not list the provider's models ({error}); continuing without the check.")
        return
    missing = [s["model"] for s in slots.values() if s["model"] not in offered]
    if missing:
        sys.exit(f"Not offered by the provider: {', '.join(missing)}. Fix config/model-connection.yaml.")
    print("Model names checked: " + ", ".join(s["model"] for s in slots.values()))


def build_jobs(args, slots):
    labels = load_labels()
    jobs = []
    for screen in load_screens():
        if args.screen and screen["id"] != args.screen:
            continue
        if not (SCREENS_DIR / f"{screen['id']}.png").exists():
            continue
        for element in screen["elements"]:
            box = labels.get(screen["id"], {}).get(element["id"])
            if box is None:
                continue
            for slot in slots:
                for run_number in range(1, args.repeats + 1):
                    jobs.append({
                        "screen_id": screen["id"],
                        "element_id": element["id"],
                        "element_name": element["name"],
                        "box": box,
                        "slot": slot,
                        "run": run_number,
                    })
    return jobs


def encode_image(screen_id):
    path = SCREENS_DIR / f"{screen_id}.png"
    with Image.open(path) as image:
        size = image.size
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"data_url": f"data:image/png;base64,{data}", "size": size}


def ask_model(client, slot, data_url, element_name, grid):
    """Return {"x", "y", "raw", "error"}. A bad answer is asked again once, as the harness will."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": f"Element: {element_name}"},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]},
    ]
    raw = ""
    for attempt in (1, 2):
        try:
            response = client.chat.completions.create(
                model=slot["model"], temperature=slot.get("temperature", 0), messages=messages)
            raw = response.choices[0].message.content or ""
        except Exception as error:
            return {"x": None, "y": None, "raw": raw, "error": f"call failed: {error}"}
        x, y, problem = parse_point(raw, grid)
        if problem is None:
            return {"x": x, "y": y, "raw": raw, "error": ""}
        if attempt == 1:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"That answer was not valid: {problem} Answer again with only the JSON object."})
    return {"x": None, "y": None, "raw": raw, "error": f"bad answer twice: {problem}"}


def parse_point(raw, grid):
    """Return (x, y, problem). problem is None when the answer is valid."""
    match = re.search(r"\{.*?\}", raw, re.DOTALL)  # tolerate ```json fences or a stray sentence
    if not match:
        return None, None, "no JSON object found."
    try:
        answer = json.loads(match.group(0))
    except json.JSONDecodeError as error:
        return None, None, f"not valid JSON ({error})."
    if not isinstance(answer, dict) or "x" not in answer or "y" not in answer:
        return None, None, "the object needs both x and y."
    x, y = answer["x"], answer["y"]
    if x is None and y is None:
        return None, None, None  # the model says the element is not on screen
    if not all(isinstance(v, (int, float)) and 0 <= v <= grid for v in (x, y)):
        return None, None, f"x and y must be numbers from 0 to {grid}."
    return round(x), round(y), None


def score(job, result, size, grid):
    width, height = size
    row = {**job, **result, "pixel_x": None, "pixel_y": None, "hit": False, "distance_px": None}
    if result["x"] is None:
        return row
    px, py = grid_to_pixel(result["x"], result["y"], width, height, grid)  # the harness's own conversion
    left, top, right, bottom = job["box"]
    # How far the point is outside the box, in pixels. 0 means inside.
    dx = max(left - px, 0, px - right)
    dy = max(top - py, 0, py - bottom)
    row.update(pixel_x=px, pixel_y=py, distance_px=round((dx * dx + dy * dy) ** 0.5),
               hit=(dx == 0 and dy == 0))
    return row


def write_answers_csv(path, rows):
    columns = ["screen_id", "element_id", "slot", "run", "x", "y", "pixel_x", "pixel_y",
               "hit", "distance_px", "box", "error", "raw"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path, rows, slots, repeats):
    slot_names = list(slots)
    elements = []  # (screen_id, element_id) in the order tested
    for row in rows:
        key = (row["screen_id"], row["element_id"])
        if key not in elements:
            elements.append(key)

    def hits(screen_id, element_id, slot):
        return sum(1 for r in rows if r["slot"] == slot and r["screen_id"] == screen_id
                   and r["element_id"] == element_id and r["hit"])

    header = ["Screen", "Element"] + [f"{s} ({slots[s]['model']})" for s in slot_names]
    lines = [
        f"# Pointing probe, {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"Prompt version {PROMPT_VERSION}. {repeats} run(s) per element per model. "
        f"A cell shows how many runs landed inside the element's true box.",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]
    for screen_id, element_id in elements:
        cells = [f"{hits(screen_id, element_id, s)}/{repeats}" for s in slot_names]
        lines.append(f"| {screen_id} | {element_id} | " + " | ".join(cells) + " |")

    total = len(elements)
    lines += ["", "| Total | " + " | ".join(slot_names) + " |", "|---|" + "---|" * len(slot_names)]
    every = [sum(1 for e in elements if hits(*e, s) == repeats) for s in slot_names]
    some = [sum(1 for e in elements if hits(*e, s) > 0) for s in slot_names]
    calls = [sum(1 for r in rows if r["slot"] == s and r["hit"]) for s in slot_names]
    errors = [sum(1 for r in rows if r["slot"] == s and r["error"]) for s in slot_names]
    lines.append("| Elements located in every run | " + " | ".join(f"{n} of {total}" for n in every) + " |")
    lines.append("| Elements located in at least one run | " + " | ".join(f"{n} of {total}" for n in some) + " |")
    lines.append("| Hits, all runs | " + " | ".join(f"{n} of {total * repeats}" for n in calls) + " |")
    lines.append("| Calls that errored or answered badly twice | " + " | ".join(str(n) for n in errors) + " |")

    text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")
    return text


def draw_overlays(out_dir, rows, slots):
    colours = {slot: MODEL_COLOURS[i % len(MODEL_COLOURS)] for i, slot in enumerate(slots)}
    for screen_id in dict.fromkeys(r["screen_id"] for r in rows):
        image = Image.open(SCREENS_DIR / f"{screen_id}.png").convert("RGB")
        draw = ImageDraw.Draw(image)
        screen_rows = [r for r in rows if r["screen_id"] == screen_id]
        for row in screen_rows:  # true boxes, green, with the element id
            draw.rectangle(row["box"], outline="#00c000", width=2)
            draw.text((row["box"][0], row["box"][3] + 2), row["element_id"], fill="#00c000")
        for row in screen_rows:  # answers: filled dot = hit, ring = miss
            if row["pixel_x"] is None:
                continue
            x, y, r = row["pixel_x"], row["pixel_y"], 6
            if row["hit"]:
                draw.ellipse([x - r, y - r, x + r, y + r], fill=colours[row["slot"]])
            else:
                draw.ellipse([x - r, y - r, x + r, y + r], outline=colours[row["slot"]], width=3)
        legend_y = 10
        for slot, colour in colours.items():
            draw.rectangle([10, legend_y, 24, legend_y + 14], fill=colour)
            draw.text((30, legend_y), f"{slot}: {slots[slot]['model']}", fill=colour)
            legend_y += 20
        image.save(out_dir / f"{screen_id}.png")


if __name__ == "__main__":
    main()
