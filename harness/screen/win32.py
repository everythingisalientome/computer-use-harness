"""The Windows calls the screen package needs, made through ctypes.

ctypes lets Python call functions inside Windows' own DLLs (user32.dll,
kernel32.dll, shcore.dll) without installing anything. Everything
unusual-looking in the screen package lives in this file; the other modules
call the plain Python functions defined here.

Importing this module makes the process DPI aware (see make_dpi_aware), so
every screen size, cursor position and screenshot is in real pixels, whatever
the Windows display scaling is.

None of these calls needs administrator rights. One consequence of that:
Windows does not let a normal process send input to an elevated window (for
example Task Manager), so the harness cannot drive elevated apps.
"""

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shcore = ctypes.WinDLL("shcore", use_last_error=True)


def last_error():
    """The Windows error code from the most recent failed call, as a readable string."""
    code = ctypes.get_last_error()
    return f"Windows error {code}: {ctypes.FormatError(code).strip()}"


# --- Display scaling (DPI awareness) ---------------------------------------
#
# A process that is not DPI aware is shown a pretend, smaller screen when
# scaling is above 100%, and Windows silently rescales every position it gives
# or receives. "Per-monitor aware v2" switches that off: the process sees real
# pixels on every monitor. It is a setting on our own process only.

DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
DPI_AWARENESS_PER_MONITOR_AWARE = 2

user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
user32.GetThreadDpiAwarenessContext.argtypes = []
user32.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
user32.GetAwarenessFromDpiAwarenessContext.argtypes = [ctypes.c_void_p]
user32.GetAwarenessFromDpiAwarenessContext.restype = ctypes.c_int


def is_dpi_aware():
    context = user32.GetThreadDpiAwarenessContext()
    return user32.GetAwarenessFromDpiAwarenessContext(context) == DPI_AWARENESS_PER_MONITOR_AWARE


def make_dpi_aware():
    # This returns False when awareness was already set earlier in the process,
    # which is fine. What matters is the result, checked next.
    user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    if not is_dpi_aware():
        raise RuntimeError(
            "Could not make this process DPI aware. Clicks would land in the wrong place "
            "when display scaling is above 100%, so the harness will not run."
        )


make_dpi_aware()


# --- Screen size and scale --------------------------------------------------

SM_CXSCREEN = 0
SM_CYSCREEN = 1
MONITOR_DEFAULTTOPRIMARY = 1
MDT_EFFECTIVE_DPI = 0

user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
user32.MonitorFromPoint.restype = wintypes.HMONITOR
shcore.GetDpiForMonitor.argtypes = [wintypes.HMONITOR, ctypes.c_int,
                                    ctypes.POINTER(wintypes.UINT), ctypes.POINTER(wintypes.UINT)]
shcore.GetDpiForMonitor.restype = ctypes.c_long


def primary_screen_size():
    """(width, height) of the primary monitor in real pixels."""
    return user32.GetSystemMetrics(SM_CXSCREEN), user32.GetSystemMetrics(SM_CYSCREEN)


def primary_monitor_scale_percent():
    """The Windows display scaling of the primary monitor, for example 100, 125 or 150."""
    # The primary monitor always has its top-left corner at (0, 0).
    monitor = user32.MonitorFromPoint(wintypes.POINT(0, 0), MONITOR_DEFAULTTOPRIMARY)
    dpi_x, dpi_y = wintypes.UINT(), wintypes.UINT()
    if shcore.GetDpiForMonitor(monitor, MDT_EFFECTIVE_DPI, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) != 0:
        return None
    return round(dpi_x.value * 100 / 96)  # 96 DPI is 100%


# --- Locked or unavailable desktop ------------------------------------------
#
# Two separate questions:
# 1. Is our session active and unlocked? Asked through the Remote Desktop
#    Services API, which every Windows session has. This catches the Windows 11
#    lock screen, which is drawn on our own desktop, so question 2 misses it.
# 2. Is the desktop receiving input ours? When the sign-in screen or an
#    administrator prompt is showing, it is not: opening or switching to it fails.

wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)

WTS_CURRENT_SERVER_HANDLE = None
WTS_CURRENT_SESSION = 0xFFFFFFFF
WTS_SESSION_INFO_EX = 25   # the WTSSessionInfoEx query
WTS_ACTIVE = 0             # session state: a user is signed in and connected
WTS_SESSIONSTATE_UNLOCK = 1


class WTSINFOEX_LEVEL1_START(ctypes.Structure):
    # Only the first fields of Windows' WTSINFOEX_LEVEL1_W are read. The
    # 8-byte field gives the structure the same alignment as Windows' own.
    _fields_ = [("SessionId", wintypes.ULONG), ("SessionState", ctypes.c_int),
                ("SessionFlags", wintypes.LONG), ("_alignment", ctypes.c_longlong)]


class WTSINFOEX(ctypes.Structure):
    _fields_ = [("Level", wintypes.DWORD), ("Data", WTSINFOEX_LEVEL1_START)]


wtsapi32.WTSQuerySessionInformationW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_int,
                                                 ctypes.POINTER(ctypes.c_void_p),
                                                 ctypes.POINTER(wintypes.DWORD)]
wtsapi32.WTSQuerySessionInformationW.restype = wintypes.BOOL
wtsapi32.WTSFreeMemory.argtypes = [ctypes.c_void_p]
wtsapi32.WTSFreeMemory.restype = None


def session_state():
    """(active, unlocked) for this process's Windows session, or (None, None) if Windows will not say."""
    buffer = ctypes.c_void_p()
    size = wintypes.DWORD()
    if not wtsapi32.WTSQuerySessionInformationW(WTS_CURRENT_SERVER_HANDLE, WTS_CURRENT_SESSION,
                                                WTS_SESSION_INFO_EX, ctypes.byref(buffer), ctypes.byref(size)):
        return None, None
    try:
        info = ctypes.cast(buffer, ctypes.POINTER(WTSINFOEX)).contents.Data
        return info.SessionState == WTS_ACTIVE, info.SessionFlags == WTS_SESSIONSTATE_UNLOCK
    finally:
        wtsapi32.WTSFreeMemory(buffer)


DESKTOP_SWITCHDESKTOP = 0x0100

user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.OpenInputDesktop.restype = wintypes.HANDLE
user32.SwitchDesktop.argtypes = [wintypes.HANDLE]
user32.SwitchDesktop.restype = wintypes.BOOL
user32.CloseDesktop.argtypes = [wintypes.HANDLE]
user32.CloseDesktop.restype = wintypes.BOOL


def desktop_is_unlocked():
    desktop = user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
    if not desktop:
        return False
    try:
        # Switching to the desktop that is already showing changes nothing; it
        # only fails when that desktop is not ours to use.
        return bool(user32.SwitchDesktop(desktop))
    finally:
        user32.CloseDesktop(desktop)


# --- Mouse cursor -----------------------------------------------------------

user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL


def set_cursor_pos(x, y):
    if not user32.SetCursorPos(x, y):
        raise OSError(f"Could not move the mouse to ({x}, {y}). {last_error()}")


def get_cursor_pos():
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


# --- Sending input (SendInput) ----------------------------------------------
#
# SendInput puts mouse and keyboard events into Windows' input stream, exactly
# as if they came from a real mouse or keyboard. Each event is one INPUT
# structure; the three structures below are Windows' layouts for them.

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short


def mouse_event(flags, data=0):
    """One mouse event at the cursor's current position. data is the wheel amount, if any."""
    event = INPUT(type=INPUT_MOUSE)
    event.u.mi = MOUSEINPUT(0, 0, data & 0xFFFFFFFF, flags, 0, 0)  # & keeps negative wheel amounts valid
    return event


def key_event(virtual_key, key_up=False, extended=False):
    """One key going down or up, by its virtual-key code."""
    flags = (KEYEVENTF_KEYUP if key_up else 0) | (KEYEVENTF_EXTENDEDKEY if extended else 0)
    scan_code = user32.MapVirtualKeyW(virtual_key, 0)  # some older apps read the scan code
    event = INPUT(type=INPUT_KEYBOARD)
    event.u.ki = KEYBDINPUT(virtual_key, scan_code, flags, 0, 0)
    return event


def unicode_event(utf16_unit, key_up=False):
    """One character going down or up, sent as a character rather than as a key on a layout."""
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if key_up else 0)
    event = INPUT(type=INPUT_KEYBOARD)
    event.u.ki = KEYBDINPUT(0, utf16_unit, flags, 0, 0)
    return event


def send_input(event):
    """Send one event. Raises if Windows did not accept it."""
    sent = user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))
    if sent != 1:
        raise OSError(f"Windows did not accept the input event. {last_error()}")


def is_key_down(virtual_key):
    """True if the key or mouse button is held down right now."""
    return bool(user32.GetAsyncKeyState(virtual_key) & 0x8000)


# --- Windows and processes ---------------------------------------------------

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
GA_ROOT = 2

user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


def foreground_window_handle():
    """The window in front, or None (for example while windows are switching)."""
    return user32.GetForegroundWindow()


def top_level_window_at(x, y):
    """The top-level window that owns the pixel (x, y), or None."""
    child = user32.WindowFromPoint(wintypes.POINT(x, y))
    return user32.GetAncestor(child, GA_ROOT) if child else None


def window_title(handle):
    length = user32.GetWindowTextLengthW(handle)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, buffer, length + 1)
    return buffer.value


def window_process_id(handle):
    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
    return process_id.value or None


def process_path(process_id):
    """The full path of the process's program, or None if Windows will not say.

    Windows refuses for some protected system processes; the caller treats
    that as unknown.
    """
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


# --- Global hotkey ------------------------------------------------------------

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int


def register_hotkey(hotkey_id, modifiers, virtual_key):
    """Ask Windows to tell this thread when the key combination is pressed anywhere.

    Fails if another program has already registered the same combination.
    """
    return bool(user32.RegisterHotKey(None, hotkey_id, modifiers | MOD_NOREPEAT, virtual_key))


def wait_for_hotkey(hotkey_id):
    """Block this thread until the registered hotkey is pressed."""
    message = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
        if message.message == WM_HOTKEY and message.wParam == hotkey_id:
            return
