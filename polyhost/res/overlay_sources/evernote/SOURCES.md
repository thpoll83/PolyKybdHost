# Evernote desktop overlay: sources and licences

`gen_specs.py` writes `evernote.yaml` from its table; `fetch_icons.py` rebuilds
`icons/`; `scripts/generate_app_overlays.py` renders the PNGs.

| Set | Loads for | Keys |
|---|---|---|
| `evernote_template` (3 files) | Windows | 95 |
| `evernote_template_mac` (4 files) | macOS | 97 |

Each set also has Evernote's mark on ESC. Evernote has no Linux desktop app.

## App names

`evernote` (Windows `Evernote.exe`, the macOS app "Evernote"). Evernote is
closed source, so the names could not be read from its packaging, and they
were not checked on an install.

## Shortcuts

All keys come from Evernote's help center article "Keyboard shortcuts", which
has a Mac column and a Windows column (article updated 2026-10-26, read
2026-11-05):
<https://help.evernote.com/hc/en-us/articles/34296687388307-Keyboard-shortcuts>

The article page itself answers 403 to a script, so the text was read through
the help center's public Zendesk API, which returns the same article body:
`https://help.evernote.com/api/v2/help_center/en-us/articles/34296687388307.json`.

How the tables were read:

- Keys that are Ctrl on Windows and Cmd on macOS are one `CMDCTRL` binding;
  all others are written once per platform.
- The Mac column writes some keys as the shifted character. They are read as
  the US-layout key with Shift: Align left ⌥⌘{ = Cmd+Option+Shift+[, Align
  right ⌥⌘} = Cmd+Option+Shift+], Align center ⌥⌘+ = Cmd+Option+Shift+=,
  Superscript ^⌘+ = Ctrl+Cmd+Shift+=, Focus on note list ⌘| = Cmd+Shift+\,
  font size ⇧⌘> and ⇧⌘< = Cmd+Shift+. and Cmd+Shift+,. Zoom in is written
  ⌘+= in the same table and is read without Shift. This reading is not
  checked on a Mac.

### One key, two meanings

The Windows column gives some chords two actions in different tables. The
overlay draws one:

| Chord | Drawn | Not drawn |
|---|---|---|
| Ctrl+K / Cmd+K | Search | Add or edit link (in the note editor) |
| Ctrl+Q | Switch to | Justify |
| Ctrl+E | New event | Align center |
| Ctrl+M | Indent | Minimize window |
| Ctrl+Shift+M | Outdent | Add comment (only with text selected) |

So Windows has no Justify, Align center or Add comment key; macOS has all
three.

### Left out

- **Global shortcuts** (New note window, Paste to Evernote, Search in
  Evernote, Evernote Helper, Capture screen). They work while another app has
  the focus, and the overlay is shown only while Evernote has it.
- **macOS Cmd+M, Cmd+H and Cmd+Q** (minimize, hide, quit): system keys that the
  keyboard's own hints cover. Windows lists no hide or quit key.
- **macOS Shift+Space** (Simplify formatting, also Page up in the note list),
  so macOS has no Simplify formatting key.
- **Mouse actions** (Ctrl+Click, Shift+Click), **Tab** and **Shift+Tab**, and
  the note list's plain arrows, Home, End, Space and Shift+Space.
- **The auto formatting table**: text typed into a note (`#`, `[]`, `---`),
  not keys.

## Icons

| Icon | Source | Licence |
|---|---|---|
| shortcut icons (see `ICONS` in `fetch_icons.py`) | Microsoft Fluent UI System Icons, <https://github.com/microsoft/fluentui-system-icons> | MIT |
| `templates` (`dashboard_customize`), `replace` (`find_replace`), `numbered` (`format_list_numbered`), `checklist` (`checklist`), `removeformat` (`format_clear`) | Google Material Symbols, <https://github.com/google/material-design-icons> | Apache-2.0 |
| `shortcut1` .. `shortcut9` | Fluent `Star` with a Liberation Sans Bold digit (`../number_badge.py`) | MIT / SIL OFL 1.1 |
| `evernote.png` (ESC program mark) | Simple Icons `evernote`, <https://github.com/simple-icons/simple-icons> (`../brand_marks.py`) | CC0-1.0 |

`fetch_icons.py` prints which source each glyph came from. Labels that name a
shared concept (Copy, Paste, Undo, Bold, ...) are drawn by the shared renderer
instead of the PNG in `icons/` (see the skill, "A label that NAMES a concept").

### The program mark

Evernote's logo is proprietary, and Evernote publishes no icon under a free
licence. The mark is the monochrome elephant from Simple Icons, whose artwork
is CC0-1.0. CC0 covers the copyright only and grants no trademark rights: the
basis is nominative use, the mark names the app this overlay is for, unchanged
and with no endorsement implied (the same basis as the other `brand_marks`
logos). `fetch_icons.py` leaves a committed `evernote.png` as it is.
