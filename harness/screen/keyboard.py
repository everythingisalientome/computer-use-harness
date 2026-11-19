"""Keyboard actions: type text, and press keys such as "ctrl+s".

type_text sends each character as a character, not as a key on a keyboard
layout, so it arrives exactly as written (letters, digits, punctuation, é, ₹)
whatever layout the machine uses. A newline is sent as Enter and a tab as Tab.
Some legacy and remote-desktop apps ignore characters sent this way; see
docs/decision-record.md, section 8.

press_keys takes key names in the action format: lower case, joined with "+".
The modifiers go down in order, the last key goes down and up, then the
modifiers come up in reverse order.

Checking a key against the persona's blocked list is the guardrails' job
(piece 8), not this module's. The one combination refused here is the stop
hotkey itself, so the harness can never stop itself by accident.
"""

import time

from . import stop, win32

CHAR_PAUSE_SECONDS = 0.02        # between typed characters; web suggestion boxes can drop faster input
AFTER_KEYS_PAUSE_SECONDS = 0.1   # after a key combination or a typed text, before the next action

MODIFIERS = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B}

KEYS = {
    "enter": 0x0D, "tab": 0x09, "escape": 0x1B, "backspace": 0x08, "space": 0x20,
    "delete": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
}
KEYS.update({chr(code).lower(): code for code in range(ord("A"), ord("Z") + 1)})  # a to z
KEYS.update({str(digit): ord(str(digit)) for digit in range(10)})                # 0 to 9
KEYS.update({f"f{number}": 0x6F + number for number in range(1, 13)})            # f1 to f12

# Keys Windows calls "extended". They must be sent with a flag, or for example
# "delete" can arrive as the "." key on the number pad.
EXTENDED = {"delete", "insert", "home", "end", "pageup", "pagedown", "left", "up", "right", "down", "win"}


def parse_keys(text):
    """Turn "ctrl+s" into ["ctrl", "s"], refusing unknown names and the stop hotkey."""
    names = [name.strip() for name in text.split("+")]
    if not text or any(name == "" for name in names):
        raise ValueError(f"'{text}' is not a key combination. Use names joined with '+', such as ctrl+s.")
    for name in names:
        if name not in MODIFIERS and name not in KEYS:
            raise ValueError(f"Unknown key '{name}' in '{text}'. Known keys: {', '.join([*MODIFIERS, *KEYS])}.")
    if len(set(names)) != len(names):
        raise ValueError(f"'{text}' names the same key twice.")
    if set(names) == stop.HOTKEY_KEYS:
        raise ValueError(f"'{text}' is the stop hotkey; the harness never sends it.")
    return names


def press_keys(text, pause_after=AFTER_KEYS_PAUSE_SECONDS):
    names = parse_keys(text)
    pressed = []
    try:
        for name in names:
            _send_key(name, key_up=False)
            pressed.append(name)
    finally:
        # Release whatever went down, even after an error, so no key is left held.
        for name in reversed(pressed):
            _send_key(name, key_up=True)
    time.sleep(pause_after)


def type_text(text, char_pause=CHAR_PAUSE_SECONDS, pause_after=AFTER_KEYS_PAUSE_SECONDS):
    for char in text:
        if char == "\r":
            continue  # "\r\n" is one line break; Enter is sent for the "\n"
        if char == "\n":
            _tap("enter")
        elif char == "\t":
            _tap("tab")
        else:
            _send_char(char)
        time.sleep(char_pause)
    time.sleep(pause_after)


def _tap(name):
    _send_key(name, key_up=False)
    _send_key(name, key_up=True)


def _send_key(name, key_up):
    virtual_key = MODIFIERS.get(name) or KEYS[name]
    stop.check()
    win32.send_input(win32.key_event(virtual_key, key_up=key_up, extended=name in EXTENDED))


def _send_char(char):
    # Windows takes characters as UTF-16 units. Most characters are one unit;
    # a few, such as emoji, are two, sent one after the other.
    data = char.encode("utf-16-le")
    for i in range(0, len(data), 2):
        unit = int.from_bytes(data[i:i + 2], "little")
        stop.check()
        win32.send_input(win32.unicode_event(unit, key_up=False))
        win32.send_input(win32.unicode_event(unit, key_up=True))
