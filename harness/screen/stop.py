"""The emergency stop: press Ctrl+Alt+Q in any window to stop the harness at once.

start() registers the hotkey with Windows and waits for it on a background
thread, so it works whichever window is in front. When it is pressed:

1. A flag is set. mouse.py and keyboard.py check it before every single input
   event, and text is typed one character per event, so at most one more
   event goes out.
2. Every mouse button and modifier key (Ctrl, Shift, Alt, Win) that is held
   down is released, so nothing is left stuck.
3. The process ends immediately (os._exit), without cleaning up. Being stopped
   mid-step is a case the resume rules in docs/state-machine.md already handle.

The mouse and keyboard refuse to act until start() has succeeded: a stop that
does not work is a reason not to act at all. If another program already owns
Ctrl+Alt+Q, start() fails with a clear message.
"""

import os
import sys
import threading
import time

from . import win32

HOTKEY_NAME = "ctrl+alt+q"
HOTKEY_KEYS = {"ctrl", "alt", "q"}  # keyboard.py refuses to send this combination
EXIT_CODE = 3  # the process exit code after a stop, so a caller can tell it apart

_HOTKEY_ID = 1
_VK_Q = 0x51

# Released on stop if held: mouse buttons, then left and right Ctrl, Shift, Alt and Win.
_BUTTONS_TO_RELEASE = {
    0x01: win32.MOUSEEVENTF_LEFTUP,
    0x02: win32.MOUSEEVENTF_RIGHTUP,
    0x04: win32.MOUSEEVENTF_MIDDLEUP,
}
_KEYS_TO_RELEASE = [0xA2, 0xA3, 0xA0, 0xA1, 0xA4, 0xA5, 0x5B, 0x5C]
_EXTENDED_KEYS = {0xA3, 0xA5, 0x5B, 0x5C}  # right Ctrl, right Alt, both Win keys

_requested = threading.Event()
_active = threading.Event()


class StopRequested(Exception):
    """The stop hotkey was pressed; no more input may be sent."""


class StopNotActive(Exception):
    """The stop hotkey is not working, so the harness must not act."""


def start():
    """Register the stop hotkey. Call once, before any mouse or keyboard action."""
    if _active.is_set():
        return
    problem = []
    ready = threading.Event()
    thread = threading.Thread(target=_listen, args=(problem, ready), name="stop-hotkey", daemon=True)
    thread.start()
    ready.wait(timeout=5)
    if not _active.is_set():
        reason = problem[0] if problem else "no answer from the hotkey thread"
        raise StopNotActive(
            f"Could not register the stop hotkey {HOTKEY_NAME} ({reason}). Another program may "
            f"already use it. The harness will not act without a working stop."
        )


def check():
    """Called before every input event. Raises if input must not be sent."""
    if _requested.is_set():
        raise StopRequested(f"Stopped by {HOTKEY_NAME}.")
    if not _active.is_set():
        raise StopNotActive("The stop hotkey is not running. Call stop.start() before any input.")


def _listen(problem, ready):
    # Windows delivers a hotkey to the thread that registered it, so this
    # thread both registers it and waits for it.
    if not win32.register_hotkey(_HOTKEY_ID, win32.MOD_CONTROL | win32.MOD_ALT, _VK_Q):
        problem.append(win32.last_error())
        ready.set()
        return
    _active.set()
    ready.set()
    win32.wait_for_hotkey(_HOTKEY_ID)
    _stop_now()


def _stop_now():
    _requested.set()
    time.sleep(0.05)  # let an event that was already being sent finish
    _release_everything_held()
    print(f"\nStopped by {HOTKEY_NAME}.", file=sys.stderr, flush=True)
    os._exit(EXIT_CODE)


def _release_everything_held():
    # These go straight to win32.send_input, not through check(), because the
    # stop flag is already set.
    for button, up_flag in _BUTTONS_TO_RELEASE.items():
        if win32.is_key_down(button):
            win32.send_input(win32.mouse_event(up_flag))
    for key in _KEYS_TO_RELEASE:
        if win32.is_key_down(key):
            win32.send_input(win32.key_event(key, key_up=True, extended=key in _EXTENDED_KEYS))
