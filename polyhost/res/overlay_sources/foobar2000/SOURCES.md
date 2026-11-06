# foobar2000 overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/foobar2000/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/foobar2000/foobar2000.yaml --preview /tmp/foobar2000_preview
```

Both steps are deterministic. A second run leaves every PNG byte-identical
as long as the upstream SVGs are unchanged. The icon sources are fetched from
unpinned branches, so a change there changes the PNG bytes.

## Shortcuts

foobar2000 has nine predefined shortcuts in a fresh installation (v0.9.5 and
later). All of them are local to the foobar2000 window, and the user can change
or remove each one in Preferences > General > Keyboard Shortcuts. Playback keys
(play, pause, next, previous) have no default.

Source: the Hydrogenaudio Knowledgebase, the foobar2000 documentation wiki,
page "Foobar2000:Preferences:Keyboard Shortcuts",
<https://wiki.hydrogenaudio.org/index.php?title=Foobar2000%3APreferences%3AKeyboard_Shortcuts>.
The wiki returned HTTP 403 to this session, so the list was read from that
page's search-result text and checked against two other copies that give the
same nine keys: the Hydrogenaudio forum thread "Default keyboard shortcuts /
mouseclicks list" (<https://hydrogenaudio.org/index.php/topic,101647.0.html>)
and DefKey (<https://defkey.com/foobar2000-shortcuts>). DefKey gives
Properties as `Ctrl+Enter`; the wiki and the forum thread give `Alt+Enter`,
which is what is drawn.

| key | action (wiki wording) |
|---|---|
| Ctrl+F | Edit / Search |
| Ctrl+N | File / New playlist |
| Ctrl+O | File / Open |
| Ctrl+P | File / Preferences |
| Ctrl+S | File / Save playlist |
| Ctrl+U | File / Add location |
| Ctrl+W | File / Remove playlist |
| Alt+Enter | [context] Properties |
| Alt+A | View / Always on Top |

**Checked against the program (2026-11-06).** The default table is stored in
`foobar2000.exe` of the 2.26.2 x64 installer
(<https://www.foobar2000.org/downloads/foobar2000-x64_v2.26.2.exe>, unpacked
with 7-Zip) at file offset 0x439490: 40-byte entries of a key (virtual-key code
plus the Windows HOTKEYF modifier byte) and a command GUID. The GUIDs were named
with `standard_commands` in `SDK/guids.cpp` of the foobar2000 SDK 2026-10-01.
The table has exactly nine entries: Ctrl+P preferences, Ctrl+F playlist search,
Alt+A always on top, Ctrl+N create playlist, Ctrl+W remove playlist, Ctrl+O
open, Ctrl+S save playlist, Ctrl+U add location, and Alt+Enter on a context-menu
command (Properties). No other entry of that layout exists in the executable or
in the bundled components.

The playlist view also reacts to keys such as `Delete` and `Ctrl+A`. They are
not drawn, because no documentation found lists them as defaults.

The macOS build is not covered: its documentation has no default shortcut
list, and a 2025 forum reply says it has no default playback keys either.

## Icons

| file | art | licence |
|---|---|---|
| `search.png` | Fluent `Search` | MIT |
| `newplaylist.png` | Material Symbols `playlist_add` | Apache-2.0 |
| `removeplaylist.png` | Material Symbols `playlist_remove` | Apache-2.0 |
| `openfile.png` | Fluent `Document` (as VLC "Open file") | MIT |
| `saveplaylist.png` | Fluent `Save` (as VLC "Save playlist") | MIT |
| `addlocation.png` | Fluent `Globe` (as VLC "Open network stream") | MIT |
| `preferences.png` | Fluent `Settings` | MIT |
| `properties.png` | Fluent `Info` (as VLC "Media information") | MIT |
| `ontop.png` | Fluent `Pin` | MIT |
| `foobar2000.png` | foobar2000.org favicon, 1-bit trace (`_foobar_mark` in `fetch_icons.py`) | the foobar2000 mark, used only to name the app |

Fluent: <https://github.com/microsoft/fluentui-system-icons> (MIT). Material
Symbols: <https://fonts.google.com/icons> (Apache-2.0). Both are compatible
with this repository's GPL-3.0-or-later.

## ESC mark

The foobar2000 logo (a fox head), traced from the foobar2000.org favicon
through Google's favicon service: fitted into 32x32 and cut at luma 128, so the
dark outline, eyes and mouth are lit. `_foobar_mark` in `fetch_icons.py` draws
it. The mark is used only to name the application this overlay is for, as the
other program marks are. It is a committed asset; `fetch_icons.py` does not
redraw it once it exists, so delete `icons/foobar2000.png` to redraw it.

## Process name

The official installer `foobar2000-x64_v2.26.2.exe` from
<https://www.foobar2000.org/windows> installs `foobar2000.exe` (read
2026-11-05). The mapping key is `foobar2000`. It was not checked against a
running install.
