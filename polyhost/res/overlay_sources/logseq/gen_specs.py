#!/usr/bin/env python3
"""Write the Logseq desktop overlay spec, `logseq.yaml`, from one table.

Each row is (icon, label, Windows/Linux key, macOS key). The keys are Logseq's
built-in shortcuts, `all-built-in-keyboard-shortcuts` in
`src/main/frontend/modules/shortcut/config.cljs`, where `mod` is Ctrl or Cmd
and `(if mac? a b)` picks a per-platform chord, plus the Electron menu of
`src/electron/electron/core.cljs` (new window, zoom, full screen, paste). See
SOURCES.md.

A key is written as modifier letters and a key name joined by "+": C Ctrl,
A Alt (Option on a Mac), S Shift, M Cmd. None means the platform has no key.

* The same chord on both platforms is written once, with literal modifiers.
* A macOS chord that is the Windows chord with Ctrl replaced by Cmd becomes
  one `CMDCTRL` binding.
* Any other row is written twice, under `except: [macos]` and `only: [macos]`.

Linux takes the non-mac chords, the same as Windows, so there is no Linux set.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/logseq/gen_specs.py
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

MODS = {"C": "CTRL", "A": "ALT", "S": "SHIFT", "M": "GUI"}
KEYS = {",": "COMMA", ".": "DOT", "=": "EQUAL", "-": "MINUS", "/": "SLASH",
        ";": "SEMICOLON", "[": "LBRACKET", "]": "RBRACKET", "Enter": "ENTER",
        "Space": "SPACE", "Up": "UP", "Down": "DOWN", "Left": "LEFT",
        "Right": "RIGHT"}

ROWS = [
    # --- while editing a block ---
    ("followlink", "Follow link", "C+O", "M+O"),
    ("linksidebar", "Open link in sidebar", "CS+O", "MS+O"),
    ("bold", "Bold", "C+B", "M+B"),
    ("italic", "Italic", "C+I", "M+I"),
    ("highlight", "Highlight", "CS+H", "MS+H"),
    ("strike", "Strikethrough", "CS+S", "MS+S"),
    ("clearblock", "Clear block", "A+L", "C+L"),
    ("killbefore", "Delete to line start", "A+U", "C+U"),
    ("killafter", "Delete to line end", "A+K", None),
    ("blockstart", "Go to block start", "A+A", None),
    ("blockend", "Go to block end", "A+E", None),
    ("wordnext", "Next word", "A+F", "CS+F"),
    ("wordprev", "Previous word", "A+B", "CS+B"),
    ("killwordnext", "Delete next word", "A+D", "C+W"),
    ("killwordprev", "Delete previous word", "A+W", None),
    ("copyembed", "Copy block embed", "CS+E", "MS+E"),
    ("pasteoneblock", "Paste as one block", "CS+V", "MS+V"),
    ("ytstamp", "Insert YouTube timestamp", "CS+Y", "MS+Y"),
    ("comment", "Add comment", "C+Space", "C+Space"),
    ("zoomblock", "Zoom into block", "A+Right", "M+."),
    ("unzoomblock", "Zoom out of block", "A+Left", "M+,"),
    # --- blocks ---
    ("cycletodo", "Cycle TODO state", "C+Enter", "M+Enter"),
    ("moveup", "Move block up", "AS+Up", "MS+Up"),
    ("movedown", "Move block down", "AS+Down", "MS+Down"),
    ("moveblocks", "Move blocks to", "CS+M", "MS+M"),
    ("selectup", "Select block above", "A+Up", "A+Up"),
    ("selectdown", "Select block below", "A+Down", "A+Down"),
    ("expand", "Expand children", "C+Down", "M+Down"),
    ("collapse", "Collapse children", "C+Up", "M+Up"),
    ("togglechildren", "Toggle open blocks", "C+;", "M+;"),
    ("selectparent", "Select parent block", "C+A", "M+A"),
    ("selectall", "Select all blocks", "CS+A", "MS+A"),
    ("copy", "Copy", "C+C", "M+C"),
    ("copytext", "Copy as plain text", "CS+C", "MS+C"),
    ("cut", "Cut", "C+X", "M+X"),
    ("paste", "Paste", "C+V", "M+V"),
    ("undo", "Undo", "C+Z", "M+Z"),
    ("redo", "Redo", "CS+Z", "MS+Z"),
    ("redo", "Redo", "C+Y", "M+Y"),
    ("insertlink", "Insert link", "C+L", "M+L"),
    ("addproperty", "Add property", "CA+P", "M+P"),
    ("quickadd", "Quick capture", "CA+E", "M+E"),
    ("favorite", "Add to favorites", "CS+F", "MS+F"),
    ("jump", "Jump to block", "C+J", "M+J"),
    # --- search and navigation ---
    ("search", "Search", "C+K", "M+K"),
    ("searchpage", "Search in page", "CS+K", "MS+K"),
    ("find", "Find in page", "C+F", "M+F"),
    ("findnext", "Find next", "C+G", "M+G"),
    ("findprev", "Find previous", "CS+G", "MS+G"),
    ("commandpalette", "Command palette", "CS+P", "MS+P"),
    ("searchthemes", "Search themes", "AS+I", "MS+I"),
    ("back", "Back", "C+[", "M+["),
    ("forward", "Forward", "C+]", "M+]"),
    ("today", "Open today in sidebar", "AS+J", "MS+J"),
    ("contents", "Toggle Contents", "AS+C", "AS+C"),
    ("opengraph", "Open graph", "AS+G", "AS+G"),
    ("save", "Save", "C+S", "M+S"),
    ("shell", "Run shell command", "CS+1", "MS+1"),
    ("closewindow", "Close window", "C+W", "M+W"),
    # --- key sequences, outside editing (first key only) ---
    ("goto", "Go to (then H, J, A, G, S, T, N, P, F)", "G", "G"),
    ("toggle", "Toggle (then L, R, D, T, W, B, O, S, C, N)", "T", "T"),
    ("property", "Property (then T, D, S, P, I, R, A)", "P", "P"),
    ("help", "Keyboard shortcuts", "S+/", "S+/"),
    # --- Electron menu ---
    ("newwindow", "New window", "CS+N", "M+N"),
    ("zoomin", "Zoom in", "C+=", "M+="),
    ("zoomout", "Zoom out", "C+-", "M+-"),
    ("zoomreset", "Actual size", "C+0", "M+0"),
    ("fullscreen", "Full screen", "F11", "MC+F"),
]

# Labels that would fold onto a shared concept but mean something else here.
NOT_SHARED: set[str] = set()

HEADER = """\
# Logseq desktop shortcut overlays for PolyKybd. See SOURCES.md.
# GENERATED by gen_specs.py from its table -- edit the table, not this file.
#
# Keys: Logseq's built-in shortcuts (src/main/frontend/modules/shortcut/config.cljs)
# and its Electron menu (src/electron/electron/core.cljs), tag 2.0.2. `mod` is
# CMDCTRL; `(if mac? a b)` rows are written per platform.
#
# Regenerate (from the repo root, with the project venv):
#   PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/logseq/gen_specs.py
#   PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/logseq/fetch_icons.py
#   .venv/bin/python scripts/generate_app_overlays.py \\
#       polyhost/res/overlay_sources/logseq/logseq.yaml --preview /tmp/logseq_preview
app: logseq
match: [logseq]
output: logseq_template
icon_dir: icons
fit: contain
anchor: bottom-right
region: [40, 36]
margin: 0
mode: luma
threshold: 150

program_icon: logseq.png
program_icon_mode: alpha
program_icon_anchor: right
program_icon_region: [37, 32]
program_icon_margin: 0

bindings:
"""


def parse(chord: str) -> tuple[str, list[str]]:
    """'CS+P' -> ('P', ['CTRL', 'SHIFT']); 'G' -> ('G', [])."""
    if "+" in chord and len(chord) > 1:
        mods, key = chord.split("+", 1)
    else:
        mods, key = "", chord
    key = KEYS.get(key, key)
    if key.isdigit():
        key = f'"{key}"'
    return key, [MODS[m] for m in mods]


def line(icon: str, label: str, chord: str, scope: str = "", cmdctrl: bool = False) -> str:
    key, mods = parse(chord)
    if cmdctrl:
        mods = ["CMDCTRL" if m == "CTRL" else m for m in mods]
    parts = [f"key: {key}"] + ([f"mods: [{', '.join(mods)}]"] if mods else [])
    parts += [f"icon: {icon}.png", f'label: "{label}"']
    if label in NOT_SHARED:
        parts.append("shared: false")
    if scope:
        parts.append(scope)
    return "  - { " + ", ".join(parts) + " }"


def ctrl_to_cmd(chord: str) -> str | None:
    if "+" not in chord or len(chord) == 1:
        return None
    mods, key = chord.split("+", 1)
    if "C" not in mods:
        return None
    return "".join("M" if m == "C" else m for m in mods) + "+" + key


def render() -> str:
    out = [HEADER]
    for icon, label, win, mac in ROWS:
        if win and win == mac:
            out.append(line(icon, label, win))
        elif win and mac and ctrl_to_cmd(win) == mac:
            out.append(line(icon, label, win, cmdctrl=True))
        else:
            if win:
                out.append(line(icon, label, win, "except: [macos]"))
            if mac:
                out.append(line(icon, label, mac, "only: [macos]"))
    return "\n".join(out) + "\n"


def main() -> int:
    text = render()
    (HERE / "logseq.yaml").write_text(text, encoding="utf-8")
    print(f"logseq.yaml: {text.count(chr(10) + '  - {')} bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
