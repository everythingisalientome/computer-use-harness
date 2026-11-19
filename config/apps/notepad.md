---
schema_version: 1
id: notepad
name: Notepad
kind: desktop
launch:
  executable: notepad.exe
  wait_seconds: 3
# For a desktop app the check is by process: any window that belongs to this
# process is allowed. That includes the app's own dialogs, such as Save As.
allowed_window:
  match: process
  processes: [notepad.exe]
home:
  how: Click inside the large text area.
  looks_like: A Notepad window with File, Edit and View menus above a large text area.
---

# Notepad app context

Each line is marked **seen** (observed on the build machine, Windows 11, on 2026-11-19) or **not checked**. Notepad differs between Windows versions.

## Opening the app

- Notepad needs no sign-in and no administrator rights. (not checked)
- On recent Windows versions Notepad can reopen with text from an earlier session. Do not assume the text area is empty. (not checked)

## Layout

- A tab bar runs across the top of the window. Each tab is a separate document. (seen)
- The tab's title is the file name, or "Untitled" before saving. (not checked)
- Below the tab bar is a menu bar with File, Edit and View, and a formatting toolbar (bold, italic, lists, links, tables) on the same row. (seen)
- A large text area fills the rest of the window, with a status bar at the bottom. (seen)

## Starting a new document

- Ctrl+N opens a new, empty document. On versions with tabs it opens as a new tab. (not checked)

## Saving with Save As

- Ctrl+Shift+S opens the Save As dialog. (seen)
- On a document never saved before, Ctrl+S opens the same dialog. (not checked)
- The Save As dialog, titled "Save as", opens in front of Notepad, showing the Downloads folder. (seen)
- The Save As dialog is a window of the Notepad process, notepad.exe. (seen)
- It has a "File name" box near the bottom, filled in with "Untitled.txt" for a new document, and Save and Cancel buttons below it at the right. (seen)
- Typing a full path, including the file name, into the "File name" box and pressing Enter saves the file to that location, whatever folder the dialog is showing. Because the dialog opens in Downloads, always type the full path. (not checked)
- If a file with that name already exists, a small dialog asks whether to replace it. Choose Yes. (not checked)
- After saving, the dialog closes and the tab or window title shows the file name. (not checked)

## Known interruptions

None observed yet. Add each one here as it is found, with how to dismiss it.
