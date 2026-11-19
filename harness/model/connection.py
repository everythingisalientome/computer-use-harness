"""Read config/model-connection.yaml: where the models are and which model each slot uses.

Every connection detail comes from that file. The key comes from the
environment variable the file names; it is read here, handed to the OpenAI
library, and never printed, logged or put in an error message.

The full schema check of the file is piece 4. Until then, load() only checks
that the fields this package needs are present.
"""

import os
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[2]
CONNECTION_FILE = ROOT_DIR / "config" / "model-connection.yaml"

REQUIRED_FIELDS = ["base_url", "api_key_env", "timeout_seconds", "coordinate_grid", "models"]


class ModelConfigError(Exception):
    """The connection file is incomplete, the key is not set, or the provider refused the settings."""


def load(path=CONNECTION_FILE):
    """Return the connection settings as a dict."""
    with open(path, encoding="utf-8") as f:
        connection = yaml.safe_load(f) or {}
    missing = [field for field in REQUIRED_FIELDS if field not in connection]
    if missing:
        raise ModelConfigError(f"{path} is missing: {', '.join(missing)}.")
    for name, slot in connection["models"].items():
        if not isinstance(slot, dict) or "model" not in slot:
            raise ModelConfigError(f"{path}: model slot '{name}' needs a 'model' name.")
    return connection


def api_key(connection):
    """Return the key from the environment variable the connection file names."""
    variable = connection["api_key_env"]
    key = os.environ.get(variable)
    if not key:
        raise ModelConfigError(f"Set the environment variable {variable} first.")
    return key


def slot(connection, name):
    """Return {"model": ..., "temperature": ...} for a slot name such as "default"."""
    slots = connection["models"]
    if name not in slots:
        raise ModelConfigError(f"No model slot '{name}' in model-connection.yaml. Slots: {', '.join(slots)}.")
    return {"model": slots[name]["model"], "temperature": slots[name].get("temperature", 0)}
