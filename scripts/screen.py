"""Screen input and output from the command line (build piece 1).

Usage, from the project folder:

  .venv\\Scripts\\python scripts\\screen.py check          automatic check in a harmless test window
  .venv\\Scripts\\python scripts\\screen.py shot           save a screenshot to output\\screen\\
  .venv\\Scripts\\python scripts\\screen.py click X Y [--button left|right|middle] [--double]
  .venv\\Scripts\\python scripts\\screen.py scroll X Y DIRECTION AMOUNT
  .venv\\Scripts\\python scripts\\screen.py drag FROM_X FROM_Y TO_X TO_Y
  .venv\\Scripts\\python scripts\\screen.py type TEXT
  .venv\\Scripts\\python scripts\\screen.py key KEYS       for example ctrl+s
  .venv\\Scripts\\python scripts\\screen.py window         report the window in front

X and Y are on the 0 to 1000 grid. Every command except check counts down
first (--countdown, default 3 seconds) so you can bring the right window to
the front, then reports the window in front afterwards.

Press Ctrl+Alt+Q at any time to stop.

Pauses: --char-pause SECONDS between typed characters (default 0.02) and
--click-pause SECONDS after a click, scroll or drag (default 0.1).
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from harness.screen import display, keyboard, mouse, stop, window  # noqa: E402

SHOT_DIR = ROOT_DIR / "output" / "screen"


def main():
    # Window titles and the typed test text can hold characters such as ₹ that
    # an older console code page cannot print.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    if args.command == "check":
        import screen_check  # only needed here; it imports tkinter
        sys.exit(screen_check.run_check(args.char_pause, args.click_pause))

    width, height = display.screen_size()
    print(f"Primary monitor: {width} x {height} pixels, display scaling {display.scale_percent()}%")
    stop.start()
    print(f"Press {stop.HOTKEY_NAME} at any time to stop.")
    for remaining in range(args.countdown, 0, -1):
        print(f"  {args.command} in {remaining}...")
        time.sleep(1)

    if args.command == "shot":
        image = display.take_screenshot()
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = SHOT_DIR / f"{datetime.now():%Y-%m-%d_%H%M%S}.png"
        image.save(path)
        print(f"Saved {path} ({image.width} x {image.height})")
    elif args.command == "click":
        x, y = to_pixel(args.x, args.y)
        if args.double:
            mouse.double_click(x, y, pause_after=args.click_pause)
        else:
            mouse.click(x, y, button=args.button, pause_after=args.click_pause)
    elif args.command == "scroll":
        x, y = to_pixel(args.x, args.y)
        mouse.scroll(x, y, args.direction, args.amount, pause_after=args.click_pause)
    elif args.command == "drag":
        from_x, from_y = to_pixel(args.from_x, args.from_y)
        to_x, to_y = to_pixel(args.to_x, args.to_y)
        mouse.drag(from_x, from_y, to_x, to_y, pause_after=args.click_pause)
    elif args.command == "type":
        keyboard.type_text(args.text, char_pause=args.char_pause)
        print(f"Typed {len(args.text)} character(s).")
    elif args.command == "key":
        keyboard.press_keys(args.keys)
        print(f"Pressed {args.keys}.")

    info = window.foreground_window()
    print("Window in front:")
    print(f"  title:   {info.title!r}")
    print(f"  process: {info.process_name or 'unknown'} (id {info.process_id})")
    print(f"  path:    {info.process_path or 'unknown'}")


def to_pixel(gx, gy):
    x, y = display.grid_to_screen(gx, gy)
    print(f"Grid ({gx}, {gy}) is pixel ({x}, {y}).")
    return x, y


def parse_args():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--countdown", type=int, default=3, help="seconds to wait before acting")
    common.add_argument("--char-pause", type=float, default=keyboard.CHAR_PAUSE_SECONDS)
    common.add_argument("--click-pause", type=float, default=mouse.AFTER_CLICK_PAUSE_SECONDS)

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", parents=[common], help="automatic check in a harmless test window")
    commands.add_parser("shot", parents=[common], help="save a screenshot")
    commands.add_parser("window", parents=[common], help="report the window in front")

    click = commands.add_parser("click", parents=[common], help="click a grid position")
    click.add_argument("x", type=int)
    click.add_argument("y", type=int)
    click.add_argument("--button", default="left", choices=["left", "right", "middle"])
    click.add_argument("--double", action="store_true", help="double-click instead")

    scroll = commands.add_parser("scroll", parents=[common], help="turn the mouse wheel at a grid position")
    scroll.add_argument("x", type=int)
    scroll.add_argument("y", type=int)
    scroll.add_argument("direction", choices=["up", "down", "left", "right"])
    scroll.add_argument("amount", type=int)

    drag = commands.add_parser("drag", parents=[common], help="drag from one grid position to another")
    for name in ("from_x", "from_y", "to_x", "to_y"):
        drag.add_argument(name, type=int)

    type_ = commands.add_parser("type", parents=[common], help="type text")
    type_.add_argument("text")

    key = commands.add_parser("key", parents=[common], help="press keys, for example ctrl+s")
    key.add_argument("keys")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        main()
    except display.ScreenNotAvailable as error:
        print(f"Cannot see the screen: {error}")
        sys.exit(1)
