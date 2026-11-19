"""Take one probe screenshot of the primary monitor.

Usage:  .venv\\Scripts\\python probe\\capture.py <screen_id>

It prints how to get to the screen, counts down so you can bring the right
window to the front, then saves probe/screens/<screen_id>.png.
"""

import sys
import time

from PIL import ImageGrab

from common import SCREENS_DIR, find_screen, load_screens

COUNTDOWN_SECONDS = 5


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        print("Screens:", ", ".join(s["id"] for s in load_screens()))
        sys.exit(1)

    screen = find_screen(sys.argv[1])
    print(f"Screen: {screen['id']}")
    print(f"Get there: {screen['get_there']}")
    for remaining in range(COUNTDOWN_SECONDS, 0, -1):
        print(f"  capturing in {remaining}...")
        time.sleep(1)

    # Without all_screens, Pillow grabs only the primary monitor, in real pixels
    # even when Windows display scaling is above 100%.
    image = ImageGrab.grab()
    SCREENS_DIR.mkdir(exist_ok=True)
    path = SCREENS_DIR / f"{screen['id']}.png"
    image.save(path)
    print(f"Saved {path} ({image.width} x {image.height})")


if __name__ == "__main__":
    main()
