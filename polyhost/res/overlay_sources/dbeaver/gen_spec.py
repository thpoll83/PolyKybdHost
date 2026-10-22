#!/usr/bin/env python3
"""Write the DBeaver overlay spec (bindings.yaml) from one table.

DBeaver is an Eclipse application. Its own key bindings are in the
`plugin.xml` of each `org.jkiss.dbeaver.*` plugin; the Eclipse platform keys
(save, close, navigation) are in DBeaver's "Shortcuts" page. Eclipse writes
`M1` for Ctrl on Windows/Linux and Cmd on macOS (here `CMDCTRL`), and a literal
`CTRL` stays Control on macOS. See SOURCES.md.

Each row: (icon, label, chord, platforms). A chord is modifiers and a key joined
by "+", modifiers comma-separated. Platforms: "all", "wl" (Windows and Linux),
"mac", "win" (Windows only), "lm" (Linux and macOS).

    python polyhost/res/overlay_sources/dbeaver/gen_spec.py
    python scripts/generate_app_overlays.py polyhost/res/overlay_sources/dbeaver/bindings.yaml
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

ROWS = [
    # --- connections and scripts (plugin.xml) ---
    ("newconnection", "New connection", "CTRL,SHIFT+N", "all"),
    ("gotoobject", "Go to database object", "CTRL,SHIFT+D", "all"),
    ("newconsole", "New SQL console", "CTRL,ALT+ENTER", "all"),
    ("newscript", "New SQL script", "CTRL+RBRACKET", "all"),
    ("openscript", "Open SQL script", "CTRL+LBRACKET", "all"),
    ("openscript", "Open SQL script", "+F3", "all"),
    ("openobject", "Open object editor", "+F4", "all"),
    ("commit", "Commit", "CTRL,ALT,SHIFT+K", "win"),
    ("commit", "Commit", "CTRL+4", "lm"),
    ("rollback", "Rollback", "CTRL,ALT,SHIFT+R", "win"),
    ("rollback", "Rollback", "CTRL+8", "lm"),
    ("selectschema", "Select schema", "CTRL+0", "all"),
    ("selectconnection", "Select connection", "CTRL+9", "all"),
    ("syncconnection", "Connection from navigator", "CTRL,SHIFT+DOT", "all"),
    ("linkeditor", "Link with editor", "CTRL,SHIFT+COMMA", "all"),
    ("setdefault", "Set as default", "CTRL,SHIFT+A", "all"),
    ("tools", "Database tools", "ALT+GRAVE", "wl"),
    ("tools", "Database tools", "CTRL+V", "mac"),
    ("dashboard", "Dashboard", "CTRL,ALT,SHIFT+B", "all"),
    ("uuid", "Insert UUID", "CTRL,ALT,SHIFT+U", "all"),
    ("bookmark", "Add bookmark", "CTRL,ALT,SHIFT+D", "all"),
    ("aicomplete", "AI completion", "CTRL+I", "all"),
    # --- SQL editor (plugin.xml) ---
    ("runstatement", "Execute statement", "CMDCTRL+ENTER", "all"),
    ("runnewtab", "Execute in new tab", "CTRL+BACKSLASH", "all"),
    ("runscript", "Execute script", "ALT+X", "all"),
    ("runnative", "Execute script natively", "ALT+N", "all"),
    ("runfromhere", "Execute from cursor", "ALT+P", "all"),
    ("runtabs", "Execute in separate tabs", "CTRL,ALT,SHIFT+X", "all"),
    ("allrows", "Select all rows", "CTRL,ALT,SHIFT+A", "all"),
    ("expression", "Evaluate expression", "CTRL,ALT+QUOTE", "all"),
    ("explain", "Explain plan", "CTRL,SHIFT+E", "all"),
    ("format", "Format SQL", "CTRL,SHIFT+F", "all"),
    ("output", "Server output", "CTRL,SHIFT+O", "all"),
    ("results", "Results panel", "CTRL+T", "all"),
    ("maxresults", "Maximize results", "CTRL,SHIFT+T", "all"),
    ("switchpanel", "Switch panel", "ALT+T", "all"),
    ("closeresults", "Close results tab", "CTRL,SHIFT+BACKSLASH", "all"),
    ("pintab", "Pin results tab", "CTRL,SHIFT+P", "all"),
    ("loadfile", "Load SQL file", "CTRL,ALT,SHIFT+O", "all"),
    ("comment", "Line comment", "CTRL+SLASH", "all"),
    ("blockcomment", "Block comment", "CTRL,SHIFT+SLASH", "all"),
    ("wordwrap", "Word wrap", "CTRL,ALT,SHIFT+W", "all"),
    ("renamescript", "Rename script", "CTRL+F2", "all"),
    ("matchbracket", "Matching bracket", "CTRL,SHIFT+LBRACKET", "all"),
    ("selectbrackets", "Select to bracket", "CTRL,SHIFT+RBRACKET", "all"),
    ("nextquery", "Next query", "ALT+DOWN", "all"),
    ("prevquery", "Previous query", "ALT+UP", "all"),
    ("autocomplete", "Autocomplete", "CTRL+SPACE", "all"),
    # --- results (plugin.xml) ---
    ("reject", "Reject changes", "CTRL+R", "all"),
    ("fetchall", "Fetch all rows", "CTRL,SHIFT+EQUAL", "all"),
    ("fetchpage", "Fetch next page", "CTRL,ALT+N", "all"),
    ("frombelow", "Copy from row below", "CTRL,ALT+D", "all"),
    ("addrow", "Add row", "ALT+INSERT", "all"),
    ("addrowbefore", "Add row before", "ALT,SHIFT+INSERT", "all"),
    ("duplicaterow", "Duplicate row", "CTRL,ALT+INSERT", "all"),
    ("deleterow", "Delete row", "ALT+DELETE", "all"),
    ("setnull", "Set default value", "CTRL+BSPC", "all"),
    ("presentation", "Switch presentation", "CTRL+GRAVE", "all"),
    ("references", "References", "CTRL,SHIFT+1", "all"),
    ("sort", "Sort order", "CTRL+2", "all"),
    ("panels", "Result panels", "CTRL+7", "all"),
    ("panels", "Result panels", "+F7", "all"),
    ("focuspanel", "Focus result panel", "CTRL,SHIFT+7", "all"),
    ("focusfilter", "Focus filter", "CTRL,ALT,SHIFT+T", "all"),
    ("gotorow", "Go to row", "CTRL+G", "all"),
    ("gotocolumn", "Go to column", "CTRL,SHIFT+G", "all"),
    ("selectcolumn", "Select column", "CTRL,ALT+C", "all"),
    ("selectrow", "Select row", "CTRL,ALT+R", "all"),
    ("firstrow", "First row", "CTRL,ALT,SHIFT+LEFT", "all"),
    ("lastrow", "Last row", "CTRL,ALT,SHIFT+RIGHT", "all"),
    ("prevrow", "Previous row", "CTRL,ALT+LEFT", "all"),
    ("nextrow", "Next row", "CTRL,ALT+RIGHT", "all"),
    ("followlink", "Follow foreign key", "ALT+SPACE", "all"),
    ("distinct", "Distinct values", "CTRL+F11", "all"),
    ("filtermenu", "Filter menu", "+F11", "all"),
    ("fontup", "Larger grid font", "ALT+0", "all"),
    ("fontdown", "Smaller grid font", "ALT+9", "all"),
    ("advcopy", "Advanced copy", "CTRL,SHIFT+C", "all"),
    ("advcopylast", "Copy with last settings", "CTRL,ALT,SHIFT+C", "all"),
    ("advpaste", "Advanced paste", "CTRL,SHIFT+V", "all"),
    # --- Eclipse platform (DBeaver's Shortcuts page) ---
    (None, "Save", "CMDCTRL+S", "all"),
    ("saveall", "Save all", "CMDCTRL,SHIFT+S", "all"),
    (None, "Close", "CTRL+F4", "wl"),
    (None, "Close", "GUI+W", "mac"),
    ("closeall", "Close all", "CTRL,SHIFT+F4", "wl"),
    ("closeall", "Close all", "GUI,SHIFT+W", "mac"),
    (None, "New", "CMDCTRL+N", "all"),
    (None, "Find", "CMDCTRL+F", "all"),
    ("rename", "Rename", "+F2", "all"),
    ("refresh", "Refresh", "+F5", "all"),
    ("properties", "Properties", "ALT+ENTER", "wl"),
    ("properties", "Properties", "GUI+I", "mac"),
    ("findactions", "Find actions", "CMDCTRL+3", "all"),
    ("shortcuts", "Keyboard shortcuts", "CMDCTRL,SHIFT+L", "all"),
    ("search", "Search", "CTRL+H", "all"),
    ("openitem", "Open item", "CMDCTRL,SHIFT+R", "all"),
    ("maximize", "Maximize view", "CTRL+M", "all"),
    ("nexteditor", "Next editor", "CMDCTRL+F6", "all"),
    ("preveditor", "Previous editor", "CMDCTRL,SHIFT+F6", "all"),
    ("nexttab", "Next tab", "CTRL+PGDN", "all"),
    ("prevtab", "Previous tab", "CTRL+PGUP", "all"),
    ("back", "Back", "ALT+LEFT", "wl"),
    ("back", "Back", "GUI+LBRACKET", "mac"),
    ("forward", "Forward", "ALT+RIGHT", "wl"),
    ("forward", "Forward", "GUI+RBRACKET", "mac"),
    ("fullscreen", "Full screen", "ALT+F11", "wl"),
    ("fullscreen", "Full screen", "CTRL,GUI+F", "mac"),
]

PLATFORMS = {"all": "", "wl": "except: [macos]", "mac": "only: [macos]",
             "win": "only: [windows]", "lm": "except: [windows]"}

HEADER = """\
# DBeaver shortcut overlays for PolyKybd (Windows, Linux and macOS).
# GENERATED by gen_spec.py from its table -- edit the table, not this file.
# See SOURCES.md.
#
# Regenerate:
#   python polyhost/res/overlay_sources/dbeaver/fetch_icons.py
#   python polyhost/res/overlay_sources/dbeaver/gen_spec.py
#   python scripts/generate_app_overlays.py \\
#       polyhost/res/overlay_sources/dbeaver/bindings.yaml --preview /tmp/dbeaver_preview
app: dbeaver
match: [dbeaver]
output: dbeaver_template
icon_dir: icons
fit: contain
anchor: bottom-right
region: [36, 32]
margin: 0
mode: luma
threshold: 150

program_icon: dbeaver.png
program_icon_mode: alpha
program_icon_anchor: right
program_icon_region: [37, 32]
program_icon_margin: 0

bindings:
"""


def line(icon, label, chord, plat) -> str:
    mods, key = chord.rsplit("+", 1)
    if key.isdigit():
        key = f'"{key}"'
    mods = [m for m in mods.split(",") if m]
    parts = [f"key: {key}", f"mods: [{', '.join(mods)}]"]
    if icon:
        parts.append(f"icon: {icon}.png")
    parts.append(f'label: "{label}"')
    if PLATFORMS[plat]:
        parts.append(PLATFORMS[plat])
    return "  - { " + ", ".join(parts) + " }"


def main() -> int:
    text = HEADER + "\n".join(line(*r) for r in ROWS) + "\n"
    (HERE / "bindings.yaml").write_text(text, encoding="utf-8")
    print(f"bindings.yaml: {len(ROWS)} bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
