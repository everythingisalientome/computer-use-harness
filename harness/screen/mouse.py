"""Mouse actions: click, double-click, scroll and drag.

Positions are pixels on the primary monitor. The caller converts the model's
grid position first, with display.grid_to_screen, so the pixel can be checked
and logged before anything is clicked.

The cursor is moved by setting its exact position, then the button events are
sent. stop.check() runs before every event, so the emergency stop takes effect
between any two of them.

The pauses are plain constants. Each function also takes pause_after, so a
caller can override the pause for one action.
"""

import time

from . import stop, win32

MOVE_PAUSE_SECONDS = 0.05         # after moving the cursor, before pressing: lets hover effects appear
AFTER_CLICK_PAUSE_SECONDS = 0.1   # after a click, scroll or drag, before the next action
SCROLL_NOTCH_PAUSE_SECONDS = 0.05 # between wheel notches, so the app keeps up
DRAG_STEPS = 10                   # intermediate positions during a drag; some apps need movement to start one
WHEEL_NOTCH = 120                 # Windows' unit for one notch of the mouse wheel

_BUTTONS = {
    "left": (win32.MOUSEEVENTF_LEFTDOWN, win32.MOUSEEVENTF_LEFTUP),
    "right": (win32.MOUSEEVENTF_RIGHTDOWN, win32.MOUSEEVENTF_RIGHTUP),
    "middle": (win32.MOUSEEVENTF_MIDDLEDOWN, win32.MOUSEEVENTF_MIDDLEUP),
}

# direction: (wheel flag, sign). Wheel up and wheel right are positive in Windows.
_SCROLL = {
    "up": (win32.MOUSEEVENTF_WHEEL, 1),
    "down": (win32.MOUSEEVENTF_WHEEL, -1),
    "right": (win32.MOUSEEVENTF_HWHEEL, 1),
    "left": (win32.MOUSEEVENTF_HWHEEL, -1),
}


def move(x, y):
    stop.check()
    win32.set_cursor_pos(x, y)


def click(x, y, button="left", pause_after=AFTER_CLICK_PAUSE_SECONDS):
    down, up = _button_flags(button)
    move(x, y)
    time.sleep(MOVE_PAUSE_SECONDS)
    _send(down)
    _send(up)
    time.sleep(pause_after)


def double_click(x, y, pause_after=AFTER_CLICK_PAUSE_SECONDS):
    down, up = _button_flags("left")
    move(x, y)
    time.sleep(MOVE_PAUSE_SECONDS)
    # No pause between the two clicks, so Windows counts them as a double-click.
    for _ in range(2):
        _send(down)
        _send(up)
    time.sleep(pause_after)


def scroll(x, y, direction, amount, pause_after=AFTER_CLICK_PAUSE_SECONDS):
    """Turn the wheel `amount` notches with the cursor at (x, y). direction: up, down, left or right."""
    if direction not in _SCROLL:
        raise ValueError(f"Scroll direction must be one of {', '.join(_SCROLL)}, not '{direction}'.")
    if not isinstance(amount, int) or amount < 1:
        raise ValueError(f"Scroll amount must be a whole number of 1 or more, not {amount!r}.")
    flag, sign = _SCROLL[direction]
    move(x, y)
    time.sleep(MOVE_PAUSE_SECONDS)
    for _ in range(amount):
        _send(flag, sign * WHEEL_NOTCH)
        time.sleep(SCROLL_NOTCH_PAUSE_SECONDS)
    time.sleep(pause_after)


def drag(from_x, from_y, to_x, to_y, pause_after=AFTER_CLICK_PAUSE_SECONDS):
    """Press the left button at the first point, move to the second, release."""
    move(from_x, from_y)
    time.sleep(MOVE_PAUSE_SECONDS)
    _send(win32.MOUSEEVENTF_LEFTDOWN)
    try:
        time.sleep(0.1)
        for step in range(1, DRAG_STEPS + 1):
            move(round(from_x + (to_x - from_x) * step / DRAG_STEPS),
                 round(from_y + (to_y - from_y) * step / DRAG_STEPS))
            time.sleep(0.02)
        time.sleep(0.1)
    finally:
        # Release the button even if a move failed, so it is not left held down.
        _send(win32.MOUSEEVENTF_LEFTUP)
    time.sleep(pause_after)


def _button_flags(button):
    if button not in _BUTTONS:
        raise ValueError(f"Mouse button must be one of {', '.join(_BUTTONS)}, not '{button}'.")
    return _BUTTONS[button]


def _send(flags, data=0):
    stop.check()
    win32.send_input(win32.mouse_event(flags, data))
