#!/usr/bin/env python3
"""Write the three Audacity overlay specs from one table.

Audacity 3.7.9 and 4.0.1 have different keymaps. On Windows they are different
programs (`Audacity.exe`, `Audacity4.exe`); on macOS both are "Audacity", and on
Linux the 4.x binary name is unconfirmed. So:

    audacity3.yaml   3.7.9 keys, Windows only   (`audacity`)
    audacity4.yaml   4.0.1 keys, Windows only   (`audacity4`)
    audacity.yaml    keys that do the same thing in both versions, written with
                     CMDCTRL so the generator also writes the macOS set; macOS and
                     Linux load it

Each row: (key, mods, icon, label, versions). `versions` is "34" for a key both
versions bind to the same action, "3" or "4" for one version. Mods use CTRL;
audacity.yaml turns CTRL into CMDCTRL (Audacity maps Ctrl to Cmd on macOS).
See SOURCES.md for where every row comes from.

    python polyhost/res/overlay_sources/audacity/gen_specs.py
    python scripts/generate_app_overlays.py polyhost/res/overlay_sources/audacity/<spec>.yaml
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

C, A, S = "CTRL", "ALT", "SHIFT"

ROWS = [
    # --- file ---
    ("N", [C], None, "New", "34"),
    ("O", [C], None, "Open", "34"),
    ("S", [C], None, "Save", "34"),
    ("W", [C], "close", "Close project", "34"),
    ("E", [C, S], "export", "Export audio", "34"),
    ("I", [C, S], "import", "Import audio", "34"),
    ("P", [C], "prefs", "Preferences", "3"),
    # --- edit ---
    ("Z", [C], None, "Undo", "34"),
    ("Z", [C, S], None, "Redo", "4"),      # 3.7.9: Ctrl+Y on Windows, see REDO
    ("X", [C], None, "Cut", "34"),
    ("C", [C], None, "Copy", "34"),
    ("V", [C], None, "Paste", "34"),
    ("DEL", [], None, "Delete", "34"),
    ("BSPC", [], None, "Delete", "34"),
    ("D", [C], "duplicate", "Duplicate", "34"),
    ("L", [C], "silence", "Silence audio", "34"),
    ("I", [C], "split", "Split", "34"),
    ("J", [C], "join", "Join clips", "34"),
    ("P", [C, S], "pitchspeed", "Pitch and speed", "34"),
    ("B", [C], "label", "Add label", "34"),
    ("K", [C], "deleteclip", "Delete selection", "3"),
    ("X", [C, A], "cutgap", "Cut and leave gap", "3"),
    ("K", [C, A], "deletegap", "Delete and leave gap", "3"),
    ("T", [C], "trim", "Trim audio", "3"),
    ("F2", [C], "rename", "Rename clip", "3"),
    ("UP", [A], "pitchup", "Pitch up", "3"),
    ("DOWN", [A], "pitchdown", "Pitch down", "3"),
    ("M", [C], "playlabel", "Label at playback", "3"),
    ("V", [C, A], "pasteoverlap", "Paste overlapping", "4"),
    ("V", [S], "pasteinsert", "Paste and insert", "4"),
    ("V", [C, A, S], "pasteall", "Paste insert, all tracks", "4"),
    ("X", [C, S], "cutclose", "Cut and close gap", "4"),
    ("DEL", [S], "deleteclose", "Delete and close gap", "4"),
    ("DEL", [C], "deleteall", "Delete, close gap all tracks", "4"),
    ("J", [C, A], "splitsilence", "Split at silences", "4"),
    ("G", [C], "groupclips", "Group clips", "4"),
    ("G", [C, S], "ungroupclips", "Ungroup clips", "4"),
    ("F2", [], "rename", "Rename clip/label", "4"),
    ("S", [], "splittool", "Split tool", "4"),
    # --- select ---
    ("A", [C], None, "Select all", "34"),
    ("K", [C, S], "selalltracks", "Select in all tracks", "34"),
    ("LBRACKET", [], "selleft", "Selection start at playhead", "34"),
    ("RBRACKET", [], "selright", "Selection end at playhead", "34"),
    ("J", [S], "seltostart", "Select track start to cursor", "34"),
    ("K", [S], "seltoend", "Select cursor to track end", "34"),
    ("Z", [], "zerocross", "Zero crossings", "34"),
    ("LEFT", [S], "extendleft", "Extend selection left", "34"),
    ("RIGHT", [S], "extendright", "Extend selection right", "34"),
    ("RIGHT", [C, S], "shrinkleft", "Shrink selection from left", "34"),
    ("LEFT", [C, S], "shrinkright", "Shrink selection from right", "34"),
    ("Y", [C, S], "selsync", "Select sync-locked tracks", "3"),
    ("Q", [], "spectral", "Spectral selection", "3"),
    ("COMMA", [A], "prevclip", "Previous clip", "3"),
    ("DOT", [A], "nextclip", "Next clip", "3"),
    ("HOME", [S], "selhome", "Selection to start", "3"),
    ("END", [S], "selend", "Selection to end", "3"),
    # --- view ---
    ("Z", [S], "zoomtoggle", "Zoom toggle", "34"),
    ("F", [C], "fitwidth", "Fit to width", "34"),
    ("1", [C], "zoomin", "Zoom in", "3"),
    ("2", [C], "zoomnormal", "Zoom normal", "3"),
    ("3", [C], "zoomout", "Zoom out", "3"),
    ("E", [C], "zoomsel", "Zoom to selection", "3"),
    ("F", [C, S], "fitheight", "Fit to height", "3"),
    ("C", [C, S], "collapse", "Collapse all tracks", "3"),
    ("X", [C, S], "expand", "Expand tracks", "3"),
    ("F11", [], "fullscreen", "Full screen", "3"),
    ("EQUAL", [C], "zoomin", "Zoom in", "4"),
    ("MINUS", [C], "zoomout", "Zoom out", "4"),
    # --- transport ---
    ("SPACE", [], "playstop", "Play/stop", "34"),
    ("P", [], "pause", "Pause", "34"),
    ("R", [], "record", "Record", "34"),
    ("D", [S], "punch", "Punch and roll record", "34"),
    ("HOME", [], "projstart", "Go to start", "34"),
    ("END", [], "projend", "Go to end", "34"),
    ("L", [], "loop", "Looping on/off", "34"),
    ("L", [A, S], "clearloop", "Clear loop", "34"),
    ("L", [S], "loopsel", "Loop to selection", "34"),
    ("X", [], "playcursor", "Play/stop, set cursor", "3"),
    ("SPACE", [S], "playonce", "Play once", "3"),
    ("R", [S], "recordnew", "Record new track", "3"),
    ("T", [S], "timer", "Timer record", "3"),
    ("J", [], "trackstart", "Cursor to track start", "3"),
    ("K", [], "trackend", "Cursor to track end", "3"),
    ("B", [], "playtosel", "Play to selection", "3"),
    ("C", [], "cutpreview", "Play cut preview", "3"),
    ("U", [], "scrubback", "Scrub backwards (hold)", "3"),
    ("I", [], "scrubfwd", "Scrub forwards (hold)", "3"),
    ("COMMA", [], "jumpleft", "Cursor short jump left", "3"),
    ("DOT", [], "jumpright", "Cursor short jump right", "3"),
    ("COMMA", [S], "longleft", "Cursor long jump left", "3"),
    ("DOT", [S], "longright", "Cursor long jump right", "3"),
    ("LEFT", [A], "prevlabel", "Previous label", "3"),
    ("RIGHT", [A], "nextlabel", "Next label", "3"),
    ("SPACE", [S], "playcursor", "Play from cursor", "4"),
    ("W", [], "playsel", "Play selection", "4"),
    ("I", [], "loopinout", "Loop in/out", "4"),
    # --- tracks ---
    ("U", [C], "muteall", "Mute all tracks", "3"),
    ("U", [C, S], "unmuteall", "Unmute all tracks", "3"),
    ("U", [C, A], "mutesel", "Mute tracks", "3"),
    ("U", [C, A, S], "unmutesel", "Unmute tracks", "3"),
    ("F6", [C], "focusnext", "Focus tracks", "3"),
    ("F6", [C, S], "focusprev", "Focus tracks (back)", "3"),
    ("G", [S], "trackgain", "Track gain", "3"),
    ("M", [S], "trackmenu", "Track menu", "3"),
    ("U", [S], "trackmute", "Mute/unmute track", "3"),
    ("S", [S], "tracksolo", "Solo/unsolo track", "3"),
    ("ENTER", [], "togglefocus", "Toggle focused track", "3"),
    ("N", [C, S], "newtrack", "New mono track", "4"),
    # --- effects and tools ---
    ("E", [], "effects", "Add realtime effects", "34"),
    ("R", [C], "repeateffect", "Repeat last effect", "34"),
    ("F1", [], "seltool", "Selection tool", "3"),
    ("F2", [], "envtool", "Envelope tool", "3"),
    ("F3", [], "drawtool", "Draw tool", "3"),
    ("F6", [], "multitool", "Multi tool", "3"),
]

# 3.7.9 binds Redo to Ctrl+Y on Windows (`#ifdef __WXMSW__`), Ctrl+Shift+Z
# elsewhere; 4.0.1 uses Ctrl+Shift+Z everywhere.
REDO_3_WINDOWS = ("Y", [C], None, "Redo", "3")
REDO_SHARED = ("Z", [C, S], None, "Redo", "34")

HEADER = """\
# {title}
#
# GENERATED by gen_specs.py from one table; edit the table, not this file.
# {note}
#
# Regenerate:
#   python polyhost/res/overlay_sources/audacity/gen_specs.py
#   python polyhost/res/overlay_sources/audacity/fetch_icons.py
#   python scripts/generate_app_overlays.py \\
#       polyhost/res/overlay_sources/audacity/{name}.yaml --preview /tmp/{name}_preview
app: {name}
match: [{match}]
output: {name}_template
icon_dir: icons
fit: contain
anchor: bottom-right
region: [36, 32]
margin: 0
mode: luma
threshold: 150

bindings:
"""

SPECS = {
    "audacity3": ("Audacity 3.7.9 shortcut overlay for PolyKybd (Windows, Audacity.exe).",
                  "The 3.7.9 Standard key set, the set a new install has.",
                  "audacity", lambda v: "3" in v, False),
    "audacity4": ("Audacity 4.0.1 shortcut overlay for PolyKybd (Windows, Audacity4.exe).",
                  "Only keys whose action 4.0.1 registers and handles.",
                  "audacity4", lambda v: "4" in v, False),
    "audacity": ("Audacity shortcut overlays for PolyKybd (macOS and Linux).",
                 "Both 3.7.9 and 4.0.1 run as \"Audacity\" there, so only the keys that "
                 "do the same in both.",
                 "audacity", lambda v: v == "34", True),
}


def _row(key, mods, icon, label, cmdctrl):
    if cmdctrl:
        mods = ["CMDCTRL" if m == C else m for m in mods]
    k = f'"{key}"' if key.isdigit() else key
    ic = f" icon: {icon}.png," if icon else ""
    return f'  - {{ key: {k}, mods: [{", ".join(mods)}],{ic} label: "{label}" }}'


def main() -> int:
    for name, (title, note, match, keep, cmdctrl) in SPECS.items():
        rows = [r for r in ROWS if keep(r[4])]
        if name == "audacity3":
            rows.append(REDO_3_WINDOWS)
        elif name == "audacity":
            rows.append(REDO_SHARED)
        seen = {}
        for r in rows:
            k = (r[0], tuple(sorted(r[1])))
            if k in seen:
                raise SystemExit(f"{name}: {r[0]}+{r[1]} is both {seen[k]!r} and {r[3]!r}")
            seen[k] = r[3]
        text = HEADER.format(title=title, note=note, name=name, match=match)
        text += "\n".join(_row(*r[:4], cmdctrl) for r in rows) + "\n"
        (HERE / f"{name}.yaml").write_text(text, encoding="utf-8")
        print(f"{name}.yaml: {len(rows)} bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
