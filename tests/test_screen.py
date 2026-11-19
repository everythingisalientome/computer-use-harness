"""Tests for the parts of harness/screen that do not touch the screen:
key-name parsing, the blank-screenshot test, and refusing input without a stop.
"""

import pytest
from PIL import Image

from harness.screen import display, keyboard, mouse, stop


@pytest.mark.parametrize("text, names", [
    ("enter", ["enter"]),
    ("ctrl+s", ["ctrl", "s"]),
    ("ctrl+shift+end", ["ctrl", "shift", "end"]),
    ("f5", ["f5"]),
    ("alt+f4", ["alt", "f4"]),  # refusing it is the guardrails' job, not the keyboard's
])
def test_known_keys_parse(text, names):
    assert keyboard.parse_keys(text) == names


@pytest.mark.parametrize("text", ["", "ctrl+", "+s", "ctrl+banana", "Enter", "ctrl+ctrl"])
def test_bad_keys_are_refused(text):
    with pytest.raises(ValueError):
        keyboard.parse_keys(text)


@pytest.mark.parametrize("text", ["ctrl+alt+q", "alt+ctrl+q"])
def test_stop_hotkey_is_never_sent(text):
    with pytest.raises(ValueError, match="stop hotkey"):
        keyboard.parse_keys(text)


def test_blank_screenshot_is_detected():
    assert display.is_blank(Image.new("RGB", (100, 50), "black"))
    image = Image.new("RGB", (100, 50), "black")
    image.putpixel((10, 10), (255, 255, 255))
    assert not display.is_blank(image)


def test_no_input_without_a_working_stop():
    # The test run never starts the stop hotkey, so every input is refused before it is sent.
    with pytest.raises(stop.StopNotActive):
        mouse.click(10, 10)
    with pytest.raises(stop.StopNotActive):
        keyboard.type_text("x")


def test_bad_scroll_is_refused():
    with pytest.raises(ValueError):
        mouse.scroll(10, 10, "sideways", 1)
