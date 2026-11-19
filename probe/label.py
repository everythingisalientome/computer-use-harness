"""Draw the true box around each element on the probe screenshots.

Usage:
  .venv\\Scripts\\python probe\\label.py              label every element that has no box yet
  .venv\\Scripts\\python probe\\label.py <screen_id>  (re)label every element on one screen
  .venv\\Scripts\\python probe\\label.py --review     only write the review images (below)

In the window:
  drag with the mouse   draw the box (drag again to redraw)
  Enter                 accept the box and go to the next element
  S                     skip this element (it is not on the screenshot)
  Escape                stop; boxes accepted so far are already saved

Boxes are saved to probe/labels.yaml in screenshot pixels, after every Enter.
The screenshot may be shown smaller than real size so it fits on the monitor.

When labelling ends, one review image per screen is written to probe/review/,
with every box drawn and named. Look through them before running the probe:
a box on the wrong element shows up here, instead of as a false miss.
"""

import sys
import tkinter as tk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from common import PROBE_DIR, SCREENS_DIR, find_screen, load_labels, load_screens, save_labels

REVIEW_DIR = PROBE_DIR / "review"


def build_queue(only_screen_id):
    """Return the (screen, element) pairs to label, in order."""
    labels = load_labels()
    screens = [find_screen(only_screen_id)] if only_screen_id else load_screens()
    queue = []
    for screen in screens:
        if not (SCREENS_DIR / f"{screen['id']}.png").exists():
            print(f"No screenshot yet for '{screen['id']}', skipping it. Run capture.py first.")
            continue
        for element in screen["elements"]:
            already_done = element["id"] in labels.get(screen["id"], {})
            if only_screen_id or not already_done:
                queue.append((screen, element))
    return queue


class Labeller:
    def __init__(self, root, queue):
        self.root = root
        self.queue = queue
        self.position = 0
        self.labels = load_labels()
        self.loaded_screen_id = None
        self.drag_start = None
        self.box = None  # [left, top, right, bottom] on the canvas, not yet accepted

        self.prompt = tk.Label(root, font=("Segoe UI", 13, "bold"), anchor="w")
        self.prompt.pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(root, anchor="w", text="Drag to draw.  Enter = accept.  S = skip.  Esc = stop.").pack(fill="x", padx=8)
        self.canvas = tk.Canvas(root, highlightthickness=0, cursor="crosshair")
        self.canvas.pack()

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        root.bind("<Return>", self.on_accept)
        root.bind("<s>", self.on_skip)
        root.bind("<Escape>", lambda event: root.destroy())

        self.show_current()

    def show_current(self):
        if self.position >= len(self.queue):
            print("All done. Boxes are in probe/labels.yaml")
            self.root.destroy()
            return
        screen, element = self.queue[self.position]
        if screen["id"] != self.loaded_screen_id:
            self.load_screenshot(screen["id"])
        self.prompt.config(text=f"[{self.position + 1}/{len(self.queue)}]  {screen['id']}:  {element['name']}")
        self.box = None
        self.redraw()

    def load_screenshot(self, screen_id):
        image = Image.open(SCREENS_DIR / f"{screen_id}.png")
        # Shrink to fit the monitor, leaving room for the title bar, text and taskbar.
        room_w = self.root.winfo_screenwidth() - 40
        room_h = self.root.winfo_screenheight() - 160
        self.scale = min(1.0, room_w / image.width, room_h / image.height)
        shown = image.resize((round(image.width * self.scale), round(image.height * self.scale)), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(shown)
        self.canvas.config(width=shown.width, height=shown.height)
        self.loaded_screen_id = screen_id

    def redraw(self):
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        # Boxes already accepted on this screen, thin and grey, for reference.
        for box in self.labels.get(self.loaded_screen_id, {}).values():
            self.canvas.create_rectangle(*[v * self.scale for v in box], outline="grey", width=1)
        if self.box:
            self.canvas.create_rectangle(*self.box, outline="red", width=2)

    def on_press(self, event):
        self.drag_start = (event.x, event.y)

    def on_drag(self, event):
        x0, y0 = self.drag_start
        self.box = [min(x0, event.x), min(y0, event.y), max(x0, event.x), max(y0, event.y)]
        self.redraw()

    def on_accept(self, event):
        if not self.box:
            return
        screen, element = self.queue[self.position]
        # Convert from the shown size back to real screenshot pixels.
        real_box = [round(v / self.scale) for v in self.box]
        self.labels.setdefault(screen["id"], {})[element["id"]] = real_box
        save_labels(self.labels)
        self.position += 1
        self.show_current()

    def on_skip(self, event):
        screen, element = self.queue[self.position]
        print(f"Skipped {screen['id']} / {element['id']}")
        self.position += 1
        self.show_current()


def write_review_images():
    """Save each labelled screenshot with every box drawn and named, to probe/review/."""
    labels = load_labels()
    font = ImageFont.load_default(size=16)
    REVIEW_DIR.mkdir(exist_ok=True)
    for screen in load_screens():
        boxes = labels.get(screen["id"])
        screenshot = SCREENS_DIR / f"{screen['id']}.png"
        if not boxes or not screenshot.exists():
            continue
        image = Image.open(screenshot).convert("RGB")
        draw = ImageDraw.Draw(image)
        for element_id, box in boxes.items():
            draw.rectangle(box, outline="red", width=2)
            # The name sits just below the box, on a white strip so it reads on any background.
            text_box = draw.textbbox((box[0], box[3] + 3), element_id, font=font)
            draw.rectangle(text_box, fill="white")
            draw.text((box[0], box[3] + 3), element_id, fill="red", font=font)
        image.save(REVIEW_DIR / f"{screen['id']}.png")
    print(f"Review images written to {REVIEW_DIR}. Check every box before running the probe.")


def main():
    if sys.argv[1:] == ["--review"]:
        write_review_images()
        return
    only_screen_id = sys.argv[1] if len(sys.argv) > 1 else None
    queue = build_queue(only_screen_id)
    if not queue:
        print("Nothing to label.")
        return
    root = tk.Tk()
    root.title("Probe labeller")
    Labeller(root, queue)
    root.mainloop()
    write_review_images()


if __name__ == "__main__":
    main()
