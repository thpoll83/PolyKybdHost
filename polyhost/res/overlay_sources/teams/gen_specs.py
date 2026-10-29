#!/usr/bin/env python3
"""Write the two Microsoft Teams overlay specs from one table.

Microsoft's "Keyboard shortcuts for Microsoft Teams" page has, per platform
tab, a column for the desktop app and a column for the web app, and the four
keymaps differ (web Search is Ctrl+Alt+E, desktop Ctrl+E; macOS remaps many
keys). So:

    bindings.yaml   the desktop app: Windows set and macOS set
    web.yaml        Teams in a browser: Windows/Linux set and macOS set. It also
                    serves teams-for-linux, which wraps the web app.

Each row: (icon, label, Windows desktop, macOS desktop, Windows web, macOS web).
A key is written as modifier letters and a key name joined by "+": C Ctrl,
A Alt (Option on a Mac), S Shift, M Cmd. None means the column has no key.
See SOURCES.md for the source and the keys left out.

    python polyhost/res/overlay_sources/teams/gen_specs.py
    python scripts/generate_app_overlays.py polyhost/res/overlay_sources/teams/<spec>.yaml
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

MODS = {"C": "CTRL", "A": "ALT", "S": "SHIFT", "M": "GUI"}
KEYS = {",": "COMMA", ".": "DOT", "=": "EQUAL", "-": "MINUS", "/": "SLASH",
        "[": "LBRACKET", "]": "RBRACKET", "Enter": "ENTER", "Space": "SPACE",
        "Up": "UP", "Down": "DOWN", "Left": "LEFT", "Right": "RIGHT"}

D = range(1, 10)

ROWS = [
    # --- general ---
    ("shortcuts", "Keyboard shortcuts", "C+.", "M+.", "C+.", "M+."),
    ("search", "Search", "C+E", "M+E", "CA+E", "AM+E"),
    ("filter", "Filter", "CS+F", "MS+F", "CS+F", "MS+F"),
    ("newchat", "New chat", "C+N", "M+N", "A+N", "CM+N"),
    ("newwindowchat", "New chat in a window", "CS+N", "MS+N", None, None),
    ("settings", "Settings", "C+,", "M+,", "CS+,", "MS+,"),
    ("help", "Help", "+F1", "+F1", "C+F1", "M+F1"),
    ("zoomin", "Zoom in", "C+=", "M+=", None, None),
    ("zoomout", "Zoom out", "C+-", "M+-", None, None),
    ("resetzoom", "Reset zoom", "C+0", "C+0", None, None),
    ("report", "Report a problem", "CAS+R", "ASM+R", "CAS+R", "ASM+R"),
    ("gotochat", "Go to chat or channel", "C+G", "M+G", "C+G", "M+G"),
    ("pinontop", "Pin window on top", "CS+T", "SM+T", None, None),
    ("openwindow", "Open in new window", "C+O", "M+O", None, None),
    # --- navigation ---
    ("focuslist", "Chat and channel list", "C+L", "M+L", "AS+L", "CM+L"),
    ("focusmsg", "Message pane", "C+M", "M+P", "AS+M", "CM+P"),
    ("compose", "Compose box", "C+R", "M+R", "AS+R", "CM+R"),
    ("history", "History menu", "C+H", "M+Y", None, None),
    ("nextsection", "Next section", "C+F6", "M+F6", "C+F6", "C+F6"),
    ("prevsection", "Previous section", "CS+F6", "MS+F6", "CS+F6", "MS+F6"),
    ("back", "Back", "A+Left", "M+[", None, None),
    ("forward", "Forward", "A+Right", "M+]", None, None),
    ("movechatup", "Move chat up", "CAS+Up", None, "CAS+Up", None),
    ("movechatdown", "Move chat down", "CAS+Down", None, "CAS+Down", None),
    # --- messaging ---
    ("collapse", "Collapse folders", "A+Q", "MS+L", "A+Q", "MS+L"),
    ("jumpnew", "Jump to newest", "C+J", "M+J", "A+J", "M+J"),
    ("find", "Find in chat", "C+F", "M+F", "C+F", "M+F"),
    ("details", "Details pane", "A+P", "M+D", "A+P", "CM+E"),
    ("reply", "Reply to last message", "AS+R", "SM+R", "A+R", "CM+Z"),
    ("react", "React to last message", "CA+R", "AM+R", "CA+R", "AM+R"),
    ("unread", "Unread", "CA+U", "AM+U", "CA+U", "AM+U"),
    ("mentions", "Mentions", "CA+M", "AM+M", "CA+M", "AM+M"),
    ("chat", "All chats", "CA+C", "AM+C", "CA+C", "AM+C"),
    ("channels", "All channels", "CA+A", "AM+A", "CA+A", "AM+A"),
    ("meetingchats", "Meeting chats", "CA+B", "AM+B", "CA+B", "AM+B"),
    ("clearfilters", "Clear filters", "CA+Z", "AM+Z", "CA+Z", "AM+Z"),
    # --- compose ---
    ("expand", "Expand compose box", "CS+X", "SM+X", "CS+X", "SM+X"),
    ("send", "Send", "C+Enter", "M+Enter", "C+Enter", "M+Enter"),
    ("paragraph", "Paragraph style", "CA+P", "AM+P", "CA+P", "AM+P"),
    ("quote", "Block quote", "CA+4", None, "CA+4", None),
    ("attach", "Attach file", "AS+O", "AM+O", "AS+O", "AM+O"),
    ("h1", "Heading 1", "CA+1", "AM+1", "CA+1", "AM+1"),
    ("h2", "Heading 2", "CA+2", "AM+2", "CA+2", "AM+2"),
    ("h3", "Heading 3", "CA+3", "AM+3", "CA+3", "AM+3"),
    (None, "Bold", "C+B", "M+B", "C+B", "M+B"),
    (None, "Italic", "C+I", "M+I", "C+I", "M+I"),
    (None, "Underline", "C+U", "M+U", "C+U", "M+U"),
    ("strike", "Strikethrough", "CA+X", "CM+X", "CA+X", "CM+X"),
    ("important", "Mark important", "CS+I", "SM+I", "CS+I", "SM+I"),
    ("copilot", "Rewrite with Copilot", "A+A", "CM+A", "A+A", "CM+A"),
    ("videorec", "Video recorder", "AS+E", "AM+E", "AS+E", "AS+E"),
    ("loop", "Loop paragraph", "CA+L", "AM+L", "CA+L", "AM+L"),
    ("link", "Insert link", "C+K", "M+K", "C+K", "M+K"),
    ("inlinecode", "Inline code", "CS+C", "SM+C", "CAS+C", "ASM+C"),
    ("codeblock", "Code block", "CS+B", "SM+B", "CAS+B", "ASM+B"),
    ("insertcode", "Insert code", "CA+5", "AM+4", "CA+5", "AM+4"),
    # --- calls and meetings ---
    ("acceptvideo", "Accept video call", "CS+A", "MS+V", None, "SM+A"),
    ("acceptaudio", "Accept audio call", "CS+S", "MS+A", "AS+S", "MS+S"),
    ("decline", "Decline", "CS+D", "MS+D", "CS+D", "MS+D"),
    ("startaudio", "Start audio call", "AS+A", "MA+S", "AS+A", "MSC+A"),
    ("startvideo", "Start video call", "AS+V", "MS+S", "AS+V", "MSC+V"),
    ("endcall", "End call", "CS+H", "MS+H", "CS+H", "MS+H"),
    ("mute", "Mute", "CS+M", "MS+M", "CS+M", "MS+M"),
    ("camera", "Video on/off", "CS+O", "MS+O", None, "MS+O"),
    ("speaker", "Speaker on/off", "CS+U", None, "CS+U", None),
    ("tempunmute", "Hold to unmute", "C+Space", "A+Space", "C+Space", "A+Space"),
    ("raisehand", "Raise hand", "CS+K", "MS+K", "CS+K", "MS+K"),
    ("sharescreen", "Share content", "CS+E", "MS+E", "CS+E", "MS+E"),
    ("sharetoolbar", "Sharing toolbar", "CS+Space", "MS+Space", "CS+Space", "MS+Space"),
    ("admit", "Admit from lobby", "CS+Y", "MS+Y", None, "MS+Y"),
    ("schedule", "Schedule meeting", "A+N", "CM+N", None, "ASM+N"),
    ("joinmeeting", "Join meeting", "AS+J", "CM+K", "AS+J", "CM+K"),
    ("joinfromtoast", "Join from notification", "CS+J", None, None, "MS+J"),
    ("meetingchat", "Meeting chat", "CS+R", "MC+C", None, "CM+C"),
    ("fullscreen", "Full screen", "+F11", None, None, None),
    ("sharezoomin", "Zoom shared content in", "AS+=", "AM+=", "AS+=", "AM+="),
    ("sharezoomout", "Zoom shared content out", "AS+-", "AM+-", "AS+-", "AM+-"),
    ("sharezoomreset", "Reset shared content zoom", "AS+0", "AM+0", "AS+0", "AM+0"),
    ("panup", "Pan shared content up", "AS+Up", "AM+Up", "AS+Up", "AM+Up"),
    ("pandown", "Pan shared content down", "AS+Down", "AM+Down", "AS+Down", "AM+Down"),
    ("panleft", "Pan shared content left", "AS+Left", None, "AS+Left", "AM+Left"),
    ("panright", "Pan shared content right", "AS+Right", None, "AS+Right", "AM+Right"),
    # --- calendar ---
    ("dayview", "Day view", "AS+1", None, "AS+1", None),
    ("workweek", "Work week view", "AS+2", None, "AS+2", None),
    ("weekview", "Week view", "AS+3", None, "AS+3", None),
    ("monthview", "Month view", "AS+4", None, "AS+4", None),
    ("agenda", "Agenda", "AS+5", None, "AS+5", None),
    ("prevperiod", "Previous period", "CA+Left", "AM+Left", "CA+Left", None),
    ("nextperiod", "Next period", "CA+Right", "AM+Right", "CA+Right", None),
    ("today", "Today", None, "M+T", None, None),
    # --- editing (shared concepts) ---
    (None, "Cut", "C+X", "M+X", "C+X", "M+X"),
    (None, "Copy", "C+C", "M+C", "C+C", "M+C"),
    (None, "Paste", "C+V", "M+V", "C+V", "M+V"),
    (None, "Undo", "C+Z", "M+Z", "C+Z", "M+Z"),
    (None, "Select all", "C+A", "M+A", "C+A", "M+A"),
]
# The numbered rows: the Nth app on the app bar and the Nth tab of a chat.
for n in D:
    ROWS.append((f"app{n}", f"App {n}", f"C+{n}", f"M+{n}", f"CS+{n}", f"CS+{n}"))
for n in D:
    ROWS.append((f"tab{n}", f"Chat tab {n}", f"A+{n}", f"C+{n}", f"A+{n}", f"C+{n}"))

HEADER = """\
# Microsoft Teams {what} shortcut overlays for PolyKybd.
# GENERATED by gen_specs.py from its table -- edit the table, not this file.
#
# Shortcuts: Microsoft Support, "Keyboard shortcuts for Microsoft Teams", the
# {column} column of its Windows and macOS tabs. See SOURCES.md.
#
# Regenerate:
#   python polyhost/res/overlay_sources/teams/gen_specs.py
#   python scripts/generate_app_overlays.py \\
#       polyhost/res/overlay_sources/teams/{spec} --preview /tmp/teams_preview
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
{extra}
bindings:
"""

PROGRAM_ICON = """
program_icon: teams_logo.png     # generic drawn mark (see fetch_icons._draw_teams_logo)
program_icon_mode: alpha          # white-on-transparent drawing: alpha is the shape
program_icon_anchor: bottom-right
program_icon_region: [46, 40]
program_icon_margin: 0
"""

# Labels that would fold onto a shared concept but mean something else here.
NOT_SHARED = {"Zoom shared content in", "Zoom shared content out",
              "Reset shared content zoom", "Find in chat", "Send"}


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
    if label in NOT_SHARED:
        parts.append("shared: false")
    parts.append("only: [macos]" if mac else "except: [macos]")
    return "  - { " + ", ".join(parts) + " }"


def render(win_col: int, mac_col: int, **fmt) -> str:
    out = [HEADER.format(**fmt)]
    for row in ROWS:
        icon, label = row[0], row[1]
        if row[win_col]:
            out.append(line(icon, label, row[win_col], mac=False))
        if row[mac_col]:
            out.append(line(icon, label, row[mac_col], mac=True))
    return "\n".join(out) + "\n"


def main() -> int:
    specs = {
        "bindings.yaml": render(
            2, 3, what="desktop app (Windows and macOS)",
            column="desktop app", spec="bindings.yaml", app="teams",
            match="ms-teams, teams, microsoft teams", output="teams_template",
            extra=PROGRAM_ICON),
        "web.yaml": render(
            4, 5, what="web app (in a browser; Windows, Linux and macOS)",
            column="web app", spec="web.yaml", app="teams-web",
            match="teams-for-linux", output="teams_web_template", extra=""),
    }
    for name, text in specs.items():
        (HERE / name).write_text(text, encoding="utf-8")
        print(f"{name}: {text.count(chr(10) + '  - {')} bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
