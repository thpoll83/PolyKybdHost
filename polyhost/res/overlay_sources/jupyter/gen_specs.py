#!/usr/bin/env python3
"""Write the JupyterLab overlay spec from one table.

The keys are JupyterLab 4.5.11's defaults, read from the `jupyter.lab.shortcuts`
entries of `packages/*/schema/*.json` (tag v4.5.11). In those files `Accel` is
Ctrl on Windows/Linux and Cmd on macOS; `Ctrl` stays Control on macOS. Jupyter
Notebook 7 is built from the same packages and has the same keys.

Each row: (icon, label, Windows/Linux key, macOS key). A key is written as
modifier letters and a key name joined by "+": C Ctrl, A Alt (Option on a
Mac), S Shift, M Cmd. None means no key on that platform. See SOURCES.md for
the keys left out.

    python polyhost/res/overlay_sources/jupyter/gen_specs.py
    python scripts/generate_app_overlays.py polyhost/res/overlay_sources/jupyter/bindings.yaml
    for m in command edit editor console global; do
        python scripts/generate_app_overlays.py polyhost/res/overlay_sources/jupyter/bindings_$m.yaml
    done

`bindings.yaml` has every row: it is the set shown while no mode is known (no
extension, or a remote server). The `bindings_<mode>.yaml` sets have only the
rows whose schema selector matches in that mode (SCOPES below); the
jupyterlab-extension/ reporter selects them through a `jupyter://` URL.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

MODS = {"C": "CTRL", "A": "ALT", "S": "SHIFT", "M": "GUI"}
KEYS = {"Enter": "ENTER", "Bksp": "BACKSPACE", "Up": "UP", "Down": "DOWN",
        "Left": "LEFT", "Right": "RIGHT", ",": "COMMA", ".": "DOT", "/": "SLASH",
        "-": "MINUS", "[": "LBRACKET", "]": "RBRACKET", "'": "QUOTE"}


def both(win, mac=None):
    """A row's Windows/Linux and macOS keys; `Accel` rows pass C+ and M+."""
    return win, (win if mac is None else mac)


ROWS = [
    # --- notebook: run and edit cells ---
    ("run", "Run cell", *both("C+Enter", "M+Enter")),
    ("runnext", "Run, select next", *both("S+Enter")),
    ("runinsert", "Run, insert below", *both("A+Enter")),
    ("cmdmode", "Command mode", *both("C+M")),
    ("splitcell", "Split cell", *both("CS+-")),
    ("mergebelow", "Merge with cell below", *both("CS+M")),
    ("mergeabove", "Merge with cell above", *both("C+Bksp")),
    ("moveup", "Move cell up", *both("CS+Up")),
    ("movedown", "Move cell down", *both("CS+Down")),
    ("collapseall", "Collapse all headings", *both("CS+Left")),
    ("expandall", "Expand all headings", *both("CS+Right")),
    ("histprev", "Previous history entry", *both("A+Up")),
    ("histnext", "Next history entry", *both("A+Down")),
    # --- code editor ---
    ("comment", "Toggle comment", *both("C+/", "M+/")),
    ("blockcomment", "Block comment", *both("A+A")),
    ("deleteline", "Delete line", *both("C+D", "M+D")),
    ("selectnext", "Select next occurrence", *both("CS+D", "MS+D")),
    # --- files, search ---
    (None, "Save", *both("C+S", "M+S")),
    ("saveas", "Save as", *both("CS+S", "MS+S")),
    (None, "Print", *both("C+P", "M+P")),
    (None, "Find", *both("C+F", "M+F")),
    ("findnext", "Find next", *both("C+G", "M+G")),
    ("findprev", "Find previous", *both("CS+G", "MS+G")),
    ("findsel", "Search in selection", *both("A+L")),
    (None, "Undo", *both("C+Z", "M+Z")),
    (None, "Redo", *both("CS+Z", "MS+Z")),
    (None, "Select all", *both("C+A", "M+A")),
    # --- panels and tools ---
    ("palette", "Command palette", *both("CS+C", "MS+C")),
    ("shortcuts", "Keyboard shortcuts", *both("CS+H", "MS+H")),
    ("leftarea", "Left sidebar", *both("C+B", "M+B")),
    ("rightarea", "Right sidebar", *both("C+J", "M+J")),
    ("filebrowser", "File browser", *both("CS+F", "MS+F")),
    ("toc", "Table of contents", *both("CS+K", "MS+K")),
    ("running", "Running sessions", *both("CS+B", "MS+B")),
    ("launcher", "Launcher", *both("CS+L", "MS+L")),
    ("extensions", "Extension manager", *both("CS+X", "MS+X")),
    ("debugger", "Debugger panel", *both("CS+E", "MS+E")),
    ("propinsp", "Property inspector", *both("CS+U", "MS+U")),
    ("inspector", "Contextual help", *both("C+I", "M+I")),
    ("settings", "Settings", *both("C+,", "M+,")),
    # --- tabs ---
    ("nexttab", "Next tab", *both("CS+]")),
    ("prevtab", "Previous tab", *both("CS+[")),
    ("nexttabbar", "Next tab bar", *both("CS+.")),
    ("prevtabbar", "Previous tab bar", *both("CS+,")),
    ("lasttab", "Previously used tab", *both("CS+'", "MS+'")),
    ("closetab", "Close tab", *both("A+W")),
    # --- debugger (while stopped) ---
    ("continue", "Continue", *both("+F9")),
    ("terminate", "Terminate", *both("S+F9")),
    ("stepover", "Next line", *both("+F10")),
    ("stepout", "Step out", *both("S+F11")),
    # --- notebook command mode (no cell being edited; Esc enters it) ---
    ("insertabove", "Insert cell above", *both("+A")),
    ("insertbelow", "Insert cell below", *both("+B")),
    ("headingabove", "Insert heading above", *both("S+A")),
    ("headingbelow", "Insert heading below", *both("S+B")),
    ("cutcell", "Cut cells", *both("+X")),
    ("copycell", "Copy cells", *both("+C")),
    ("pastecell", "Paste cells below", *both("+V")),
    ("undocell", "Undo cell action", *both("+Z")),
    ("redocell", "Redo cell action", *both("S+Z")),
    ("tocode", "Change to code", *both("+Y")),
    ("tomarkdown", "Change to Markdown", *both("+M")),
    ("toraw", "Change to raw", *both("+R")),
    ("mergecells", "Merge selected cells", *both("S+M")),
    ("cellbelow", "Select cell below", *both("+J")),
    ("cellabove", "Select cell above", *both("+K")),
    ("extendbelow", "Extend selection below", *both("S+J")),
    ("extendabove", "Extend selection above", *both("S+K")),
    ("linenumbers", "Toggle line numbers", *both("S+L")),
    ("sidebyside", "Render side by side", *both("S+R")),
]
# 1..6 turn the active cell into a Markdown heading of that level.
for n in range(1, 7):
    ROWS.append((f"heading{n}", f"Heading {n}", *both(f"+{n}")))
# Alt+1..9 open the left sidebar's panels by rank, Alt+Shift+1..9 the right's.
for n in range(1, 10):
    ROWS.append((f"left{n}", f"Left panel {n}", *both(f"A+{n}")))
for n in range(1, 10):
    ROWS.append((f"right{n}", f"Right panel {n}", *both(f"AS+{n}")))

# Where each row acts, from the `selector` of its `jupyter.lab.shortcuts` entry:
#   global  body (any activity)
#   file    body, but only a document can be saved or printed
#   search  .jp-mod-searchable / .jp-mod-search-active (notebook, file editor)
#   text    [data-jp-undoer] and the editor's own Select all
#   nb      the notebook in either mode (run cell)
#   cmd     .jp-Notebook.jp-mod-commandMode
#   edit    .jp-Notebook.jp-mod-editMode
#   cm      .cm-content (any code editor: a cell being edited, file, console)
SCOPE = {
    "Run cell": "nb", "Run, select next": "nb", "Run, insert below": "nb",
    "Command mode": "edit", "Split cell": "edit",
    "Previous history entry": "edit", "Next history entry": "edit",
    "Merge with cell below": "cmd", "Merge with cell above": "cmd",
    "Move cell up": "cmd", "Move cell down": "cmd",
    "Collapse all headings": "cmd", "Expand all headings": "cmd",
    "Toggle comment": "cm", "Block comment": "cm", "Delete line": "cm",
    "Select next occurrence": "cm",
    "Save": "file", "Save as": "file", "Print": "file",
    "Find": "search", "Find next": "search", "Find previous": "search",
    "Search in selection": "search",
    "Undo": "text", "Redo": "text", "Select all": "text",
}
# Rows from "Insert cell above" on are command-mode single keys (and the
# 1..6 headings), except the side panels; the rest of the table not named
# above (panels, tabs, debugger) is global.
_FIRST_SINGLE = next(i for i, r in enumerate(ROWS) if r[1] == "Insert cell above")


def scope(index: int, label: str) -> str:
    if label in SCOPE:
        return SCOPE[label]
    if label.startswith(("Left panel", "Right panel")):   # Alt(+Shift)+1..9, body
        return "global"
    if index >= _FIRST_SINGLE:
        return "cmd"
    return "global"


# Console prompt cell: Shift+Enter runs the input (console:run-forced, both
# interaction modes). Only in the console set: elsewhere Shift+Enter is
# "Run, select next".
CONSOLE_ROWS = [("run", "Run code", *both("S+Enter"))]

# One set per jupyter:// URL that changes the keys. Terminal and "other" (the
# launcher, a side panel) share `global`.
MODES = {
    "command": ({"global", "file", "search", "text", "nb", "cmd"}, []),
    "edit": ({"global", "file", "search", "text", "nb", "edit", "cm"}, []),
    "editor": ({"global", "file", "search", "text", "cm"}, []),
    "console": ({"global", "text", "cm"}, CONSOLE_ROWS),
    "global": ({"global"}, []),
}

HEADER = """\
# JupyterLab (and Jupyter Notebook 7) shortcut overlays for PolyKybd.
# GENERATED by gen_specs.py from its table -- edit the table, not this file.
#
# Shortcuts: JupyterLab 4.5.11 default key bindings (schema files). Jupyter
# runs in a browser, so the set loads through the browser entries' URL and
# title maps; the JupyterLab Desktop app loads it by its own name. See
# SOURCES.md.
#
# Regenerate:
#   python polyhost/res/overlay_sources/jupyter/fetch_icons.py
#   python polyhost/res/overlay_sources/jupyter/gen_specs.py
#   python scripts/generate_app_overlays.py \\
#       polyhost/res/overlay_sources/jupyter/bindings.yaml --preview /tmp/jupyter_preview
app: jupyter
match: [jupyterlab]
output: jupyter_template
icon_dir: icons
fit: contain
anchor: bottom-right
region: [36, 32]
margin: 0
mode: auto     # one rule per icon file: see HOUSE_LUMA_THRESHOLD in scripts/generate_app_overlays.py
threshold: 150

program_icon: jupyter.png
program_icon_mode: alpha
program_icon_anchor: right
program_icon_region: [37, 32]
program_icon_margin: 0

bindings:
"""

# Labels that would fold onto a shared concept but mean something else here.
NOT_SHARED = {"Find next", "Find previous"}


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


def write(name: str, header: str, rows) -> None:
    out = [header]
    for icon, label, win, mac in rows:
        if win:
            out.append(line(icon, label, win, mac=False))
        if mac:
            out.append(line(icon, label, mac, mac=True))
    text = "\n".join(out) + "\n"
    (HERE / name).write_text(text, encoding="utf-8")
    print(f"{name}: {text.count(chr(10) + '  - {')} bindings")


def main() -> int:
    write("bindings.yaml", HEADER, ROWS)
    for mode, (scopes, extra) in MODES.items():
        rows = [r for i, r in enumerate(ROWS) if scope(i, r[1]) in scopes] + extra
        header = (HEADER
                  .replace("output: jupyter_template",
                           f"output: jupyter_{mode}_template")
                  .replace("shortcut overlays for PolyKybd.",
                           f"shortcut overlays for PolyKybd: the `{mode}` mode set\n"
                           f"# (jupyterlab-extension/ reports it; see SOURCES.md)."))
        write(f"bindings_{mode}.yaml", header, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
