# Spotify overlays — sources

`gen_specs.py` writes `bindings.yaml` from one table, and
`scripts/generate_app_overlays.py` renders it; `fetch_icons.py` rebuilds
`icons/`.

| Set | Loads for |
|---|---|
| `spotify_template` (2 files) | Windows (`Spotify.exe`) and Linux (`spotify`) |
| `spotify_template_mac` (3 files) | macOS ("Spotify") |

App names: the Spotify 1.2.95.453 Linux package (`spotify-client` from
repository.spotify.com), run under Xvfb on 2026-10-22, runs as `spotify`,
with WM_CLASS `spotify` / `Spotify` and the window title "Spotify". While a
song plays the title is the artist and song. The Windows and macOS names were
not checked on an install.

## Shortcut reference

Spotify Support, "Spotify keyboard shortcuts",
<https://support.spotify.com/us/article/keyboard-shortcuts/>, read 2026-10-22
with headless Chromium. The page has one table. It gives a separate macOS key
only for shuffle (Option+S; Ctrl+S on Windows), repeat (Option+R; Ctrl+R) and
the search page (Cmd+Shift+L; Ctrl+L). Its "Alt" is Option on a Mac. Linux is
not named; it gets the Windows keys.

The page says its list is not complete ("including (but not limited to)"). The
full list is in the app (Ctrl+/), which needs a signed-in account, so it was
not read.

## Left out

- Space (play/pause), M (mute), and Up, Down, Left, Right alone (list
  navigation, add to library, add to queue): no overlay cell, or they would
  replace the letter legends.
- Ctrl+? (a second key for the shortcut list; the same key as Ctrl+/ with
  Shift).

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- Select all and Settings are drawn by the shared concept renderer.
- ESC: the Spotify logo from Simple Icons (CC0-1.0 artwork,
  <https://simpleicons.org>), used to name the application
  (`../brand_marks.py`).
