#!/usr/bin/env python3
"""Write the Affinity overlay specs from one table.

Serif's help pages for Affinity Designer 2, Photo 2 and Publisher 2 list
mostly the same menu keys, but a few keys mean different things per app (Ctrl+L
is Lock in Designer and Publisher, Levels in Photo; Ctrl+I is Italic or
Invert). So each row names the apps it belongs to, and four specs are written:

    designer.yaml   Affinity Designer (1 and 2)      rows tagged d
    photo.yaml      Affinity Photo (1 and 2)         rows tagged p
    publisher.yaml  Affinity Publisher (1 and 2)     rows tagged u
    common.yaml     the unified Affinity app (2025)  rows tagged dpu

Each row: (icon, label, Windows, macOS, apps). A key is written as modifier
letters and a key name joined by "+": C Ctrl (Control on a Mac), A Alt
(Option), S Shift, M Cmd. Tool letters are left out: they differ per app and
per persona. See SOURCES.md.

    python polyhost/res/overlay_sources/affinity/gen_specs.py
    python scripts/generate_app_overlays.py polyhost/res/overlay_sources/affinity/<spec>.yaml
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

MODS = {"C": "CTRL", "A": "ALT", "S": "SHIFT", "M": "GUI"}
KEYS = {",": "COMMA", ".": "DOT", "=": "EQUAL", "-": "MINUS", "/": "SLASH",
        "[": "LBRACKET", "]": "RBRACKET", ";": "SEMICOLON", "'": "QUOTE",
        "\\": "BACKSLASH", "Enter": "ENTER", "Up": "UP", "PgUp": "PGUP",
        "PgDn": "PGDN"}

ALL = "dpu"

ROWS = [
    # --- file ---
    ("new", "New document", "C+N", "M+N", ALL),
    ("newclip", "New from clipboard", "CAS+N", "ASM+N", "dp"),
    ("open", "Open", "C+O", "M+O", ALL),
    (None, "Close", "C+W", "M+W", ALL),
    ("closeall", "Close all", "CA+W", "AM+W", ALL),
    (None, "Save", "C+S", "M+S", ALL),
    ("saveas", "Save as", "CS+S", "SM+S", ALL),
    ("export", "Export", "CAS+S", "ASM+S", ALL),
    ("docsetup", "Document setup", "CS+P", "SM+P", "du"),
    ("resizedoc", "Resize document", "CA+I", "AM+I", "p"),
    ("resizecanvas", "Resize canvas", "CA+C", "AM+C", "p"),
    (None, "Print", "C+P", "M+P", ALL),
    ("settings", "Settings", "C+,", "M+,", ALL),
    # --- edit ---
    (None, "Undo", "C+Z", "M+Z", ALL),
    (None, "Redo", "CS+Z", "SM+Z", ALL),
    (None, "Cut", "C+X", "M+X", ALL),
    (None, "Copy", "C+C", "M+C", ALL),
    (None, "Paste", "C+V", "M+V", ALL),
    (None, "Select all", "C+A", "M+A", ALL),
    ("deselect", "Deselect", "C+D", "M+D", ALL),
    ("pastestyle", "Paste style", "CS+V", "SM+V", ALL),
    ("pastefx", "Paste FX", "AS+V", "CM+V", ALL),
    ("pasteinside", "Paste inside", "CA+V", "AM+V", "dp"),
    ("pasteplain", "Paste without format", "CAS+V", "ASM+V", ALL),
    ("copymerged", "Copy merged", "CS+C", "SM+C", "p"),
    ("invertsel", "Invert pixel selection", "CS+I", "SM+I", "dp"),
    ("selectlayers", "Select all layers", "CA+A", "AM+A", "p"),
    ("selectnext", "Select next", "CA+]", "AM+]", "du"),
    ("selectprev", "Select previous", "CA+[", "AM+[", "du"),
    ("selectparent", "Select parent", "C+Up", "M+Up", "du"),
    # --- arrange and layers ---
    ("group", "Group", "C+G", "M+G", ALL),
    ("ungroup", "Ungroup", "CS+G", "SM+G", ALL),
    ("duplicate", "Duplicate", "C+J", "M+J", ALL),
    ("front", "Move to front", "CS+]", "SM+]", ALL),
    ("forward", "Move forward one", "C+]", "M+]", ALL),
    ("back", "Move to back", "CS+[", "SM+[", ALL),
    ("backward", "Move back one", "C+[", "M+[", ALL),
    ("moveinside", "Move inside", "CA+G", "AM+G", "d"),
    ("moveoutside", "Move outside", "CAS+G", "ASM+G", "d"),
    ("showall", "Show all", "CAS+H", "CM+H", ALL),
    ("lock", "Lock", "C+L", "M+L", "du"),
    ("unlock", "Unlock", "CS+L", "SM+L", ALL),
    ("unlockall", "Unlock all", "CAS+L", "CM+L", ALL),
    ("newlayer", "New pixel layer", "CS+N", "SM+N", "d"),
    ("newlayer", "New layer", "CS+N", "SM+N", "p"),
    ("rename", "Rename layer", "CS+R", "SM+R", ALL),
    ("curves", "Convert to curves", "C+Enter", "M+Enter", "dp"),
    ("symbol", "Create symbol", "CS+K", "SM+K", "d"),
    ("mergedown", "Merge down", "C+E", "M+E", "p"),
    ("mergesel", "Merge selected", "CS+E", "SM+E", "p"),
    ("mergevis", "Merge visible", "CAS+E", "ASM+E", "p"),
    # --- adjustments and filters ---
    ("adjcurves", "Curves", "C+M", "M+M", ALL),
    ("blackwhite", "Black and white", "CAS+B", "ASM+B", ALL),
    ("levels", "Levels", "C+L", "M+L", "p"),
    ("hsl", "HSL", "C+U", "M+U", "p"),
    ("invert", "Invert", "C+I", "M+I", "p"),
    ("repeatfilter", "Repeat filter", "C+F", "M+F", "p"),
    ("fade", "Fade", "CS+F", "SM+F", "p"),
    ("growshrink", "Grow / shrink", "C+B", "M+B", "p"),
    ("refine", "Refine edges", "CA+R", "AM+R", "p"),
    ("fill", "Fill", "S+F5", "S+F5", "p"),
    ("feather", "Feather", "S+F6", "S+F6", "p"),
    # --- text ---
    ("character", "Character panel", "C+T", "M+T", ALL),
    ("typography", "Typography panel", "CS+T", "SM+T", ALL),
    ("spelling", "Spelling options", "CS+;", "SM+;", ALL),
    (None, "Bold", "C+B", "M+B", "du"),
    (None, "Italic", "C+I", "M+I", "du"),
    (None, "Underline", "C+U", "M+U", "du"),
    ("superscript", "Superscript", "CS+=", "CM+=", ALL),
    ("subscript", "Subscript", "CA+-", "CM+-", ALL),
    ("bigger", "Bigger text", "CS+.", "SM+.", ALL),
    ("smaller", "Smaller text", "CS+,", "SM+,", ALL),
    ("alignleft", "Align left", "CA+L", "AM+L", "du"),
    ("aligncenter", "Align center", "CA+C", "AM+C", "du"),
    ("alignright", "Align right", "CA+R", "AM+R", "du"),
    # --- Publisher ---
    ("place", "Place image", "CS+M", "SM+M", "u"),
    ("addpage", "Add page", "CS+PgDn", "SM+PgDn", "u"),
    ("prevpage", "Previous page", "C+PgUp", "M+PgUp", "u"),
    ("nextpage", "Next page", "C+PgDn", "M+PgDn", "u"),
    ("detached", "Edit detached", "CS+D", "SM+D", "u"),
    ("find", "Find", "C+F", "M+F", "u"),
    ("previewmode", "Preview mode", "CS+W", "C+W", "u"),
    ("indenthere", "Indent to here", "C+\\", "M+\\", "u"),
    # --- view ---
    (None, "Zoom in", "C+=", "M+=", ALL),
    (None, "Zoom out", "C+-", "M+-", ALL),
    ("zoomfit", "Zoom to fit", "C+0", "M+0", ALL),
    ("zoom100", "Zoom 100%", "C+1", "M+1", ALL),
    ("zoom200", "Zoom 200%", "C+2", "M+2", ALL),
    ("pixelsize", "Pixel size", "C+9", "M+9", ALL),
    ("rulers", "Rulers", "C+R", "M+R", ALL),
    ("guides", "Guides", "C+;", "M+;", ALL),
    ("grid", "Grid", "C+'", "M+'", ALL),
    ("studio", "Show / hide studio", "CS+H", "SM+H", ALL),
    ("toolbar", "Show / hide toolbar", "CA+T", "AM+T", ALL),
    ("resetrotation", "Reset view rotation", "CAS+R", "CSM+R", ALL),
    ("pixelview", "Pixel view mode", "CA+Y", "AM+Y", "d"),
    ("wireframe", "Wireframe mode", "C+Y", "M+Y", "d"),
]

HEADER = """\
# Affinity {what} shortcut overlays for PolyKybd.
# GENERATED by gen_specs.py from its table -- edit the table, not this file.
#
# Shortcuts: Serif, Affinity help, "Keyboard shortcuts" for {pages}, the
# Windows and macOS keys. See SOURCES.md.
#
# Regenerate:
#   python polyhost/res/overlay_sources/affinity/gen_specs.py
#   python scripts/generate_app_overlays.py \\
#       polyhost/res/overlay_sources/affinity/{spec} --preview /tmp/affinity_preview
app: {app}
match: [{match}]
output: {output}
icon_dir: icons
fit: contain
anchor: bottom-right
region: [36, 32]
margin: 0
mode: luma
threshold: 150

program_icon: {mark}
program_icon_mode: alpha
program_icon_anchor: bottom-right
program_icon_region: [37, 32]
program_icon_margin: 0

bindings:
"""


def parse(chord: str) -> tuple[str, list[str]]:
    mods, key = chord.split("+", 1)
    key = KEYS.get(key, key)
    if key.isdigit():
        key = f'"{key}"'
    return key, [MODS[m] for m in mods]


def line(icon, label, chord, mac: bool) -> str:
    key, mods = parse(chord)
    parts = [f"key: {key}", f"mods: [{', '.join(mods)}]"]
    if icon:
        parts.append(f"icon: {icon}.png")
    parts.append(f'label: "{label}"')
    parts.append("only: [macos]" if mac else "except: [macos]")
    return "  - { " + ", ".join(parts) + " }"


def render(tag: str, **fmt) -> str:
    out = [HEADER.format(**fmt)]
    for icon, label, win, mac, apps in ROWS:
        if (tag == ALL and apps != ALL) or (tag != ALL and tag not in apps):
            continue
        out.append(line(icon, label, win, mac=False))
        out.append(line(icon, label, mac, mac=True))
    return "\n".join(out) + "\n"


def main() -> int:
    specs = {
        "designer.yaml": render("d", what="Designer", pages="Affinity Designer 2",
                                spec="designer.yaml", app="affinity-designer",
                                match="designer, affinity designer, affinity designer 2",
                                output="affinity_designer_template", mark="designer.png"),
        "photo.yaml": render("p", what="Photo", pages="Affinity Photo 2",
                             spec="photo.yaml", app="affinity-photo",
                             match="photo, affinity photo, affinity photo 2",
                             output="affinity_photo_template", mark="photo.png"),
        "publisher.yaml": render("u", what="Publisher", pages="Affinity Publisher 2",
                                 spec="publisher.yaml", app="affinity-publisher",
                                 match="publisher, affinity publisher, affinity publisher 2",
                                 output="affinity_publisher_template", mark="publisher.png"),
        "common.yaml": render(ALL, what="app (2025, the keys Designer, Photo and Publisher share)",
                              pages="Affinity Designer 2, Photo 2 and Publisher 2",
                              spec="common.yaml", app="affinity", match="affinity",
                              output="affinity_template", mark="affinity.png"),
    }
    for name, text in specs.items():
        (HERE / name).write_text(text, encoding="utf-8")
        print(f"{name}: {text.count(chr(10) + '  - {')} bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
