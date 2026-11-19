"""Screen input and output: screenshots in, mouse and keyboard out (build piece 1).

The modules, one job each:

- grid.py      converts the model's 0 to 1000 grid to pixels (no Windows calls)
- win32.py     the Windows calls, made through ctypes; importing it makes the
               process DPI aware
- display.py   screen size, display scaling, screenshots
- mouse.py     click, double-click, scroll, drag
- keyboard.py  type text, press keys such as "ctrl+s"
- window.py    the foreground window's title and process
- stop.py      the emergency stop hotkey, Ctrl+Alt+Q

Only the primary monitor is used. Nothing here needs administrator rights.
This package logs nothing; logging belongs to the audit code (piece 9).
"""
