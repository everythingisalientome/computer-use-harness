"""Shared helpers for the probe scripts: file locations and loading YAML."""

from pathlib import Path

import yaml

PROBE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PROBE_DIR.parent
SCREENS_DIR = PROBE_DIR / "screens"
RESULTS_DIR = PROBE_DIR / "results"
ELEMENTS_FILE = PROBE_DIR / "elements.yaml"
LABELS_FILE = PROBE_DIR / "labels.yaml"
MODEL_CONNECTION_FILE = ROOT_DIR / "config" / "model-connection.yaml"


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_screens():
    """Return the list of screens from elements.yaml."""
    return load_yaml(ELEMENTS_FILE)["screens"]


def find_screen(screen_id):
    for screen in load_screens():
        if screen["id"] == screen_id:
            return screen
    known = ", ".join(s["id"] for s in load_screens())
    raise SystemExit(f"Unknown screen '{screen_id}'. Known screens: {known}")


def load_labels():
    """Return {screen_id: {element_id: [left, top, right, bottom]}} in screenshot pixels."""
    if not LABELS_FILE.exists():
        return {}
    return load_yaml(LABELS_FILE)


def save_labels(labels):
    with open(LABELS_FILE, "w", encoding="utf-8") as f:
        f.write("# Written by label.py. Boxes are [left, top, right, bottom] in screenshot pixels.\n")
        yaml.safe_dump(labels, f, sort_keys=False, default_flow_style=None)
