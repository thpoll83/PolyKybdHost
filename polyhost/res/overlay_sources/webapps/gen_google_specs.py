#!/usr/bin/env python3
"""Write the Google Sheets, Slides, Gmail and Calendar overlay specs.

Each table row is (icon, label, Windows/Linux key, macOS key), read from the
PC and Mac tables of Google's help pages (see SOURCES.md). A key is written as
modifier letters and a key name joined by "+": C Ctrl, A Alt (Option on a Mac),
S Shift, M Cmd. None means the platform has no key. A row whose macOS key is the
Windows key with Ctrl replaced by Cmd becomes one `CMDCTRL` binding; any other
row is written twice, under `except: [macos]` and `only: [macos]`. An icon of
None draws the label through the shared concept renderer (Bold, Copy, ...).

    python polyhost/res/overlay_sources/webapps/gen_google_specs.py
    python scripts/generate_app_overlays.py polyhost/res/overlay_sources/webapps/<spec>.yaml
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

MODS = {"C": "CTRL", "A": "ALT", "S": "SHIFT", "M": "GUI"}
KEYS = {",": "COMMA", ".": "DOT", "=": "EQUAL", "-": "MINUS", "/": "SLASH",
        "[": "LBRACKET", "]": "RBRACKET", "\\": "BACKSLASH", ";": "SEMICOLON",
        "'": "QUOTE", "`": "GRAVE", "Enter": "ENTER", "Bksp": "BSPC",
        "Up": "UP", "Down": "DOWN", "Left": "LEFT", "Right": "RIGHT",
        "Home": "HOME", "End": "END"}

SHEETS = [
    # --- common actions ---
    (None, "Select all", "C+A", "M+A"),
    (None, "Undo", "C+Z", "M+Z"),
    (None, "Redo", "C+Y", "M+Y"),
    (None, "Redo", "CS+Z", "MS+Z"),
    ("find", "Find", "C+F", "M+F"),
    ("findreplace", "Find and replace", "C+H", "MS+H"),
    ("fillrange", "Fill range", "C+Enter", "M+Enter"),
    ("filldown", "Fill down", "C+D", "M+D"),
    ("fillright", "Fill right", "C+R", "M+R"),
    ("save", "Save", "C+S", "M+S"),
    ("open", "Open", "C+O", "M+O"),
    ("print", "Print", "C+P", "M+P"),
    (None, "Copy", "C+C", "M+C"),
    (None, "Cut", "C+X", "M+X"),
    (None, "Paste", "C+V", "M+V"),
    ("pastevalues", "Paste values only", "CS+V", "MS+V"),
    ("shortcuts", "Keyboard shortcuts", "C+/", "M+/"),
    ("compact", "Compact controls", "CS+F", "CS+F"),
    ("toolfinder", "Tool finder", "A+/", "A+/"),
    ("rename", "Rename sheet", "A+1", None),
    ("table", "Convert to table", "CA+T", "AM+T"),
    ("gotorange", "Go to range", None, "C+G"),
    # --- format cells ---
    (None, "Bold", "C+B", "M+B"),
    (None, "Underline", "C+U", "M+U"),
    (None, "Italic", "C+I", "M+I"),
    ("strikethrough", "Strikethrough", "AS+5", "MS+X"),
    ("aligncenter", "Center align", "CS+E", "MS+E"),
    ("alignleft", "Left align", "CS+L", "MS+L"),
    ("alignright", "Right align", "CS+R", "MS+R"),
    ("bordertop", "Top border", "AS+1", "AS+1"),
    ("borderright", "Right border", "AS+2", "AS+2"),
    ("borderbottom", "Bottom border", "AS+3", "AS+3"),
    ("borderleft", "Left border", "AS+4", "AS+4"),
    ("bordernone", "Remove borders", "AS+6", "AS+6"),
    ("borderouter", "Outer border", "AS+7", "AS+7"),
    ("link", "Insert link", "C+K", "M+K"),
    ("inserttime", "Insert time", "CS+;", "MS+;"),
    ("insertdate", "Insert date", "C+;", "M+;"),
    ("insertdatetime", "Insert date and time", "CAS+;", "AMS+;"),
    ("fmtdecimal", "Format as decimal", "CS+1", "CS+1"),
    ("fmttime", "Format as time", "CS+2", "CS+2"),
    ("fmtdate", "Format as date", "CS+3", "CS+3"),
    ("fmtcurrency", "Format as currency", "CS+4", "CS+4"),
    ("fmtpercent", "Format as percentage", "CS+5", "CS+5"),
    ("fmtexponent", "Format as exponent", "CS+6", "CS+6"),
    ("clearfmt", "Clear formatting", "C+\\", "M+\\"),
    # --- navigate ---
    ("sheetstart", "Beginning of sheet", "C+Home", None),
    ("sheetend", "End of sheet", "C+End", None),
    ("activecell", "Scroll to active cell", "C+Bksp", "M+Bksp"),
    ("nextsheet", "Next sheet", "A+Down", "A+Down"),
    ("prevsheet", "Previous sheet", "A+Up", "A+Up"),
    ("sheetlist", "List of sheets", "AS+K", "AS+K"),
    ("openlink", "Open link", "A+Enter", "A+Enter"),
    ("explore", "Explore", "CAS+I", "AMS+I"),
    ("sidepanel", "Side panel", "CA+.", "AM+."),
    ("sidepanel", "Side panel", "CA+,", "AM+,"),
    ("quicksum", "Quick sum", "AS+Q", "AS+Q"),
    ("filter", "Filter menu", "CA+R", "CM+R"),
    ("history", "Version history", "CAS+H", "AMS+H"),
    # --- comments and menus ---
    ("addcomment", "Insert comment", "CA+M", "AM+M"),
    ("comment", "Open discussion thread", "CAS+A", "AMS+A"),
    ("sheetmenu", "Sheet menu", "AS+S", "AS+S"),
    ("contextmenu", "Context menu", "CS+\\", "MS+\\"),
    ("columnmenu", "Table column menu", "CA+\\", "AM+\\"),
    ("insertmenu", "Insert cells", "CA+=", "AM+="),
    ("deletemenu", "Delete cells", "CA+-", "AM+-"),
    ("showmenus", "Show or hide menus", None, "AM+R"),
    # --- rows, columns and formulas ---
    ("hiderow", "Hide row", "CA+9", "AM+9"),
    ("unhiderow", "Unhide row", "CS+9", "MS+9"),
    ("hidecol", "Hide column", "CA+0", "AM+0"),
    ("unhidecol", "Unhide column", "CS+0", "MS+0"),
    ("group", "Group", "AS+Right", "AS+Right"),
    ("ungroup", "Ungroup", "AS+Left", "AS+Left"),
    ("expand", "Expand group", "AS+Down", "AS+Down"),
    ("collapse", "Collapse group", "AS+Up", "AS+Up"),
    ("formulas", "Show all formulas", "C+`", "C+`"),
    ("arrayformula", "Array formula", "CS+Enter", "MS+Enter"),
    ("collapsearray", "Collapse array", "C+E", "M+E"),
    # --- accessibility ---
    ("screenreader", "Screen reader support", "CA+Z", "AM+Z"),
    ("braille", "Braille support", "CA+H", "AM+H"),
    ("readcolumn", "Read column", "CAS+C", "AMS+C"),
    ("readrow", "Read row", "CAS+R", "AMS+R"),
]

SLIDES = [
    # --- common actions ---
    ("newslide", "New slide", "C+M", "C+M"),
    ("duplicate", "Duplicate", "C+D", "M+D"),
    (None, "Undo", "C+Z", "M+Z"),
    (None, "Redo", "C+Y", "M+Y"),
    (None, "Redo", "CS+Z", "MS+Z"),
    (None, "Copy", "C+C", "M+C"),
    (None, "Cut", "C+X", "M+X"),
    (None, "Paste", "C+V", "M+V"),
    ("copyformat", "Copy formatting", "CA+C", "AM+C"),
    ("pasteformat", "Paste formatting", "CA+V", "AM+V"),
    ("link", "Insert link", "C+K", "M+K"),
    ("openlink", "Open link", "A+Enter", "A+Enter"),
    (None, "Select all", "C+A", "M+A"),
    ("find", "Find", "C+F", "M+F"),
    ("findreplace", "Find and replace", "C+H", "MS+H"),
    ("findnext", "Find next", "C+G", "M+G"),
    ("findprev", "Find previous", "CS+G", "MS+G"),
    ("open", "Open", "C+O", "M+O"),
    ("print", "Print", "C+P", "M+P"),
    ("save", "Save", "C+S", "M+S"),
    ("shortcuts", "Keyboard shortcuts", "C+/", "M+/"),
    ("toolfinder", "Tool finder", "A+/", "A+/"),
    ("compact", "Compact mode", "CS+F", "CS+F"),
    ("captions", "Captions", "CS+C", "MS+C"),
    ("alttext", "Alt text", "CA+Y", "AM+Y"),
    # --- navigation ---
    (None, "Zoom in", "C+=", "M+="),
    (None, "Zoom out", "C+-", "M+-"),
    ("zoomreset", "Zoom 100%", "C+0", "M+0"),
    ("filmstrip", "Filmstrip", "CAS+F", "AMS+F"),
    ("canvas", "Canvas", "CAS+C", "AMS+C"),
    ("notes", "Speaker notes", "CAS+S", "AMS+S"),
    ("htmlview", "HTML view", "CAS+P", "AMS+P"),
    ("animations", "Animations", "CAS+B", "AMS+B"),
    ("explore", "Explore", "CAS+I", "AMS+I"),
    ("sidepanel", "Side panel", "CA+.", "AM+."),
    ("sidepanel", "Side panel", "CA+,", "AM+,"),
    ("dictionary", "Dictionary", "CS+Y", "MS+Y"),
    ("history", "Version history", "CAS+H", "AMS+H"),
    ("present", "Present", "C+F5", "M+Enter"),
    ("presentstart", "Present from beginning", None, "MS+Enter"),
    ("contextmenu", "Context menu", "CS+\\", "MS+\\"),
    ("contextmenu", "Context menu", "CS+X", None),
    # --- comments ---
    ("addcomment", "Insert comment", "CA+M", "AM+M"),
    ("comment", "Open discussion thread", "CAS+A", "AMS+A"),
    ("hidecomment", "Hide comment", "CAS+J", "AMS+J"),
    # --- text ---
    (None, "Bold", "C+B", "M+B"),
    (None, "Italic", "C+I", "M+I"),
    (None, "Underline", "C+U", "M+U"),
    ("subscript", "Subscript", "C+,", "M+,"),
    ("superscript", "Superscript", "C+.", "M+."),
    ("strikethrough", "Strikethrough", "AS+5", "MS+X"),
    ("clearfmt", "Clear formatting", "C+\\", "M+\\"),
    ("fontinc", "Larger font", "CS+.", "MS+."),
    ("fontdec", "Smaller font", "CS+,", "MS+,"),
    ("alignleft", "Left align", "CS+L", "MS+L"),
    ("alignright", "Right align", "CS+R", "MS+R"),
    ("aligncenter", "Center align", "CS+E", "MS+E"),
    ("alignjustify", "Justify", "CS+J", "MS+J"),
    ("paradown", "Move paragraph down", "AS+Down", None),
    ("paraup", "Move paragraph up", "AS+Up", None),
    ("indent", "Indent", "C+]", "M+]"),
    ("outdent", "Outdent", "C+[", "M+["),
    ("bulletlist", "Bulleted list", "CS+8", "MS+8"),
    ("numberlist", "Numbered list", "CS+7", "MS+7"),
    ("nextspell", "Next misspelling", "C+'", "M+'"),
    ("prevspell", "Previous misspelling", "C+;", "M+;"),
    # --- arrange objects ---
    ("group", "Group", "CA+G", "AM+G"),
    ("ungroup", "Ungroup", "CAS+G", "AMS+G"),
    ("sendbackward", "Send backward", "C+Down", "M+Down"),
    ("bringforward", "Bring forward", "C+Up", "M+Up"),
    ("sendback", "Send to back", "CS+Down", "MS+Down"),
    ("bringfront", "Bring to front", "CS+Up", "MS+Up"),
    ("rotateccw", "Rotate left 1°", "AS+Left", "AS+Left"),
    ("rotatecw", "Rotate right 1°", "AS+Right", "AS+Right"),
    ("widen", "Wider", "CA+B", "CM+B"),
    ("taller", "Taller", "CA+I", "CM+I"),
    ("shrink", "Smaller", "CA+J", "CM+J"),
    ("grow", "Larger", "CA+K", "CM+K"),
    ("shorter", "Shorter", "CA+9", None),
    ("narrower", "Narrower", "CA+W", "CM+W"),
    # --- accessibility ---
    ("speak", "Read selection", "CA+X", "CM+X"),
    ("speakcursor", "Read from cursor", "CA+R", "CM+R"),
    ("screenreader", "Screen reader support", "CA+Z", "AM+Z"),
    ("braille", "Braille support", "CA+H", "AM+H"),
]

GMAIL = [
    # --- compose ---
    ("nextchat", "Next chat or compose", "C+.", "C+."),
    ("prevchat", "Previous chat or compose", "C+,", "C+,"),
    ("submit", "Send", "C+Enter", "M+Enter"),
    ("addcc", "Add Cc", "CS+C", "MS+C"),
    ("addbcc", "Add Bcc", "CS+B", "MS+B"),
    ("fromaddr", "Change From", "CS+F", "MS+F"),
    ("link", "Insert link", "C+K", "M+K"),
    ("spelling", "Spelling suggestions", "C+M", None),
    ("nextspell", "Next misspelling", None, "M+;"),
    # --- formatting ---
    ("prevfont", "Previous font", "CS+5", "MS+5"),
    ("nextfont", "Next font", "CS+6", "MS+6"),
    ("fontdec", "Smaller text", "CS+-", "MS+-"),
    ("fontinc", "Larger text", "CS+=", "MS+="),
    (None, "Bold", "C+B", "M+B"),
    (None, "Italic", "C+I", "M+I"),
    (None, "Underline", "C+U", "M+U"),
    ("numberlist", "Numbered list", "CS+7", "MS+7"),
    ("bulletlist", "Bulleted list", "CS+8", "MS+8"),
    ("quote", "Quote", "CS+9", "MS+9"),
    ("outdent", "Outdent", "C+[", "M+["),
    ("indent", "Indent", "C+]", "M+]"),
    ("alignleft", "Align left", "CS+L", "MS+L"),
    ("aligncenter", "Align center", "CS+E", "MS+E"),
    ("alignright", "Align right", "CS+R", "MS+R"),
    ("clearfmt", "Remove formatting", "C+\\", "M+\\"),
    # --- side panel ---
    ("sidepanel", "Side panel", "CA+.", "AM+."),
    ("sidepanel", "Side panel", "CA+,", "AM+,"),
]

CALENDAR = [
    ("save", "Save event", "C+S", "M+S"),
    ("sidepanel", "Side panel", "CA+.", "AM+."),
    ("sidepanel", "Side panel", "CA+,", "AM+,"),
]

# Labels that would fold onto a shared concept but mean something else here.
NOT_SHARED = {"Send", "Save event", "Find next", "Find previous"}

HEADER = """\
# {name} (in-browser) shortcut overlays for PolyKybd. See SOURCES.md.
# GENERATED by gen_google_specs.py from its table -- edit the table, not this file.
#
# Shortcuts: the PC and Mac tables of Google's help page
# {page}
# Bare letters, digits and Shift+letter keys are left out: they would replace
# the letter legends while the user types.
#
# Regenerate:
#   python polyhost/res/overlay_sources/webapps/fetch_icons.py
#   python polyhost/res/overlay_sources/webapps/gen_google_specs.py
#   python scripts/generate_app_overlays.py \\
#       polyhost/res/overlay_sources/webapps/{spec} --preview /tmp/{app}_preview
app: {app}
match: [{app}]
output: {app}_template
icon_dir: icons
fit: contain
anchor: bottom-right
region: [40, 36]
margin: 0
mode: luma
threshold: 150

program_icon: {mark}
program_icon_mode: alpha
{mark_geometry}
bindings:
"""

# Sheets and Slides are documents: a labelled page frame, like Google Docs'.
DOC_GEOMETRY = "program_icon_region: [72, 40]\nprogram_icon_margin: 0\n"
# Gmail and Calendar: the brand mark, at the size the other brand marks use.
BRAND_GEOMETRY = ("program_icon_anchor: right\nprogram_icon_region: [37, 32]\n"
                  "program_icon_margin: 0\n")


def parse(chord: str) -> tuple[str, list[str]]:
    mods, key = chord.split("+", 1)
    key = KEYS.get(key, key)
    if key.isdigit():
        key = f'"{key}"'
    return key, [MODS[m] for m in mods]


def line(icon, label, chord, scope: str, cmdctrl: bool = False) -> str:
    key, mods = parse(chord)
    if cmdctrl:
        mods = ["CMDCTRL" if m == "CTRL" else m for m in mods]
    parts = [f"key: {key}", f"mods: [{', '.join(mods)}]"]
    if icon:
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


def render(rows, **fmt) -> str:
    out = [HEADER.format(**fmt)]
    for icon, label, win, mac in rows:
        if win and mac and "C" in win.split("+", 1)[0] and ctrl_to_cmd(win) == mac:
            out.append(line(icon, label, win, "", cmdctrl=True))
            continue
        if win:
            out.append(line(icon, label, win, "except: [macos]"))
        if mac:
            out.append(line(icon, label, mac, "only: [macos]"))
    return "\n".join(out) + "\n"


SPECS = {
    "googlesheets.yaml": (SHEETS, dict(name="Google Sheets", app="googlesheets", mark="gs.png",
                                       page="https://support.google.com/docs/answer/181110", mark_geometry=DOC_GEOMETRY)),
    "googleslides.yaml": (SLIDES, dict(name="Google Slides", app="googleslides", mark="gsl.png",
                                       page="https://support.google.com/docs/answer/1696717", mark_geometry=DOC_GEOMETRY)),
    "gmail.yaml": (GMAIL, dict(name="Gmail", app="gmail", mark="gmail.png",
                               page="https://support.google.com/mail/answer/6594", mark_geometry=BRAND_GEOMETRY)),
    "googlecalendar.yaml": (CALENDAR, dict(name="Google Calendar", app="googlecalendar",
                                           mark="gcal.png", page="https://support.google.com/calendar/answer/37034",
                                           mark_geometry=BRAND_GEOMETRY)),
}


def main() -> int:
    for name, (rows, fmt) in SPECS.items():
        text = render(rows, spec=name, **fmt)
        (HERE / name).write_text(text, encoding="utf-8")
        print(f"{name}: {text.count(chr(10) + '  - {')} bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
