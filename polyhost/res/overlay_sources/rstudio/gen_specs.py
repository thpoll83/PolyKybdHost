#!/usr/bin/env python3
"""Write the RStudio overlay spec from one table.

The keys are from Posit's "Keyboard Shortcuts" reference for RStudio 2026.10.0
(docs.posit.co/ide/user/ide/reference/shortcuts.html), its "Windows & Linux"
and "Mac" columns, for the desktop app.

Each row: (icon, label, Windows/Linux key, macOS key). A key is written as
modifier letters and a key name joined by "+": C Ctrl (Control on a Mac),
A Alt (Option on a Mac), S Shift, M Cmd. None means no key on that platform.
See SOURCES.md for the keys left out.

    python polyhost/res/overlay_sources/rstudio/gen_specs.py
    python scripts/generate_app_overlays.py polyhost/res/overlay_sources/rstudio/bindings.yaml
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

MODS = {"C": "CTRL", "A": "ALT", "S": "SHIFT", "M": "GUI"}
KEYS = {"Enter": "ENTER", "Up": "UP", "Down": "DOWN", "Left": "LEFT",
        "Right": "RIGHT", "PgUp": "PGUP", "PgDn": "PGDN", ",": "COMMA",
        ".": "DOT", "/": "SLASH", "-": "MINUS"}


def both(win, mac=None):
    return win, (win if mac is None else mac)


PANES = ["Source", "Console", "Help", "History", "Files", "Plots", "Packages",
         "Environment", "Viewer"]

ROWS = [
    # --- general ---
    ("palette", "Command palette", *both("CS+P", "MS+P")),
    ("shortcuts", "Shortcut reference", *both("AS+K")),
    ("gotofile", "Go to file or function", *both("C+.")),
    ("setwd", "Change working directory", *both("CS+H")),
    ("clearconsole", "Clear console", *both("C+L")),
    ("terminal", "Terminal", *both("AS+M")),
    ("newterminal", "New terminal", *both("AS+R")),
    ("restart", "Restart R", *both("CS+F10", "MS+0")),
    # --- documents ---
    ("newscript", "New R script", *both("CS+N", "MS+N")),
    (None, "Open", *both("C+O", "M+O")),
    (None, "Save", *both("C+S", "M+S")),
    ("saveall", "Save all", *both("CA+S", "MA+S")),
    (None, "Close", *both("C+W", "M+W")),
    ("closeall", "Close all documents", *both("CS+W", "MS+W")),
    ("outline", "Document outline", *both("CS+O", "MS+O")),
    ("knit", "Knit or preview", *both("CS+K", "MS+K")),
    ("insertchunk", "Insert chunk", *both("CA+I", "MA+I")),
    ("insertsection", "Insert code section", *both("CS+R", "MS+R")),
    # --- run ---
    ("runline", "Run line or selection", *both("C+Enter", "M+Enter")),
    ("runretain", "Run, keep cursor", *both("A+Enter")),
    ("rerun", "Re-run previous region", *both("CA+P", "MA+P")),
    ("runall", "Run document", *both("CA+R", "MA+R")),
    ("runtoline", "Run to current line", *both("CA+B", "MA+B")),
    ("runfromline", "Run to end", *both("CA+E", "MA+E")),
    ("runfunction", "Run function", *both("CA+F", "MA+F")),
    ("runsection", "Run code section", *both("CA+T", "MA+T")),
    ("runchunk", "Run chunk", *both("CA+C", "MA+C")),
    ("nextchunk", "Run next chunk", *both("CA+N", "MA+N")),
    ("sourcefile", "Source a file", *both("CA+G")),
    ("sourcedoc", "Source document", *both("CS+S", "MS+S")),
    ("sourceecho", "Source with echo", *both("CS+Enter", "MS+Enter")),
    ("toterminal", "Send to terminal", *both("CA+Enter", "MA+Enter")),
    # --- navigate ---
    ("fold", "Fold", *both("A+L", "MA+L")),
    ("unfold", "Unfold", *both("AS+L", "MAS+L")),
    ("foldall", "Fold all", *both("A+O", "MA+O")),
    ("unfoldall", "Unfold all", *both("AS+O", "MAS+O")),
    ("gotoline", "Go to line", *both("AS+G", "MAS+G")),
    ("jumpto", "Jump to", *both("AS+J", "MAS+J")),
    ("nextsection", "Next section", *both("C+PgDn", "M+PgDn")),
    ("prevsection", "Previous section", *both("C+PgUp", "M+PgUp")),
    ("switchtab", "Switch to tab", *both("CS+.")),
    ("prevtab", "Previous tab", *both("CA+Left")),
    ("nexttab", "Next tab", *both("CA+Right")),
    ("firsttab", "First tab", *both("CAS+Left")),
    ("lasttab", "Last tab", *both("CAS+Right")),
    ("navback", "Navigate back", *both("C+F9", "M+F9")),
    ("navfwd", "Navigate forward", *both("C+F10", "M+F10")),
    ("matchbrace", "Matching brace", *both("C+P")),
    # --- edit ---
    ("expandsel", "Expand selection", *both("CS+Up", "CAS+Up")),
    ("shrinksel", "Shrink selection", *both("CS+Down", "CAS+Down")),
    ("cursorup", "Add cursor above", *both("CA+Up")),
    ("cursordown", "Add cursor below", *both("CA+Down")),
    ("lineup", "Move line up", *both("A+Up")),
    ("linedown", "Move line down", *both("A+Down")),
    ("copyup", "Copy line up", *both("AS+Up", "MA+Up")),
    ("copydown", "Copy line down", *both("AS+Down", "MA+Down")),
    ("deleteline", "Delete line", *both("C+D", "M+D")),
    ("comment", "Comment lines", *both("CS+C", "MS+C")),
    ("reflow", "Reflow comment", *both("CS+/")),
    ("reindent", "Reindent lines", *both("C+I", "M+I")),
    ("reformat", "Reformat selection", *both("CS+A", "MS+A")),
    ("extractfn", "Extract function", *both("CA+X", "MA+X")),
    ("extractvar", "Extract variable", *both("CA+V", "MA+V")),
    ("rename", "Rename in scope", *both("CAS+M", "MAS+M")),
    ("roxygen", "Roxygen skeleton", *both("CAS+R", "MAS+R")),
    ("assign", "Insert <-", *both("A+-")),
    ("pipe", "Insert pipe", *both("CS+M", "MS+M")),
    ("pasteindent", "Paste with indent", *both("CS+V", "MS+V")),
    (None, "Undo", *both("C+Z", "M+Z")),
    (None, "Redo", *both("CS+Z", "MS+Z")),
    (None, "Cut", *both("C+X", "M+X")),
    (None, "Copy", *both("C+C", "M+C")),
    (None, "Paste", *both("C+V", "M+V")),
    (None, "Select all", *both("C+A", "M+A")),
    # --- find ---
    (None, "Find", *both("C+F", "M+F")),
    ("findnext", "Find next", None, "M+G"),
    ("findprev", "Find previous", None, "MS+G"),
    ("usesel", "Use selection for find", *both("C+F3", "M+E")),
    ("replacefind", "Replace and find", *both("CS+J", "MS+J")),
    ("findinfiles", "Find in files", *both("CS+F", "MS+F")),
    ("spell", "Check spelling", *both("+F7")),
    ("help", "Help for function", *both("+F1")),
    ("showsource", "Function source", *both("+F2")),
    # --- build ---
    ("installrestart", "Install and restart", *both("CS+B", "MS+B")),
    ("loadall", "Load all", *both("CS+L", "MS+L")),
    ("testpkg", "Test package", *both("CS+T", "MS+T")),
    ("checkpkg", "Check package", *both("CS+E", "MS+E")),
    ("docpkg", "Document package", *both("CS+D", "MS+D")),
    # --- debug ---
    ("breakpoint", "Toggle breakpoint", *both("S+F9")),
    ("stepover", "Next line", *both("+F10")),
    ("stepinto", "Step into", *both("S+F4")),
    ("stepout", "Finish function", *both("S+F7")),
    ("continue", "Continue", *both("S+F5")),
    ("stopdebug", "Stop debugging", *both("S+F8")),
    # --- plots, git ---
    ("prevplot", "Previous plot", *both("CA+F11", "MA+F11")),
    ("nextplot", "Next plot", *both("CA+F12", "MA+F12")),
    ("gitdiff", "Git diff", *both("CA+D")),
    ("gitcommit", "Git commit", *both("CA+M")),
]
# Ctrl+1..9 move the focus to a pane, Ctrl+Shift+1..9 zoom it (Control on a
# Mac too).
for n, pane in enumerate(PANES, start=1):
    ROWS.append((f"pane{n}", f"{pane} pane", *both(f"C+{n}")))
for n, pane in enumerate(PANES, start=1):
    ROWS.append((f"zoom{n}", f"Zoom {pane}", *both(f"CS+{n}")))

HEADER = """\
# RStudio shortcut overlays for PolyKybd (Windows, Linux and macOS).
# GENERATED by gen_specs.py from its table -- edit the table, not this file.
#
# Shortcuts: Posit, RStudio 2026.10.0 "Keyboard Shortcuts" reference. See
# SOURCES.md.
#
# Regenerate:
#   python polyhost/res/overlay_sources/rstudio/fetch_icons.py
#   python polyhost/res/overlay_sources/rstudio/gen_specs.py
#   python scripts/generate_app_overlays.py \\
#       polyhost/res/overlay_sources/rstudio/bindings.yaml --preview /tmp/rstudio_preview
app: rstudio
match: [rstudio]
output: rstudio_template
icon_dir: icons
fit: contain
anchor: bottom-right
region: [36, 32]
margin: 0
mode: luma
threshold: 150

program_icon: rstudio.png
program_icon_mode: alpha
program_icon_anchor: right
program_icon_region: [37, 32]
program_icon_margin: 0

bindings:
"""

# Labels that would fold onto a shared concept but mean something else here.
NOT_SHARED = {"Find next", "Find previous", "Find in files"}


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
