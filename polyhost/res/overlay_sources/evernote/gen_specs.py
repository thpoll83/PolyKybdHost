#!/usr/bin/env python3
"""Write the Evernote desktop overlay spec, `evernote.yaml`, from one table.

Each row is (icon, label, Windows key, macOS key), read from Evernote's help
center article "Keyboard shortcuts" (see SOURCES.md), whose tables have a Mac
column and a Windows column. Evernote has no Linux app.

A key is written as modifier letters and a key name joined by "+": C Ctrl,
A Alt (Option on a Mac), S Shift, M Cmd. None means the platform has no key,
or the key is left out (SOURCES.md says why).

The article writes some macOS keys as the shifted character: `{` `}` `|` `>`
`<` `+`. They are read as the US-layout key with Shift (`{` is Shift+[, `+`
is Shift+=), the same way it writes Zoom in as Cmd+= without Shift.

* The same chord on both platforms is written once, with literal modifiers.
* A macOS chord that is the Windows chord with Ctrl replaced by Cmd becomes
  one `CMDCTRL` binding.
* Any other row is written twice, under `except: [macos]` and `only: [macos]`.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/evernote/gen_specs.py
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

MODS = {"C": "CTRL", "A": "ALT", "S": "SHIFT", "M": "GUI"}
KEYS = {",": "COMMA", ".": "DOT", "=": "EQUAL", "-": "MINUS", "/": "SLASH",
        "[": "LBRACKET", "]": "RBRACKET", "\\": "BACKSLASH", "'": "QUOTE",
        "Bksp": "BSPC", "Del": "DELETE", "Space": "SPACE", "Up": "UP",
        "Down": "DOWN", "Left": "LEFT", "Right": "RIGHT"}

ROWS = [
    # --- general ---
    ("newnote", "New note", "C+N", "M+N"),
    ("newnotebook", "New notebook", "AS+N", "MS+N"),
    ("newspace", "New space", "AS+S", "MS+S"),
    ("newtask", "New task", "A+T", "M+T"),
    ("newtag", "New tag", "CS+T", "MC+T"),
    ("newevent", "New event", "C+E", "M+E"),
    ("search", "Search", "C+K", "M+K"),
    ("scratchpad", "Convert Scratch Pad to note", "CS+N", "MA+N"),
    ("trash", "Move to Trash", "Del", "M+Bksp"),
    ("selectall", "Select all", "C+A", "M+A"),
    ("closewindow", "Close window", "C+W", "M+W"),
    ("shortcuts", "Keyboard shortcuts", "C+/", "M+/"),
    ("settings", "Settings", "C+,", "M+,"),
    # --- navigation ---
    ("switchto", "Switch to", "C+Q", "M+J"),
    ("shortcut1", "Open shortcut 1", "C+1", "M+1"),
    ("shortcut2", "Open shortcut 2", "C+2", "M+2"),
    ("shortcut3", "Open shortcut 3", "C+3", "M+3"),
    ("shortcut4", "Open shortcut 4", "C+4", "M+4"),
    ("shortcut5", "Open shortcut 5", "C+5", "M+5"),
    ("shortcut6", "Open shortcut 6", "C+6", "M+6"),
    ("shortcut7", "Open shortcut 7", "C+7", "M+7"),
    ("shortcut8", "Open shortcut 8", "C+8", "M+8"),
    ("shortcut9", "Open shortcut 9", "C+9", "M+9"),
    ("home", "Open Home", "CA+1", "MA+1"),
    ("notes", "Open Notes", "CA+2", "MA+2"),
    ("tasks", "Open Tasks", "CA+3", "MA+3"),
    ("files", "Open Files", "CA+4", "MA+4"),
    ("calendar", "Open Calendar", "CA+5", "MA+5"),
    ("notebooks", "Open Notebooks", "CA+6", "MA+6"),
    ("tags", "Open Tags", "CA+7", "MA+7"),
    ("shared", "Open Shared with Me", "CA+8", "MA+8"),
    ("templates", "Open Templates", "CA+9", "MA+9"),
    ("snippetview", "Snippet view", "C+F5", "S+F5"),
    ("cardview", "Card view", "C+F6", "S+F6"),
    ("toplist", "Top list view", "C+F7", "S+F7"),
    ("sidelist", "Side list view", "C+F8", "S+F8"),
    ("listview", "Switch note list view", "F5", "F5"),
    ("tagfilter", "Open tag filter", "A+F2", "MS+J"),
    ("back", "Back", "A+Left", "M+["),
    ("forward", "Forward", "A+Right", "M+]"),
    ("focuslist", "Focus note list", "CA+\\", "MS+\\"),
    ("focusformat", "Focus formatting bar", "CA+F10", "A+F10"),
    ("listprev", "Previous note list mode", "CA+Left", "MA+Left"),
    ("listnext", "Next note list mode", "CA+Right", "MA+Right"),
    # --- view ---
    ("zoomin", "Zoom in", "C+=", "M+="),
    ("zoomout", "Zoom out", "C+-", "M+-"),
    ("zoomreset", "Zoom to 100%", "C+0", "M+0"),
    ("sidebar", "Expand or collapse sidebar", "F10", "MA+S"),
    ("fullscreen", "Full screen", "F11", "MC+F"),
    # --- note actions ---
    ("newwindow", "Open note in new window", "A+O", "M+O"),
    ("liteeditor", "Open note in Lite editor", "CA+O", "MA+O"),
    ("share", "Share", "A+S", "M+S"),
    ("move", "Move note", "AS+M", "MC+M"),
    ("addtag", "Add tag", "F3", "M+'"),
    ("edittags", "Edit tags", "CA+T", "MCA+T"),
    ("copylink", "Copy note link", "CA+L", "M+L"),
    ("internallink", "Copy internal link", "CAS+C", "MCA+C"),
    ("noteinfo", "Note info", "CS+I", "MS+I"),
    ("print", "Print", "C+P", "M+P"),
    ("rename", "Rename", "F2", "F2"),
    # --- editing ---
    ("undo", "Undo", "C+Z", "M+Z"),
    ("redo", "Redo", "C+Y", "MS+Z"),
    ("copy", "Copy", "C+C", "M+C"),
    ("cut", "Cut", "C+X", "M+X"),
    ("paste", "Paste", "C+V", "M+V"),
    ("pastematch", "Paste and match style", "CS+V", "MS+V"),
    ("find", "Find within note", "C+F", "M+F"),
    ("replace", "Find and replace", "C+H", "MS+F"),
    ("notelink", "Add note link", "CA+K", "MA+K"),
    ("divider", "Insert divider", "CS+-", "MS+H"),
    ("codeblock", "Insert code block", "CS+L", "MC+B"),
    ("insertdate", "Insert date", "AS+D", "MS+D"),
    ("inserttime", "Insert time", "CS+D", "MAS+D"),
    ("comment", "Add comment", None, "MS+M"),
    # --- text formatting ---
    ("fontup", "Increase font size", "CS+.", "MS+."),
    ("fontdown", "Decrease font size", "CS+,", "MS+,"),
    ("bold", "Bold", "C+B", "M+B"),
    ("italic", "Italic", "C+I", "M+I"),
    ("underline", "Underline", "C+U", "M+U"),
    ("highlight", "Highlight", "CS+H", "MC+H"),
    ("bullets", "Bulleted list", "CS+B", "MS+U"),
    ("numbered", "Numbered list", "CS+O", "MS+O"),
    ("checklist", "Checklist", "CS+C", "MS+C"),
    ("alignleft", "Align left", "C+L", "MAS+["),
    ("aligncenter", "Align center", None, "MAS+="),
    ("alignright", "Align right", "C+J", "MAS+]"),
    ("justify", "Justify", None, "MA+-"),
    ("indent", "Indent", "C+M", "MS+]"),
    ("outdent", "Outdent", "CS+M", "MS+["),
    ("strike", "Strikethrough", "C+T", "MC+K"),
    ("superscript", "Superscript", "CS+Up", "MCS+="),
    ("subscript", "Subscript", "CS+Down", "MC+-"),
    ("simplify", "Simplify formatting", "C+Space", None),
    ("removeformat", "Remove formatting", "CS+Space", "MS+Space"),
    ("encrypt", "Encrypt selected text", "CS+X", "MS+X"),
    # --- AI Assistant ---
    ("ai", "Toggle AI Assistant", "A+A", "A+A"),
    ("aiexpand", "Expand or collapse AI Assistant", "AS+A", "AS+A"),
    ("aichat", "New AI chat", "A+C", "A+C"),
]

# Labels that would fold onto a shared concept but mean something else here.
NOT_SHARED = {"Move to Trash"}

HEADER = """\
# Evernote desktop shortcut overlays for PolyKybd. See SOURCES.md.
# GENERATED by gen_specs.py from its table -- edit the table, not this file.
#
# Keys: Evernote's help center article "Keyboard shortcuts"
# https://help.evernote.com/hc/en-us/articles/34296687388307
# (Mac and Windows columns). Evernote has no Linux app.
#
# Regenerate (from the repo root, with the project venv):
#   PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/evernote/gen_specs.py
#   PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/evernote/fetch_icons.py
#   .venv/bin/python scripts/generate_app_overlays.py \\
#       polyhost/res/overlay_sources/evernote/evernote.yaml --preview /tmp/evernote_preview
app: evernote
match: [evernote]
output: evernote_template
icon_dir: icons
fit: contain
anchor: bottom-right
region: [40, 36]
margin: 0
mode: luma
threshold: 150

program_icon: evernote.png
program_icon_mode: alpha
program_icon_anchor: right
program_icon_region: [37, 32]
program_icon_margin: 0

bindings:
"""


def parse(chord: str) -> tuple[str, list[str]]:
    """'CS+P' -> ('P', ['CTRL', 'SHIFT']); 'F5' -> ('F5', [])."""
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
    (HERE / "evernote.yaml").write_text(text, encoding="utf-8")
    print(f"evernote.yaml: {text.count(chr(10) + '  - {')} bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
