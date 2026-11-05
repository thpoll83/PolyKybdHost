# foobar2000 overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/foobar2000/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/foobar2000/foobar2000.yaml --preview /tmp/foobar2000_preview
```

Both steps are deterministic. A second run leaves every PNG byte-identical.

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
| `foobar2000.png` | Simple Icons `foobar2000` | CC0-1.0 (artwork) |

Fluent: <https://github.com/microsoft/fluentui-system-icons> (MIT). Material
Symbols: <https://fonts.google.com/icons> (Apache-2.0). Both are compatible
with this repository's GPL-3.0-or-later.

## ESC mark

The foobar2000 logo, rendered from Simple Icons
(<https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/foobar2000.svg>,
whose own source is <https://hydrogenaud.io/index.php?topic=55604.0>). The SVG
artwork is CC0-1.0. CC0 grants no trademark rights; the mark is used only to
name the application this overlay is for (nominative use), as with the other
Simple Icons marks in `../brand_marks.py`. It is a committed asset;
`fetch_icons.py` does not fetch it again once it exists.

## Process name

The official installer `foobar2000-x64_v2.26.2.exe` from
<https://www.foobar2000.org/windows> installs `foobar2000.exe` (read
2026-11-05). The mapping key is `foobar2000`. It was not checked against a
running install.
