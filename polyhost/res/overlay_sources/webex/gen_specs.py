#!/usr/bin/env python3
"""Write the two Cisco Webex overlay specs from one table.

Cisco documents two desktop clients with different keys:

    app.yaml        Webex App (CiscoCollabHost): messaging, calling and meetings
                    on the Webex Suite platform. Windows/Linux set and macOS set.
    meetings.yaml   the older Webex Meetings desktop app (meetings and webinars
                    on the Webex Meetings platform). Windows set and macOS set.

Each row: (icon, label, App Windows, App macOS, Meetings Windows, Meetings macOS).
A key is written as modifier letters and a key name joined by "+": C Ctrl,
A Alt (Option on a Mac), S Shift, M Cmd. None means the column has no key.
See SOURCES.md for the sources and the keys left out.

    python polyhost/res/overlay_sources/webex/gen_specs.py
    python scripts/generate_app_overlays.py polyhost/res/overlay_sources/webex/<spec>.yaml
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

MODS = {"C": "CTRL", "A": "ALT", "S": "SHIFT", "M": "GUI"}
KEYS = {",": "COMMA", ".": "DOT", "=": "EQUAL", "-": "MINUS", "/": "SLASH",
        "[": "LBRACKET", "]": "RBRACKET", "Enter": "ENTER", "Space": "SPACE",
        "Up": "UP", "Down": "DOWN", "Left": "LEFT", "Right": "RIGHT",
        "Del": "DELETE", "Bksp": "BSPC"}

ROWS = [
    # --- general ---
    ("search", "Search", "C+F", "M+F", None, None),
    ("back", "Back", "A+Left", "M+[", None, None),
    ("forward", "Forward", "A+Right", "M+]", None, None),
    ("tabmessaging", "Messaging", "C+1", "SM+A", None, None),
    ("tabteams", "Teams", "C+2", "SM+T", None, None),
    ("tabcontacts", "Contacts", "C+3", "SM+G", None, None),
    ("tabcalling", "Calling", "C+4", "SM+C", None, None),
    ("tabmeetings", "Meetings", "C+5", "SM+B", None, None),
    ("tabinsights", "Personal insights", "C+6", "SM+O", None, None),
    ("tabvoicemail", "Voicemail", "C+7", "SM+V", None, None),
    ("tabwhiteboards", "Whiteboards", "C+8", "SM+W", None, None),
    ("health", "Health center", "+F1", None, None, None),
    ("settings", "Preferences", "C+,", "M+,", None, None),
    ("assistant", "AI Assistant", "A+L", "C+L", None, None),
    ("diagnostics", "Diagnostics", "CAS+D", "CAS+D", None, None),
    ("navmenu", "Collapse navigation", "AS+Q", "AM+Q", None, None),
    ("shortcuts", "Keyboard shortcuts", "C+/", "M+/", "C+/", None),
    ("signout", "Sign out", "A+Q", None, None, None),
    # --- messaging ---
    ("findinspace", "Search in space", "CS+J", "SM+F", None, None),
    ("newdm", "Direct message", "C+N", "SM+P", None, None),
    ("newspace", "Create space", "CS+N", "SM+N", None, None),
    ("allspaces", "All spaces", "AS+A", "M+1", None, None),
    ("notifications", "Notifications", "AS+N", "M+2", None, None),
    ("drafts", "Drafts", "AS+D", "M+3", None, None),
    ("unread", "Unread", "AS+E", "M+4", None, None),
    ("dmlist", "Direct messages", "CS+T", "M+5", None, None),
    ("favorites", "Favorites", "CS+O", "M+6", None, None),
    ("mentionsme", "Mentions to me", "AS+H", "M+7", None, None),
    ("mentionsall", "Mentions to all", "AS+G", "M+8", None, None),
    ("flagged", "Flagged", "AS+F", "M+9", None, None),
    ("spacemessages", "Messages tab", None, "CM+M", None, None),
    ("spacecontent", "Content tab", None, "CM+C", None, None),
    ("peopletab", "People tab", None, "ASM+P", None, None),
    ("linkstab", "Links tab", None, "SM+L", None, None),
    ("leavespace", "Leave space", "CS+E", "AM+E", None, None),
    ("addpeople", "Add people", "CS+P", "AM+P", None, None),
    ("stickers", "Stickers", "C+J", "C+J", None, None),
    ("gif", "GIF", "C+G", "C+G", None, None),
    ("emoji", "Emoji", "CS+Space", "CM+Space", None, None),
    ("attach", "Attach file", "C+O", "AM+A", None, None),
    ("prevspace", "Previous space", "A+Up", "A+Up", None, None),
    ("nextspace", "Next space", "A+Down", "A+Down", None, None),
    ("collapse", "Collapse sections", "AS+Left", "AM+Left", None, None),
    ("expand", "Expand sections", "AS+Right", "AM+Right", None, None),
    ("newwhiteboard", "New whiteboard", "CS+B", "ASM+W", None, None),
    ("spacewhiteboards", "Space whiteboards", "CS+W", "CSM+W", None, None),
    ("jumpnew", "New messages", "CA+M", None, None, None),
    ("roomlink", "Personal room link", "AS+P", "SM+K", None, None),
    ("capture", "Screen capture", None, "M+S", None, None),
    ("capturehide", "Screen capture, hide Webex", None, "AM+S", None, None),
    ("favorite", "Favorite space", "CS+F", "AM+V", None, None),
    ("callperson", "Call selected person", "CS+Enter", "M+Enter", None, None),
    ("gototeam", "Go to team", "CS+2", "ASM+T", None, None),
    ("reload", "Reload space", "CA+Y", "CS+Y", None, None),
    ("spacesettings", "Space settings", None, "CM+T", None, None),
    ("notifyall", "Notify on all messages", None, "AM+N", None, None),
    ("newmessage", "New message", "AS+J", None, None, None),
    ("newreply", "New reply", "AS+T", None, None, None),
    ("copyspace", "Copy space details", "CS+K", "AM+K", None, None),
    ("focusconv", "Conversation", "C+H", None, None, None),
    ("compose", "Message box", "CA+I", None, None, None),
    ("quickmsg", "Quick message", None, "CM+S", None, None),
    # --- formatting ---
    ("link", "Insert link", "C+K", "M+K", None, None),
    ("markdown", "Markdown on/off", "AS+M", "AM+F", None, None),
    ("h1", "Heading 1", "AS+1", "AM+1", None, None),
    ("h2", "Heading 2", "AS+2", "AM+2", None, None),
    ("h3", "Heading 3", "AS+3", "AM+3", None, None),
    (None, "Bold", "C+B", "M+B", None, None),
    (None, "Italic", "C+I", "M+I", None, None),
    (None, "Underline", "C+U", "M+U", None, None),
    # --- calls and meetings ---
    ("mute", "Mute", "C+M", "SM+M", "C+M", "SM+M"),
    ("camera", "Video on/off", "CS+V", "CS+V", "CS+V", "CS+V"),
    ("endcall", "Leave or end", "C+L", "M+L", "C+L", "M+L"),
    ("answer", "Answer call", "CS+C", "CS+C", None, None),
    ("answermsg", "Answer with message", "CA+A", None, None, None),
    ("decline", "Decline call", "C+D", "SM+D", None, None),
    ("callingdock", "Calling dock", "CS+X", None, None, None),
    ("hold", "Hold or resume", "CA+H", "CA+H", None, None),
    ("highlightcall", "Highlight to call", "CAS+H", "CAM+H", None, None),
    ("transfer", "Transfer call", "A+T", "AM+T", None, None),
    ("dialpad", "Dial pad", None, "CS+K", None, None),
    ("smartaudio", "Smart audio mode", "CS+M", "CS+M", "CS+M", "CS+M"),
    ("share", "Share content", "CS+D", "CS+D", "CS+D", "AM+K"),
    ("sharefile", "Share file", "CA+O", "M+O", "C+O", "M+O"),
    ("sharebrowser", "Share browser", None, None, "C+B", "AM+B"),
    ("whiteboard", "Share whiteboard", None, None, "CS+B", "CS+B"),
    ("pauseshare", "Pause sharing", "AS+S", "CS+S", None, None),
    ("stopshare", "Stop sharing", "CS+Z", "CS+Z", "CS+Z", "CS+Z"),
    ("videoview", "Video while sharing", "CA+P", "AS+P", None, None),
    ("cleanmode", "Clean mode", "CS+Q", "CS+Q", None, "ASM+H"),
    ("controls", "Meeting controls", "CS+H", "CS+H", "CS+Q", "CS+Q"),
    ("menubar", "Menu bar", None, None, "CS+H", None),
    ("floating", "Floating windows", "CAS+S", "ASM+S", None, "CSM+S"),
    ("annotate", "Start annotation", "AS+Z", "AM+Z", None, None),
    ("stopannotate", "Stop annotation", "AS+X", "AM+X", None, None),
    ("clearannot", "Clear annotations", "C+Del", "M+Bksp", "C+Del", "M+Bksp"),
    ("fullscreen", "Full screen", "A+Enter", "CS+F", "A+Enter", "CS+F"),
    ("thumbnails", "Thumbnails", "C+T", "M+T", "C+T", "SM+T"),
    ("raisehand", "Raise hand", "CS+R", "SM+R", "CS+R", "CS+R"),
    ("chat", "Chat", "C+E", "SM+E", "C+E", "SM+E"),
    ("chatnotify", "Chat read-out", "CA+K", "AM+J", "CS+K", "CS+K"),
    ("interpret", "Interpretation", "AS+W", "AM+W", "AS+W", None),
    ("outlang", "Output language", None, None, "AS+H", "CM+H"),
    ("videos", "Participant videos", "CAS+X", "SM+X", "CAS+X", "SM+X"),
    ("novideo", "Participants without video", "CA+Q", "SM+H", "CS+P", "SM+H"),
    ("names", "Names in video", "CS+I", "CS+I", "CS+I", "SM+I"),
    ("muteall", "Mute all", "CS+U", "SM+U", "CS+U", "SM+U"),
    ("lowerhands", "Lower all hands", "CS+L", "CS+L", "CS+L", "CS+L"),
    ("lock", "Lock meeting", "C+R", "M+R", "C+R", "M+R"),
    ("remove", "Remove attendee", "CA+R", "M+E", "CS+E", "M+E"),
    ("admit", "Admit from lobby", "CS+G", "CS+G", "CS+G", "CS+G"),
    ("allowshare", "Allow all to share", "CS+S", None, "CS+S", None),
    ("privileges", "Participant privileges", None, None, "C+K", "M+K"),
    ("addguest", "Add guest", "CA+G", None, None, None),
    ("remote", "Remote control", "AS+R", "AS+R", "AS+R", None),
    ("captions", "Captions", "CS+A", "CS+A", "CS+A", "CS+A"),
    ("captionmenu", "Captions panel", None, None, "C+P", "C+P"),
    ("notification", "Meeting notification", "C+F6", "M+F6", None, None),
    ("reactions", "Reactions", "CS+Y", "SM+Y", None, None),
    ("thumbsup", "Thumbs up", "AS+4", "AM+4", None, None),
    ("clap", "Clap", "AS+5", "AM+5", None, None),
    ("haha", "Haha", "AS+6", "AM+6", None, None),
    ("celebrate", "Celebrate", "AS+7", "AM+7", None, None),
    ("love", "Love", "AS+8", "AM+8", None, None),
    # --- shared content (Webex Meetings) ---
    ("sync", "Sync view", None, None, "CS+Y", "M+Y"),
    ("transferfile", "Transfer file", None, None, "CS+T", "M+T"),
    ("addpage", "Add whiteboard page", None, None, "CS+N", "SM+N"),
    ("fit", "Fit to viewer", None, None, "C+0", "M+0"),
    ("fitwidth", "Fit to width", None, None, "CS+W", "AM+0"),
    ("rotateleft", "Rotate left", None, None, "CS+,", "SM+L"),
    ("rotateright", "Rotate right", None, None, "CS+.", "SM+R"),
    ("closefile", "Close shared file", None, None, "C+W", None),
    (None, "Zoom in", "C+=", "M+=", "C+=", None),
    (None, "Zoom out", "C+-", "M+-", "C+-", None),
    (None, "Undo", None, None, "C+Z", "M+Z"),
    (None, "Redo", None, None, "C+Y", "SM+Z"),
]

HEADER = """\
# Cisco Webex {what} shortcut overlays for PolyKybd.
# GENERATED by gen_specs.py from its table -- edit the table, not this file.
#
# Shortcuts: Cisco Webex Help Center, "{article}", the Windows and macOS keys.
# See SOURCES.md.
#
# Regenerate:
#   python polyhost/res/overlay_sources/webex/gen_specs.py
#   python scripts/generate_app_overlays.py \\
#       polyhost/res/overlay_sources/webex/{spec} --preview /tmp/webex_preview
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

program_icon: webex.png
program_icon_mode: alpha
program_icon_anchor: right
program_icon_region: [37, 32]
program_icon_margin: 0

bindings:
"""

# Labels that would fold onto a shared concept but mean something else here.
NOT_SHARED = {"Search in space"}


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
        "app.yaml": render(
            2, 3, what="App (Windows, Linux and macOS)",
            article="Webex App | Keyboard navigation and shortcuts",
            spec="app.yaml", app="webex",
            match="ciscocollabhost, webex", output="webex_template"),
        "meetings.yaml": render(
            4, 5, what="Meetings desktop app (Windows and macOS)",
            article="Accessibility features for meetings and webinars",
            spec="meetings.yaml", app="webex-meetings",
            match="atmgr, cisco webex meetings, webex meetings",
            output="webex_meetings_template"),
    }
    for name, text in specs.items():
        (HERE / name).write_text(text, encoding="utf-8")
        print(f"{name}: {text.count(chr(10) + '  - {')} bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
