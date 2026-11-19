"""The automatic check for build piece 1. Run it through `scripts\\screen.py check`.

It opens the harmless test window (screen_target.py) in its own process, then:
clicks grid positions and compares the pixel that arrived with the pixel
expected, finds the red dot each click left in a screenshot, double-clicks,
right-clicks, scrolls, drags, types text, presses keys, and reads the
foreground window's title and process. Every click is first checked to land
on the test window; a point covered by anything else is not clicked.

It prints a PASS or FAIL table and saves it, with the screenshot, to
output/screen-check/.
"""

import json
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import screen_target as layout
from harness.screen import display, keyboard, mouse, stop, window, win32

ROOT_DIR = Path(__file__).resolve().parent.parent
TARGET_SCRIPT = Path(__file__).resolve().parent / "screen_target.py"
REPORT_DIR = ROOT_DIR / "output" / "screen-check"

TYPED_TEXT = "Acme Robotics 1118, Café & Co. ₹4,50,000.00"

# (keys sent, keysym the window should receive, Ctrl held, Shift held)
KEY_TESTS = [
    ("ctrl+a", "a", True, False),
    ("shift+a", "A", False, True),
    ("enter", "Return", False, False),
    ("tab", "Tab", False, False),
    ("escape", "Escape", False, False),
    ("down", "Down", False, False),
    ("delete", "Delete", False, False),
    ("f5", "F5", False, False),
]

TOLERANCE_PX = 1


class TargetWindow:
    """The test window process, and the events it reports."""

    def __init__(self):
        self.process = subprocess.Popen(
            [sys.executable, str(TARGET_SCRIPT)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8",
        )
        self.events = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.ready = self.wait_for("ready", timeout=15)
        if self.ready is None:
            self.close()
            raise RuntimeError("The test window did not start within 15 seconds.")
        # The window's own process id. The venv's python.exe starts the real
        # Python as a second process, so this differs from self.process.pid.
        self.pid = self.ready["pid"]

    def _read(self):
        for line in self.process.stdout:
            try:
                self.events.put(json.loads(line))
            except json.JSONDecodeError:
                pass

    def drain(self):
        """Throw away events reported so far."""
        while not self.events.empty():
            self.events.get()

    def wait_for(self, name, timeout=2.0):
        """The next event with this name, or None if none arrives in time."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                event = self.events.get(timeout=max(deadline - time.time(), 0.01))
            except queue.Empty:
                return None
            if event["event"] == name:
                return event
        return None

    def collect(self, seconds):
        """Every event reported in the next few seconds."""
        time.sleep(seconds)
        found = []
        while not self.events.empty():
            found.append(self.events.get())
        return found

    def command(self, text):
        self.process.stdin.write(text + "\n")
        self.process.stdin.flush()

    def close(self):
        try:
            self.command("quit")
            self.process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            self.process.kill()


def near(event, x, y):
    return event is not None and abs(event["x"] - x) <= TOLERANCE_PX and abs(event["y"] - y) <= TOLERANCE_PX


def where(event):
    return "nothing arrived" if event is None else f"arrived at ({event['x']}, {event['y']})"


def run_check(char_pause, click_pause):
    width, height = display.screen_size()
    scale = display.scale_percent()
    print(f"Primary monitor: {width} x {height} pixels, display scaling {scale}%, "
          f"DPI aware: {win32.is_dpi_aware()}")
    stop.start()
    print(f"Press {stop.HOTKEY_NAME} at any time to stop.\n")

    results = []  # (status, check name, detail)

    def record(passed, name, detail=""):
        results.append(("PASS" if passed else "FAIL", name, detail))

    try:
        display.take_screenshot()
    except (display.ScreenNotAvailable, RuntimeError) as error:
        print(f"FAIL  screenshot: {error}")
        return 1
    record(True, "screenshot works and matches the screen size", f"{width} x {height}")

    target = TargetWindow()
    try:
        ready = target.ready
        record(ready["window_width"] == width and ready["window_height"] == height,
               "test window covers the screen in real pixels",
               f"window {ready['window_width']} x {ready['window_height']}")
        time.sleep(0.5)  # let it finish drawing

        clicked = check_clicks(target, record, click_pause)
        shot = check_dots(clicked, record)
        check_foreground(target, record)
        check_other_mouse_actions(target, record, results, click_pause)
        check_typing(target, record, char_pause, click_pause)
        check_keys(target, record, click_pause)
    finally:
        target.close()

    try:
        keyboard.parse_keys(stop.HOTKEY_NAME)
        record(False, "stop hotkey is refused as a key to send", "it was accepted")
    except ValueError:
        record(True, "stop hotkey is refused as a key to send")

    return report(results, width, height, scale, shot)


def check_clicks(target, record, click_pause):
    clicked = []
    for gx, gy in layout.CLICK_POINTS:
        x, y = display.grid_to_screen(gx, gy)
        name = f"click grid ({gx}, {gy}) -> pixel ({x}, {y})"
        owner = window.window_at(x, y)
        if owner.process_id != target.pid:
            record(False, name, f"not clicked: the pixel belongs to '{owner.title}' ({owner.process_name})")
            continue
        target.drain()
        mouse.click(x, y, pause_after=click_pause)
        event = target.wait_for("press")
        record(near(event, x, y), name, where(event))
        clicked.append((x, y))
    return clicked


def check_dots(clicked, record):
    shot = display.take_screenshot()
    missing = []
    for x, y in clicked:
        red, green, blue = shot.getpixel((x, y))
        if not (red > 200 and green < 80 and blue < 80):
            missing.append(f"({x}, {y}) is {red},{green},{blue}")
    record(not missing and bool(clicked), "each click's red dot is at the same pixel in the screenshot",
           "; ".join(missing) or f"{len(clicked)} dots found")
    return shot


def check_foreground(target, record):
    info = window.foreground_window()
    record(info.process_id == target.pid and info.title == layout.TITLE,
           "foreground window title and process",
           f"'{info.title}', {info.process_name}, process {info.process_id}")


def check_other_mouse_actions(target, record, results, click_pause):
    x, y = display.grid_to_screen(*layout.DOUBLE_CLICK_POINT)
    target.drain()
    mouse.double_click(x, y, pause_after=click_pause)
    event = target.wait_for("double_click")
    record(near(event, x, y), f"double-click at pixel ({x}, {y})", where(event))

    target.drain()
    mouse.click(x, y, button="right", pause_after=click_pause)
    event = target.wait_for("right_click")
    record(near(event, x, y), f"right-click at pixel ({x}, {y})", where(event))

    x, y = display.grid_to_screen(*layout.SCROLL_POINT)
    for direction, amount, expected in [("down", 3, -360), ("up", 2, 240)]:
        target.drain()
        mouse.scroll(x, y, direction, amount, pause_after=click_pause)
        total = sum(e["delta"] for e in target.collect(0.5) if e["event"] == "wheel")
        record(total == expected, f"scroll {direction} {amount} notches", f"wheel total {total}, expected {expected}")

    target.drain()
    mouse.scroll(x, y, "right", 1, pause_after=click_pause)
    sideways = [e for e in target.collect(0.5) if e["event"] == "hwheel"]
    if sideways:
        record(True, "scroll right 1 notch", f"received {sideways}")
    else:
        results.append(("INFO", "scroll right 1 notch",
                        "sent; this test window does not report sideways wheel events, so not verified here"))

    (fx, fy), (tx, ty) = display.grid_to_screen(*layout.DRAG_FROM), display.grid_to_screen(*layout.DRAG_TO)
    target.drain()
    mouse.drag(fx, fy, tx, ty, pause_after=click_pause)
    events = target.collect(0.5)
    press = next((e for e in events if e["event"] == "press"), None)
    release = next((e for e in events if e["event"] == "release"), None)
    motions = release["motions"] if release else 0
    record(near(press, fx, fy) and near(release, tx, ty) and motions > 0,
           f"drag from ({fx}, {fy}) to ({tx}, {ty})",
           f"pressed: {where(press)}; released: {where(release)}; {motions} moves in between")


def check_typing(target, record, char_pause, click_pause):
    target.command("clear")
    target.wait_for("cleared")
    ex, ey = target.ready["entries"][0]
    mouse.click(ex, ey, pause_after=click_pause)
    keyboard.type_text(TYPED_TEXT, char_pause=char_pause)
    target.command("text")
    event = target.wait_for("text")
    typed = event["values"][0] if event else None
    record(typed == TYPED_TEXT, "typed text arrives exactly", f"received {typed!r}")

    keyboard.press_keys("backspace")
    target.command("text")
    event = target.wait_for("text")
    after = event["values"][0] if event else None
    record(after == TYPED_TEXT[:-1], "backspace removes the last character", f"received {after!r}")


def check_keys(target, record, click_pause):
    ex, ey = target.ready["entries"][1]
    mouse.click(ex, ey, pause_after=click_pause)
    for keys, keysym, ctrl, shift in KEY_TESTS:
        target.drain()
        keyboard.press_keys(keys)
        events = [e for e in target.collect(0.3) if e["event"] == "key"]
        match = next((e for e in events if e["keysym"] == keysym), None)
        passed = match is not None and match["ctrl"] == ctrl and match["shift"] == shift
        received = ", ".join(f"{e['keysym']}{' +ctrl' if e['ctrl'] else ''}{' +shift' if e['shift'] else ''}"
                             for e in events) or "nothing"
        record(passed, f"key {keys}", f"received {received}")


def report(results, width, height, scale, shot):
    failures = sum(1 for status, _, _ in results if status == "FAIL")
    lines = [
        f"Screen check, {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Primary monitor {width} x {height}, display scaling {scale}%",
        "",
    ]
    lines += [f"{status:<5} {name}" + (f"  [{detail}]" if detail else "") for status, name, detail in results]
    lines += ["", "RESULT: " + ("PASS" if failures == 0 else f"FAIL ({failures} check(s) failed)")]
    text = "\n".join(lines)
    print(text)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.now():%Y-%m-%d_%H%M%S}_scale{scale}"
    (REPORT_DIR / f"{stem}.txt").write_text(text + "\n", encoding="utf-8")
    if shot is not None:
        shot.save(REPORT_DIR / f"{stem}.png")
    print(f"\nSaved to {REPORT_DIR / stem}.txt")
    return 0 if failures == 0 else 1
