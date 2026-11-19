"""The harmless test window used by `scripts\\screen.py check`. Not run by hand.

A full-screen window, drawn by its own Python process, that reports every
mouse and keyboard event it receives as one JSON line on its output. The check
compares what it sent with what arrived. Nothing outside this window is touched.

It closes itself when told to ("quit" on its input), when the check process
ends, or after LIFETIME_SECONDS, so it can never stay stuck on top of the screen.
"""

import json
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.screen import win32  # noqa: E402  importing it makes this window DPI aware, so positions are real pixels
from harness.screen.grid import grid_to_pixel  # noqa: E402

TITLE = "Screen check target"
LIFETIME_SECONDS = 90

# Grid positions the check clicks: the four corners, the middle, and points between.
CLICK_POINTS = [(0, 0), (1000, 0), (0, 1000), (1000, 1000), (500, 500),
                (250, 250), (750, 250), (250, 750), (750, 750)]
# The two text boxes, the double-click and right-click spot, the scroll spot, and the drag line.
ENTRY_POINTS = [(500, 380), (500, 440)]
DOUBLE_CLICK_POINT = (350, 600)
SCROLL_POINT = (650, 600)
DRAG_FROM, DRAG_TO = (300, 880), (700, 880)


def send(event, **fields):
    print(json.dumps({"event": event, **fields}), flush=True)


class Target:
    def __init__(self, root):
        self.root = root
        self.commands = queue.Queue()
        self.drag_motions = 0

        root.title(TITLE)
        root.geometry("+0+0")  # the primary monitor
        root.attributes("-fullscreen", True)
        root.attributes("-topmost", True)
        width, height = root.winfo_screenwidth(), root.winfo_screenheight()
        self.width, self.height = width, height

        canvas = tk.Canvas(root, width=width, height=height, bg="white", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        self.canvas = canvas
        canvas.create_text(width // 2, height // 6, fill="#333333", font=("Segoe UI", 18),
                           text="Screen check in progress. Press Ctrl+Alt+Q to stop it.")
        for gx, gy in CLICK_POINTS + [DOUBLE_CLICK_POINT, SCROLL_POINT, DRAG_FROM, DRAG_TO]:
            x, y = self.pixel(gx, gy)
            canvas.create_line(x - 15, y, x + 16, y, fill="#999999")
            canvas.create_line(x, y - 15, x, y + 16, fill="#999999")
        canvas.create_line(*self.pixel(*DRAG_FROM), *self.pixel(*DRAG_TO), fill="#cccccc", dash=(4, 4))

        self.entries = []
        for gx, gy in ENTRY_POINTS:
            entry = tk.Entry(root, font=("Segoe UI", 16), width=40)
            canvas.create_window(*self.pixel(gx, gy), window=entry)
            self.entries.append(entry)

        canvas.bind("<ButtonPress-1>", self.on_press)
        canvas.bind("<ButtonRelease-1>", self.on_release)
        canvas.bind("<B1-Motion>", self.on_motion)
        canvas.bind("<Double-Button-1>", lambda e: send("double_click", x=e.x_root, y=e.y_root))
        canvas.bind("<ButtonPress-3>", lambda e: send("right_click", x=e.x_root, y=e.y_root))
        root.bind_all("<MouseWheel>", lambda e: send("wheel", delta=e.delta, x=e.x_root, y=e.y_root))
        root.bind_all("<Shift-MouseWheel>", lambda e: send("hwheel", delta=e.delta, x=e.x_root, y=e.y_root))
        # Bound on the window, not with bind_all: tkinter's own Tab binding sits
        # on "all" and would hide Tab from a bind_all handler.
        root.bind("<KeyPress>", self.on_key)

        threading.Thread(target=self.read_commands, daemon=True).start()
        root.after(50, self.poll_commands)
        root.after(LIFETIME_SECONDS * 1000, root.destroy)
        root.after(500, self.report_ready)

    def pixel(self, gx, gy):
        return grid_to_pixel(gx, gy, self.width, self.height)

    def report_ready(self):
        self.root.update_idletasks()
        self.root.focus_force()
        entries = [[e.winfo_rootx() + e.winfo_width() // 2, e.winfo_rooty() + e.winfo_height() // 2]
                   for e in self.entries]
        send("ready", pid=os.getpid(), width=self.width, height=self.height,
             window_width=self.root.winfo_width(), window_height=self.root.winfo_height(),
             entries=entries)

    def on_press(self, event):
        # A red dot where the press arrived; the check looks for it in a screenshot.
        x, y = event.x, event.y
        self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="red", outline="red")
        self.drag_motions = 0
        send("press", x=event.x_root, y=event.y_root)

    def on_motion(self, event):
        self.drag_motions += 1

    def on_release(self, event):
        send("release", x=event.x_root, y=event.y_root, motions=self.drag_motions)

    def on_key(self, event):
        send("key", keysym=event.keysym, char=event.char,
             ctrl=bool(event.state & 0x4), shift=bool(event.state & 0x1))

    def read_commands(self):
        for line in sys.stdin:
            self.commands.put(line.strip())
        self.commands.put("quit")  # the check process has ended

    def poll_commands(self):
        while not self.commands.empty():
            command = self.commands.get()
            if command == "quit":
                self.root.destroy()
                return
            if command == "text":
                send("text", values=[e.get() for e in self.entries])
            elif command == "clear":
                for entry in self.entries:
                    entry.delete(0, "end")
                send("cleared")
        self.root.after(50, self.poll_commands)


def main():
    root = tk.Tk()
    Target(root)
    root.mainloop()


if __name__ == "__main__":
    main()
