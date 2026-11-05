#!/usr/bin/env python3
"""Write the Todoist overlay specs: `todoist.yaml` (desktop app) and
`todoist_web.yaml` (todoist.com in a browser).

Each table row is (icon, label, Windows/Linux key, macOS key, where), read from
Todoist's help page "Use keyboard shortcuts in Todoist" (see SOURCES.md), whose
tables are split into Web, macOS and Windows. `where` is "all", "desktop" or
"web": the desktop app has keys the web page does not (window management, back
and forward, scrolling), and a few keys differ (zoom in). A key is written as
modifier letters and a key name joined by "+": C Ctrl, A Alt (Option on a Mac),
S Shift, M Cmd. None means the platform has no key. A row whose macOS key is
the Windows key with Ctrl replaced by Cmd becomes one `CMDCTRL` binding; any
other row is written twice, under `except: [macos]` and `only: [macos]`.

The Linux app has no table of its own; it gets the Windows keys.

    python polyhost/res/overlay_sources/todoist/gen_specs.py
    python polyhost/res/overlay_sources/todoist/fetch_icons.py
    python scripts/generate_app_overlays.py polyhost/res/overlay_sources/todoist/<spec>.yaml
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

MODS = {"C": "CTRL", "A": "ALT", "S": "SHIFT", "M": "GUI"}
KEYS = {",": "COMMA", ".": "DOT", "=": "EQUAL", "-": "MINUS", "/": "SLASH",
        "[": "LBRACKET", "]": "RBRACKET", "Enter": "ENTER", "Bksp": "BSPC",
        "Up": "UP", "Down": "DOWN", "Left": "LEFT", "Right": "RIGHT",
        "Home": "HOME", "End": "END", "Del": "DELETE", "F11": "F11"}

ROWS = [
    # --- general ---
    ("quickadd", "Quick Add", "Q", "Q", "all"),
    ("newproject", "New project", "A+P", "A+P", "all"),
    ("search", "Search", "/", "/", "all"),
    ("search", "Search", "F", "F", "all"),
    ("undo", "Undo", "C+Z", "M+Z", "all"),
    ("sidebar", "Toggle sidebar", "M", "M", "all"),
    ("shortcuts", "Keyboard shortcuts", "S+/", "S+/", "all"),
    ("quickfind", "Quick Find", "C+K", "M+K", "all"),
    ("print", "Print", "C+P", "M+P", "all"),
    ("zoomin", "Zoom in", "CS+=", "M+=", "desktop"),
    ("zoomin", "Zoom in", "C+=", "M+=", "web"),
    ("zoomout", "Zoom out", "C+-", "M+-", "all"),
    ("zoomreset", "Reset zoom", "C+0", "M+0", "web"),
    ("collapseall", "Collapse or expand all", "CA+0", "MA+0", "all"),
    # --- navigation ---
    ("home", "Home view", "H", "H", "all"),
    ("gotoproject", "Open task in its project", "S+G", "S+G", "all"),
    ("goto", "Go to (then I, T, U, P, L)", "G", "G", "all"),
    ("open", "Open (then S, T, N, H)", "O", "O", "all"),
    ("focusup", "Focus up", "K", "K", "all"),
    ("focusdown", "Focus down", "J", "J", "all"),
    ("back", "Back", "A+Left", "M+[", "desktop"),
    ("forward", "Forward", "A+Right", "M+]", "desktop"),
    # --- create tasks ---
    ("addbottom", "Add task at bottom", "A", "A", "all"),
    ("addtop", "Add task at top", "S+A", "S+A", "all"),
    ("saveedits", "Save and add task above", "C+Enter", "C+Enter", "all"),
    # --- manage tasks ---
    ("complete", "Complete task", "E", "E", "all"),
    ("edit", "Edit task", "C+E", "M+E", "all"),
    ("setdate", "Set date", "T", "T", "all"),
    ("removedate", "Remove date", "S+T", "S+T", "all"),
    ("priority", "Priority 1", "1", "1", "all"),
    ("priority", "Priority 2", "2", "2", "all"),
    ("priority", "Priority 3", "3", "3", "all"),
    ("priority", "Priority 4", "4", "4", "all"),
    ("changepriority", "Change priority", "Y", "Y", "all"),
    ("comment", "Comment", "C", "C", "all"),
    ("label", "Add label", "L", "L", "all"),
    ("assign", "Assign", "S+R", "S+R", "all"),
    ("moveto", "Move to", "V", "V", "all"),
    ("moreactions", "More task actions", ".", ".", "all"),
    ("select", "Select task", "X", "X", "all"),
    ("multiselect", "Multi-select toolbar", ",", ",", "all"),
    ("delete", "Delete task", "S+Del", "M+Bksp", "all"),
    ("copylink", "Copy link to task", "CS+C", "MS+C", "all"),
    ("taskabove", "Edit task above", "C+Up", "M+Up", "all"),
    ("taskbelow", "Edit task below", "C+Down", "M+Down", "all"),
    # --- sub-tasks (Control on macOS too) ---
    ("indent", "Indent", "C+]", "C+]", "all"),
    ("outdent", "Outdent", "C+[", "C+[", "all"),
    ("subtasks", "Show or hide sub-tasks", "S+E", "S+E", "all"),
    # --- projects ---
    ("layout", "Change layout", "S+V", "S+V", "all"),
    ("addsection", "Add section", "S", "S", "all"),
    ("share", "Share project", "S+S", "S+S", "all"),
    ("sortdate", "Sort by date", "D", "D", "all"),
    ("sortpriority", "Sort by priority", "P", "P", "all"),
    ("sortname", "Sort by name", "N", "N", "all"),
    ("sortassignee", "Sort by assignee", "R", "R", "all"),
    ("projectactions", "Project actions", "W", "W", "all"),
    ("insights", "Insights", "I", "I", "all"),
    ("scrolltop", "Scroll to top", "C+Home", None, "desktop"),
    ("scrollbottom", "Scroll to bottom", "C+End", None, "desktop"),
    # --- Upcoming view ---
    ("today", "Go to today", "Home", "AS+Y", "all"),
    ("prevweek", "Previous week", "S+Left", "S+Left", "all"),
    ("nextweek", "Next week", "S+Right", "S+Right", "all"),
    # --- windows (desktop app only) ---
    ("newwindow", "View in new window", "CS+N", "MS+N", "desktop"),
    ("newhomewindow", "New Home window", "CAS+N", "MAS+N", "desktop"),
    ("floattop", "Float window on top", "C+F11", "MA+F", "desktop"),
]

# Labels that fold onto a shared concept but mean something else here.
NOT_SHARED = {"Delete task", "Edit task", "Add label", "Move to"}

HEADER = """\
# Todoist ({flavour}) shortcut overlays for PolyKybd. See SOURCES.md.
# GENERATED by gen_specs.py from its table -- edit the table, not this file.
#
# Shortcuts: the Web, macOS and Windows tables of Todoist's help page
# https://www.todoist.com/help/articles/use-keyboard-shortcuts-in-todoist-Wyovn2
# The single-letter keys act when no text field has the focus.
#
# Regenerate:
#   python polyhost/res/overlay_sources/todoist/gen_specs.py
#   python polyhost/res/overlay_sources/todoist/fetch_icons.py
#   python scripts/generate_app_overlays.py \\
#       polyhost/res/overlay_sources/todoist/{spec} --preview /tmp/{output}_preview
app: {app}
match: [{app}]
output: {output}
icon_dir: icons
fit: contain
anchor: bottom-right
region: [40, 36]
margin: 0
mode: luma
threshold: 150

program_icon: todoist.png
program_icon_mode: alpha
program_icon_anchor: right
program_icon_region: [37, 32]
program_icon_margin: 0

bindings:
"""


def parse(chord: str) -> tuple[str, list[str]]:
    mods, key = chord.split("+", 1) if "+" in chord and len(chord) > 1 else ("", chord)
    key = KEYS.get(key, key)
    if key.isdigit():
        key = f'"{key}"'
    return key, [MODS[m] for m in mods]


def line(icon, label, chord, scope: str, cmdctrl: bool = False) -> str:
    key, mods = parse(chord)
    if cmdctrl:
        mods = ["CMDCTRL" if m == "CTRL" else m for m in mods]
    parts = [f"key: {key}"] + ([f"mods: [{', '.join(mods)}]"] if mods else [])
    parts.append(f"icon: {icon}.png")
    parts.append(f'label: "{label}"')
    if label in NOT_SHARED:
        parts.append("shared: false")
    if scope:
        parts.append(scope)
    return "  - { " + ", ".join(parts) + " }"


def ctrl_to_cmd(chord: str) -> str:
    mods, key = chord.split("+", 1)
    return "".join("M" if m == "C" else m for m in mods) + "+" + key


def render(flavour: str, **fmt) -> str:
    out = [HEADER.format(flavour=flavour, **fmt)]
    for icon, label, win, mac, where in ROWS:
        if where not in ("all", flavour):
            continue
        if win and win == mac and set(parse(win)[1]) <= {"SHIFT"}:
            out.append(line(icon, label, win, ""))
            continue
        if win and mac and "C" in win.split("+", 1)[0] and "+" in win and ctrl_to_cmd(win) == mac:
            out.append(line(icon, label, win, "", cmdctrl=True))
            continue
        if win:
            out.append(line(icon, label, win, "except: [macos]"))
        if mac:
            out.append(line(icon, label, mac, "only: [macos]"))
    return "\n".join(out) + "\n"


SPECS = {
    "todoist.yaml": ("desktop", dict(app="todoist", output="todoist_template")),
    "todoist_web.yaml": ("web", dict(app="todoist_web", output="todoist_web_template")),
}


def main() -> int:
    for name, (flavour, fmt) in SPECS.items():
        text = render(flavour, spec=name, **fmt)
        (HERE / name).write_text(text, encoding="utf-8")
        print(f"{name}: {text.count(chr(10) + '  - {')} bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
