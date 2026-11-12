# Logic Pro overlay — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `logicpro_template_mac` (4 files) | Logic Pro on macOS |

Logic Pro is a macOS app, so every binding is `only: [macos]` and no Windows
set is written; the mapping entry's top-level overlay is the macOS set, as for
Safari. App names: "Logic Pro" (the bundle name since 10.8) and "Logic Pro X"
(older installs). Not checked on an install. On macOS the host also reads
every menu shortcut of the focused app, and those fill each key this set
leaves free.

## Shortcut reference

Apple, Logic Pro User Guide for Mac, "Key command tables" (the U.S. default
preset), read 2026-11-12:

- Global Commands, <https://support.apple.com/guide/logicpro/global-commands-lgcp02bf31b6/mac>
- Various Windows, <https://support.apple.com/guide/logicpro/various-windows-lgcp665bbccc/mac>
- Main Window Tracks and Various Editors, <https://support.apple.com/guide/logicpro/main-window-tracks-and-various-editors-lgcpe8314fe2/mac>
- Views Showing Time Ruler, <https://support.apple.com/guide/logicpro/views-showing-time-ruler-lgcp267f63a1/mac>
- Main Window Tracks, <https://support.apple.com/guide/logicpro/main-window-tracks-lgcpb99be9c5/mac>

Command is GUI, Option is ALT, Control is CTRL. Apple's "Delete" is the
key labelled delete on a Mac keyboard (Backspace), and "Return" is Enter.

The tables list several hundred defaults. The set has the Tracks area and the
global keys that a user reaches without a dialog. Where one key has a
meaning in several areas, the Tracks area meaning is drawn (for example Left
and Right select the previous/next region).

### Left out

- Numeric keypad keys (no cell): Enter (Play), . (Pause), 0 (Stop), * (Record
  toggle), = (Skip Cycle), the Go to Marker Number keys, Toggle Replace.
- Keys that act only in an editor window: the Piano Roll, Score, Event List,
  Step Sequencer, Audio File Editor and Smart Tempo Editor tables were not
  read; the Various Editors table (Select Same Channels, Trim Note End, ...)
  is not drawn.
- Global keys left out to keep one meaning per cell: the Screenset 1x..9x
  keys (Control-1..9 recall screensets 11..19), Control-Shift-1..9 (Toggle Hide
  Group), Control-Option-1/0 and the other Set Nudge Value keys, the automation
  mode keys (Control-Command-O/A, Control-Shift-Command-O/R/T/L), the take folder
  and comping keys, the track alternative keys, the global track show/hide keys
  (Shift-Command-A/K/O/T/C/B), the punch locator keys
  (Control-Option-Command-I/O), the zoom slots (Control-Option-Command-1..3),
  Page Up/Down, Home and End, Option-Page Up/Down, Tab and Shift-Tab, the
  Equal Sign and Hyphen parameter keys, Command-Grave Accent (system window
  cycling), Command-H, Option-Command-H, Command-M, Option-Command-M,
  Control-Command-M.
- Esc: the ESC key shows the program mark, which the host draws.

## Icons

- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: every `ms:`
  entry in `fetch_icons.py`.
- Byte-identical copies of the icons another DAW set draws for the same
  action (`BORROW` and `RENAMED` in `fetch_icons.py`), from `../ableton`,
  `../reaper`, `../flstudio`, `../protools`, `../soundcraft`, `../cubase` and
  `../garageband`. Their sources and licences are in those folders'
  `SOURCES.md`.
- `screenset1..9.png`: the Ableton set's Fluent `Square` (MIT) with a digit,
  from `../number_badge.py`; 1..8 are byte-identical to Ableton's `track1..8`.
- New, Open, Save, Save as, Close, Quit, Undo, Redo, Cut, Copy, Paste, Select
  all, Help, Zoom in and Zoom out are drawn by the shared concept renderer.

**ESC mark.** None is baked in. Logic Pro is proprietary Apple software, so
the host draws the mark for the running app (the icon from its bundle first,
then the icon catalogs; neither Simple Icons nor Material Design Icons has a
Logic Pro mark).
