"""Facts about windows: which window is in front, its title and its process.

These are operating-system facts, used for checks: the allowed-app check
(piece 8) and the audit log (piece 9). They are never used to decide where
to click.
"""

import os
from dataclasses import dataclass

from . import win32


@dataclass
class WindowInfo:
    handle: int | None        # Windows' number for the window
    title: str
    process_id: int | None
    process_name: str | None  # for example "notepad.exe"; None when Windows will not say
    process_path: str | None


def foreground_window():
    """The window in front of all others, the one that receives typing."""
    return describe(win32.foreground_window_handle())


def window_at(x, y):
    """The top-level window that owns the pixel (x, y)."""
    return describe(win32.top_level_window_at(x, y))


def describe(handle):
    if not handle:
        return WindowInfo(handle=None, title="", process_id=None, process_name=None, process_path=None)
    process_id = win32.window_process_id(handle)
    path = win32.process_path(process_id) if process_id else None
    return WindowInfo(
        handle=handle,
        title=win32.window_title(handle),
        process_id=process_id,
        process_name=os.path.basename(path).lower() if path else None,
        process_path=path,
    )
