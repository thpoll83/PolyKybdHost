#!/usr/bin/env python3
"""Write the VLC media player overlay spec from one table.

The keys are VLC 3.0.x's defaults, read from its source (see SOURCES.md):
the Qt menus (`modules/gui/qt/menus.cpp`) and the hotkey table
(`src/libvlc-module.c`) on Windows and Linux; the Cocoa main menu
(`modules/gui/macosx/UI/MainMenu.xib`, with the keys `VLCMainMenu.m` copies from
the hotkey table at start) and the hotkey table on macOS.

Each row: (icon, label, Windows/Linux, macOS). A key is written as modifier
letters and a key name joined by "+": C Ctrl, A Alt (Option on a Mac), S Shift,
M Cmd. None means the platform has no key.

    python polyhost/res/overlay_sources/vlc/gen_specs.py
    python scripts/generate_app_overlays.py polyhost/res/overlay_sources/vlc/bindings.yaml
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

MODS = {"C": "CTRL", "A": "ALT", "S": "SHIFT", "M": "GUI"}
KEYS = {",": "COMMA", ".": "DOT", "=": "EQUAL", "-": "MINUS", "/": "SLASH",
        "Up": "UP", "Down": "DOWN", "Left": "LEFT", "Right": "RIGHT"}

ROWS = [
    # --- media and files ---
    ("openfile", "Open file", "C+O", "M+O"),
    ("openmulti", "Open multiple files", "CS+O", None),
    ("openadvanced", "Advanced open", None, "SM+O"),
    ("openfolder", "Open folder", "C+F", None),
    ("opendisc", "Open disc", "C+D", "M+D"),
    ("opennetwork", "Open network stream", "C+N", "M+N"),
    ("opencapture", "Open capture device", "C+C", None),
    ("openclipboard", "Open location from clipboard", "C+V", None),
    ("saveplaylist", "Save playlist", "C+Y", "M+S"),
    ("convert", "Convert / save", "C+R", "SM+S"),
    ("stream", "Stream", "C+S", None),
    ("reveal", "Reveal in Finder", None, "SM+R"),
    (None, "Quit", "C+Q", None),
    # --- playback ---
    ("playpause", "Play / pause", None, "M+P"),
    ("stop", "Stop", None, "M+."),
    ("previous", "Previous", None, "M+Left"),
    ("next", "Next", None, "M+Right"),
    ("record", "Record", None, "AM+R"),
    ("jumptime", "Jump to time", "C+T", "M+J"),
    ("shuffle", "Shuffle", None, "M+Z"),
    ("repeatall", "Repeat playlist", None, "M+L"),
    ("abloop", "A-B loop", None, "SM+L"),
    ("faster", "Faster", None, "M+="),
    ("slower", "Slower", None, "M+-"),
    ("back3", "Back 3 s", "S+Left", "CM+Left"),
    ("fwd3", "Forward 3 s", "S+Right", "CM+Right"),
    ("back10", "Back 10 s", "A+Left", "AM+Left"),
    ("fwd10", "Forward 10 s", "A+Right", "AM+Right"),
    ("back60", "Back 1 min", "C+Left", "SM+Left"),
    ("fwd60", "Forward 1 min", "C+Right", "SM+Right"),
    ("back300", "Back 5 min", "CA+Left", "ASM+Left"),
    ("fwd300", "Forward 5 min", "CA+Right", "ASM+Right"),
    ("discmenu", "Disc menu", None, "C+M"),
    ("titleprev", "Previous title", None, "C+P"),
    ("titlenext", "Next title", None, "C+N"),
    ("chapterprev", "Previous chapter", None, "C+U"),
    ("chapternext", "Next chapter", None, "C+D"),
    # --- audio ---
    ("volup", "Volume up", "C+Up", "M+Up"),
    ("voldown", "Volume down", "C+Down", "M+Down"),
    ("mute", "Mute", None, "AM+Down"),
    # --- video ---
    ("fullscreen", "Full screen", None, "M+F"),
    ("snapshot", "Snapshot", None, "AM+S"),
    ("zoomquarter", "Zoom 1:4", "A+1", None),
    ("zoomhalf", "Zoom 1:2", "A+2", "M+0"),
    ("zoomoriginal", "Zoom 1:1", "A+3", "M+1"),
    ("zoomdouble", "Zoom 2:1", "A+4", "M+2"),
    ("fitscreen", "Fit to screen", None, "M+3"),
    ("scaleup", "Scale up", "A+O", None),
    ("scaledown", "Scale down", "AS+O", None),
    ("croptop", "Crop top", "A+R", None),
    ("cropleft", "Crop left", "A+D", None),
    ("cropbottom", "Crop bottom", "A+C", None),
    ("cropright", "Crop right", "A+F", None),
    ("uncroptop", "Uncrop top", "AS+R", None),
    ("uncropleft", "Uncrop left", "AS+D", None),
    ("uncropbottom", "Uncrop bottom", "AS+C", None),
    ("uncropright", "Uncrop right", "AS+F", None),
    # --- subtitles ---
    ("subsize", "Reset subtitle size", "C+0", None),
    ("subsync", "Reset subtitle sync", "CS+K", "SM+K"),
    # --- tools and windows ---
    ("effects", "Effects and filters", "C+E", None),
    ("videoeffects", "Video effects", None, "M+E"),
    ("audioeffects", "Audio effects", None, "SM+E"),
    ("mediainfo", "Media information", "C+I", "M+I"),
    ("codecinfo", "Codec information", "C+J", None),
    ("messages", "Messages", "C+M", "SM+M"),
    ("errors", "Errors and warnings", None, "AM+M"),
    (None, "Settings", "C+P", "M+,"),
    ("playlist", "Playlist", "C+L", "AM+P"),
    ("playbackwin", "Playback window", None, "AM+C"),
    ("minimal", "Minimal interface", "C+H", None),
    ("fsinterface", "Full screen interface", "+F11", None),
    (None, "Bookmarks", "C+B", "M+B"),
    ("clearplaylist", "Clear playlist", "C+W", None),
    (None, "Find", None, "SM+F"),
    (None, "Help", None, "SM+/"),
]
# Ctrl+F1..F10 (Cmd+F1..F8 on macOS) set bookmarks 1..10; the 10th draws "0".
for n in range(1, 11):
    ROWS.append((f"setbm{n % 10}", f"Set bookmark {n}", f"C+F{n}",
                 f"M+F{n}" if n <= 8 else None))

HEADER = """\
# VLC media player shortcut overlays for PolyKybd.
# GENERATED by gen_specs.py from its table -- edit the table, not this file.
#
# Keys: VLC 3.0.x defaults, read from its source. See SOURCES.md.
#
# Regenerate:
#   python polyhost/res/overlay_sources/vlc/fetch_icons.py
#   python polyhost/res/overlay_sources/vlc/gen_specs.py
#   python scripts/generate_app_overlays.py \\
#       polyhost/res/overlay_sources/vlc/bindings.yaml --preview /tmp/vlc_preview
app: vlc
match: [vlc]
output: vlc_template
icon_dir: icons
fit: contain
anchor: bottom-right
region: [36, 32]
margin: 0
mode: luma
threshold: 150

program_icon: vlc.png
program_icon_mode: alpha
program_icon_anchor: right
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
