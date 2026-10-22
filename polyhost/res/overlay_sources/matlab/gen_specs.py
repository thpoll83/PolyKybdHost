#!/usr/bin/env python3
"""Write the MATLAB Editor overlay spec from one table.

The keys are from MathWorks' "Editor Keyboard Shortcuts" page for R2026b
(mathworks.com/help/matlab/matlab_prog/editor-keyboard-shortcuts.html), its
Windows/Linux and macOS columns. They are the default key set.

Each row: (icon, label, Windows/Linux key, macOS key). A key is written as
modifier letters and a key name joined by "+": C Ctrl (Control on a Mac),
A Alt (Option on a Mac), S Shift, M Cmd. None means no key on that platform.
See SOURCES.md for the keys left out.

    python polyhost/res/overlay_sources/matlab/gen_specs.py
    python scripts/generate_app_overlays.py polyhost/res/overlay_sources/matlab/bindings.yaml
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

MODS = {"C": "CTRL", "A": "ALT", "S": "SHIFT", "M": "GUI"}
KEYS = {"Enter": "ENTER", "Up": "UP", "Down": "DOWN", "Left": "LEFT",
        "Right": "RIGHT", "Home": "HOME", "End": "END", ",": "COMMA",
        ".": "DOT", "/": "SLASH", "-": "MINUS", "=": "EQUAL", "[": "LBRACKET", "]": "RBRACKET"}


def both(win, mac=None):
    return win, (win if mac is None else mac)


ROWS = [
    # --- editor window ---
    ("maximize", "Maximize Editor", *both("CS+M", "MS+M")),
    ("undock", "Undock Editor", *both("CS+U")),
    ("dock", "Dock Editor", *both("CS+D")),
    ("editor", "Go to Editor", *both("CS+0", "MS+0")),
    # --- files ---
    ("newscript", "New script", *both("C+N", "M+N")),
    (None, "Open", *both("C+O", "M+O")),
    ("reopen", "Reopen closed file", *both("CS+T", "MS+T")),
    (None, "Save", *both("C+S", "M+S")),
    (None, "Print", *both("C+P", "M+P")),
    (None, "Close", *both("C+W", "M+W")),
    (None, "Undo", *both("C+Z", "M+Z")),
    (None, "Redo", *both("C+Y", "MS+Z")),
    # --- navigate ---
    ("gotoline", "Go to line", *both("C+G", "M+L")),
    ("bookmark", "Set or clear bookmark", *both("C+F2", "M+F2")),
    ("nextbookmark", "Next bookmark", *both("+F2")),
    ("prevbookmark", "Previous bookmark", *both("S+F2")),
    ("back", "Back", *both("A+Left", "C+-")),
    ("forward", "Forward", *both("A+Right", "CS+-")),
    ("prevvar", "Previous variable instance", *both("A+Up")),
    ("nextvar", "Next variable instance", *both("A+Down")),
    ("filestart", "Start of file", "C+Home", None),
    ("fileend", "End of file", "C+End", None),
    ("prevsection", "Previous section", "C+Up", None),
    ("nextsection", "Next section", "C+Down", None),
    # --- find ---
    (None, "Find", *both("C+F", "M+F")),
    ("findnext", "Find next", *both("+F3", "M+G")),
    ("findprev", "Find previous", *both("S+F3", "MS+G")),
    ("replace", "Find and replace", *both("C+H", "MA+F")),
    ("findsel", "Find selection", *both("C+F3", "M+E")),
    # --- code ---
    ("comment", "Comment", *both("C+R", "M+/")),
    ("uncomment", "Uncomment", *both("CS+R", "MA+/")),
    ("wrap", "Wrap comments", *both("C+J", "MS+W")),
    ("smartindent", "Smart indent", *both("C+I", "M+I")),
    ("indent", "Increase indent", *both("C+]", "M+]")),
    ("outdent", "Decrease indent", *both("C+[", "M+[")),
    ("duplicate", "Duplicate line", *both("CS+C", "MS+C")),
    ("changecase", "Change case", *both("CS+A", "MS+A")),
    ("analyzer", "Code Analyzer message", "C+M", None),
    # --- sections and running ---
    ("sectionbreak", "Insert section break", *both("CA+Enter", "MA+Enter")),
    ("runsection", "Run section", *both("C+Enter", "M+Enter")),
    ("runadvance", "Run section and advance", *both("CS+Enter", "MS+Enter")),
    ("run", "Run", *both("+F5")),
    ("pause", "Pause", *both("C+F5", "M+F5")),
    ("stop", "Quit execution", *both("S+F5")),
    ("breakpoint", "Set or clear breakpoint", *both("+F12")),
    ("stepover", "Step", *both("+F10")),
    ("stepin", "Step in", *both("+F11")),
    ("stepout", "Step out", *both("S+F11")),
    # --- live scripts ---
    ("textline", "Insert text line", *both("A+Enter")),
    ("normaltext", "Normal text", *both("CA+T")),
    ("h1", "Heading 1", *both("CS+1")),
    ("h2", "Heading 2", *both("CS+2")),
    ("h3", "Heading 3", *both("CS+3")),
    ("titletext", "Title text", *both("CA+L")),
    (None, "Bold", *both("C+B", "M+B")),
    (None, "Underline", *both("C+U", "M+U")),
    ("monospace", "Monospaced", None, "C+M"),
    ("bullets", "Bulleted list", *both("CA+U")),
    ("numbered", "Numbered list", *both("CA+O")),
    ("link", "Hyperlink", *both("C+K", "M+K")),
    ("equation", "Equation", *both("CS+E", "MS+E")),
    ("latex", "LaTeX equation", *both("CS+L", "MS+L")),
    ("codeoutput", "Code or output", *both("CS+O", "MA+O")),
    # --- display ---
    ("fullscreen", "Full screen", *both("C+F11", "M+F11")),
    (None, "Zoom in", *both("C+=", "M+=")),
    (None, "Zoom out", *both("C+-", "M+-")),
    ("resetzoom", "Reset zoom", *both("CA+0", "MA+0")),
    ("mdpreview", "Markdown preview", *both("CS+K", "MS+K")),
    # --- folding (Control on a Mac too) ---
    ("expand", "Expand fold", *both("CS+.")),
    ("collapse", "Collapse fold", *both("C+.")),
    ("expandall", "Expand all", *both("CS+,")),
    ("collapseall", "Collapse all", *both("C+,")),
    # --- spelling ---
    ("nextspell", "Next spelling issue", *both("A+F7")),
    ("prevspell", "Previous spelling issue", *both("AS+F7")),
]

HEADER = """\
# MATLAB Editor shortcut overlays for PolyKybd (Windows, Linux and macOS).
# GENERATED by gen_specs.py from its table -- edit the table, not this file.
#
# Shortcuts: MathWorks, "Editor Keyboard Shortcuts" (R2026b). See SOURCES.md.
#
# Regenerate:
#   python polyhost/res/overlay_sources/matlab/fetch_icons.py
#   python polyhost/res/overlay_sources/matlab/gen_specs.py
#   python scripts/generate_app_overlays.py \\
#       polyhost/res/overlay_sources/matlab/bindings.yaml --preview /tmp/matlab_preview
app: matlab
match: [matlab]
output: matlab_template
icon_dir: icons
fit: contain
anchor: bottom-right
region: [36, 32]
margin: 0
mode: luma
threshold: 150

program_icon: matlab.png
program_icon_mode: alpha
program_icon_anchor: right
program_icon_region: [37, 32]
program_icon_margin: 0

bindings:
"""

# Labels that would fold onto a shared concept but mean something else here.
NOT_SHARED = {"Find next", "Find previous", "Find selection", "Back", "Forward",
              "Comment"}


def parse(chord: str) -> tuple[str, list[str]]:
    mods, key = chord.split("+", 1)
    key = KEYS.get(key, key)
    return f'"{key}"', [MODS[m] for m in mods]


def line(icon, label, chord, mac: bool) -> str:
    key, mods = parse(chord)
    parts = [f"key: {key}", f"mods: [{', '.join(mods)}]"]
    if icon:
        parts.append(f"icon: {icon}.png")
    parts.append(f'label: "{label}"')
    if label in NOT_SHARED:
        parts.append("shared: false")
    parts.append("only: [macos]" if mac else "except: [macos]")
    return "  - { " + ", ".join(parts) + " }"


def main() -> int:
    out = [HEADER]
    for icon, label, win, mac in ROWS:
        if win:
            out.append(line(icon, label, win, mac=False))
        if mac:
            out.append(line(icon, label, mac, mac=True))
    text = "\n".join(out) + "\n"
    (HERE / "bindings.yaml").write_text(text, encoding="utf-8")
    print(f"bindings.yaml: {text.count(chr(10) + '  - {')} bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
