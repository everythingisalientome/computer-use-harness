"""The screen itself: its size, its display scaling, and screenshots.

Only the primary monitor is used. Its top-left corner is always pixel (0, 0),
so its pixels are also the positions the mouse uses.

Importing win32 makes this process DPI aware, so the screen size and the
screenshot are both in real pixels at any display scaling. take_screenshot
checks that they agree every time, because if they did not, clicks would land
in the wrong place.

take_screenshot also refuses when the desktop cannot be seen: the harness
needs an unlocked, active desktop session (docs/decision-record.md, section 8).
"""

from PIL import ImageGrab

from . import win32
from .grid import grid_to_pixel

NEEDS_SESSION = "The harness needs an unlocked, active desktop session."


class ScreenNotAvailable(Exception):
    """The desktop cannot be seen: the session is locked or disconnected, or the screenshot is blank."""


def screen_size():
    """(width, height) of the primary monitor in real pixels."""
    return win32.primary_screen_size()


def scale_percent():
    """The primary monitor's display scaling, for example 100, 125 or 150."""
    return win32.primary_monitor_scale_percent()


def grid_to_screen(gx, gy, grid=1000):
    """The screen pixel for a grid position on a screenshot of the whole primary monitor."""
    width, height = screen_size()
    return grid_to_pixel(gx, gy, width, height, grid)


def take_screenshot():
    """A screenshot of the primary monitor, as a Pillow image in real pixels."""
    check_session()
    try:
        # Without all_screens, Pillow grabs only the primary monitor.
        image = ImageGrab.grab().convert("RGB")
    except OSError as error:
        raise ScreenNotAvailable(
            f"Windows refused the screenshot ({error}). This happens when the session is "
            f"disconnected, for example a closed Remote Desktop connection. {NEEDS_SESSION}"
        ) from error
    if image.size != screen_size():
        raise RuntimeError(
            f"The screenshot is {image.width} x {image.height} pixels but the screen is "
            f"{screen_size()[0]} x {screen_size()[1]}. Display scaling is not being handled, "
            "so clicks would land in the wrong place."
        )
    if is_blank(image):
        raise ScreenNotAvailable(
            "The screenshot is one flat colour. The session may be locked, disconnected or "
            f"minimised (for example a minimised Remote Desktop window). {NEEDS_SESSION}"
        )
    return image


def check_session():
    """Raise ScreenNotAvailable unless the session is active, unlocked, and its desktop is ours."""
    active, unlocked = win32.session_state()
    if active is None:
        raise ScreenNotAvailable(f"Windows would not say whether this session is locked. {NEEDS_SESSION}")
    if not active:
        raise ScreenNotAvailable(
            "This Windows session is not active, for example a disconnected Remote Desktop "
            f"session. {NEEDS_SESSION}"
        )
    if not unlocked:
        raise ScreenNotAvailable(f"This Windows session is locked. {NEEDS_SESSION}")
    if not win32.desktop_is_unlocked():
        raise ScreenNotAvailable(
            "A secure screen such as the sign-in screen or an administrator prompt is showing. "
            f"{NEEDS_SESSION}"
        )


def is_blank(image):
    """True if every pixel in the image is the same colour."""
    return all(low == high for low, high in image.convert("RGB").getextrema())
