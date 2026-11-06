# Winamp overlay: sources

One spec, `winamp.yaml`, with one artwork set: `winamp_template.*` (Windows).
Winamp 5.x has no macOS or Linux build. Rebuild with `fetch_icons.py`, then
`scripts/generate_app_overlays.py` on the spec.

## Shortcuts

The keys are read from Winamp's own resource file, which defines the default
accelerator tables:

- **Source:** `Src/Winamp/Winamp.rc` of the Winamp source that Llama Group
  published on 2024-09-24 as `github.com/WinampDesktop/winamp`. That repository
  is no longer reachable (HTTP 403 for the repository page, 404 for its raw
  files, read 2026-11-06). The file was read from the mirror
  `https://github.com/csware/winamp`, branch `community`, commit
  `5b91e3f697cb6a484b6a63d4fe529e4e15f6dd19` (2024-09-27):
  `https://raw.githubusercontent.com/csware/winamp/community/Src/Winamp/Winamp.rc`.
- **How it was read:** the file has four `ACCELERATORS` blocks.
  `IDR_ACCELERATOR_GLOBAL` and `IDR_ACCELERATOR_MAIN` are loaded for the main
  window in `Src/Winamp/main_wndproc.cpp` (`Main_OnCreate`; the global table
  with `TRANSLATE_MODE_GLOBAL`, so it acts in every Winamp window).
  `IDR_ACCELERATOR_PL` is loaded by the playlist editor (`Pledit.cpp`) and
  `IDR_ACCELERATOR_EQ` by the equalizer. Each entry is a key, a command id and
  its modifiers. The command ids were matched to the menu text in the same file
  (for example `MENUITEM "Stop w/ fa&deout\tShift+V", WINAMP_BUTTON4_SHIFT`)
  and, where no menu item names one, to its `case` in
  `Src/Winamp/main_command.cpp`.
- **Cross-check:** the Webamp hotkey table
  (`https://docs.webamp.org/docs/features/hotkeys/`, a reimplementation of the
  classic Winamp 2 skin) agrees on Z, X, C, V, B, R, S, L, the arrow keys,
  Ctrl+D, Ctrl+T, Alt+W, Alt+E and Alt+G.

Labels use the menu text in `Winamp.rc` ("Start of list", "Stop after current",
"Jump to time", "Add current as bookmark", "Skin Browser", ...).

| Command id | Key | Drawn as |
|---|---|---|
| `WINAMP_BUTTON1` .. `WINAMP_BUTTON5` | Z, X, C, V, B | Previous, Play, Pause, Stop, Next |
| `WINAMP_REW5S`, `WINAMP_FFWD5S` | Left, Right | Rewind / Forward 5 seconds |
| `WINAMP_BUTTON1_SHIFT`, `WINAMP_BUTTON5_SHIFT` | Shift+Z, Shift+B | Rewind / Forward 5 seconds (`main_buttons.cpp` sends `WINAMP_REW5S` / `WINAMP_FFWD5S`) |
| `WINAMP_VOLUMEUP`, `WINAMP_VOLUMEDOWN` | Up, Down | Volume up / down |
| `WINAMP_FILE_REPEAT`, `WINAMP_FILE_SHUFFLE` | R, S | Repeat, Shuffle |
| `WINAMP_FILE_MANUALPLADVANCE` | Shift+R | Manual playlist advance |
| `WINAMP_FILE_PLAY` | L, Shift+X | Open file |
| `WINAMP_FILE_DIR` | Shift+L, Insert | Open folder |
| `WINAMP_FILE_LOC` | Ctrl+L, Ctrl+X | Open URL |
| `WINAMP_JUMPFILE`, `WINAMP_PE_SEARCH` | J, F3 | Jump to file (both open the same dialog) |
| `WINAMP_REFRESHSKIN` | F5 | Reload skin |
| `WINAMP_BUTTON1_CTRL`, `WINAMP_BUTTON5_CTRL` | Ctrl+Z, Ctrl+B | Start of list, End of list |
| `WINAMP_BUTTON4_SHIFT`, `WINAMP_BUTTON4_CTRL` | Shift+V, Ctrl+V | Stop with fadeout, Stop after current |
| `WINAMP_EDIT_ID3` | Alt+3 | View file info |
| `WINAMP_SELSKIN` | Alt+S | Skin browser |
| `WINAMP_EDIT_BOOKMARKS` | Ctrl+Alt+I | Edit bookmarks |
| global: `WINAMP_MAKECURBOOKMARK` | Ctrl+Alt+B | Add current as bookmark |
| `ID_PE_CLOSE` | Ctrl+F4 | Close window (shows or hides the main window) |
| global: `ID_HELP_HELPTOPICS`, `WINAMP_HELP_ABOUT` | F1, Ctrl+F1 | Winamp Help, About Winamp |
| global: `WINAMP_JUMP` | Ctrl+J | Jump to time |
| global: `ID_PE_OPEN`, `ID_PE_SAVEAS` | Ctrl+O, Ctrl+S | Open playlist, Save playlist |
| global: `WINAMP_OPTIONS_PREFS` | Ctrl+P | Preferences |
| global: `WINAMP_OPTIONS_TOGTIME` | Ctrl+T | Elapsed / remaining time |
| global: `WINAMP_OPTIONS_DSIZE` | Ctrl+D | Double size |
| global: `WINAMP_OPTIONS_WINDOWSHADE_GLOBAL` | Ctrl+W | Windowshade mode (of the focused window) |
| global: `WINAMP_PLGSETUP` | Ctrl+K, Alt+O | Select visualization plug-in (Preferences, visualization page) |
| global: `WINAMP_VISCONF`, `WINAMP_VISPLUGIN` | Alt+K, Ctrl+Shift+K | Configure / start or stop visualization |
| global: `WINAMP_NEXT_WINDOW` | Ctrl+Tab | Next window |
| global: `WINAMP_MAIN_WINDOW`, `WINAMP_OPTIONS_PLEDIT`, `WINAMP_OPTIONS_EQ`, `WINAMP_OPTIONS_VIDEO` | Alt+W, Alt+E, Alt+G, Alt+V | Main window, Playlist editor, Equalizer, Video |
| global: `WINAMP_VIDEO_TOGGLE_FS` | Alt+Enter | Video full screen |
| global: `WINAMP_MAINMENU`, `WINAMP_MINIMIZE`, `WINAMP_FILE_QUIT` | Alt+F, Alt+M, Alt+F4 | Main menu, Minimize, Exit |
| global: `WINAMP_NEW_INSTANCE` | Ctrl+Alt+N | New Winamp instance |

Left out:

- Numeric keypad keys (Numpad 0..9, Decimal; for example Numpad 1 / 3 jump 10
  tracks back / forward): the keypad has no overlay cell.
- `WINAMP_OPTIONS_AOT` (Ctrl+A, Always On Top) and `WINAMP_OPTIONS_EASYMOVE`
  (Ctrl+E, EasyMove): in the playlist editor the same keys are Select all and
  Edit entry, and one overlay serves both windows.
- `WINAMP_BROWSER_ID` (Alt+B) and `WINAMP_OPTIONS_MINIBROWSER` (Alt+T):
  `main_command.cpp` has no `case` for either, and `main_init.cpp` greys out
  the minibrowser menu item, so the action of these keys could not be
  confirmed.
- Esc: the ESC cell shows the program mark.
- The Media Library (`gen_ml`) and the Modern skin (`gen_ff`) are plug-ins
  with their own key handling. Their keys are not in `Winamp.rc` and are not
  drawn.

## Playlist editor

The playlist editor uses its own table, `IDR_ACCELERATOR_PL`, together with
the global table. Most keys match the main window (Z, X, C, V, B, R, S, J,
Left, Right, Ctrl+Z, Ctrl+V, Ctrl+B, Ctrl+X, Shift+Z, Shift+V, Shift+B,
Shift+X, Alt+3, Alt+S). These keys differ, and the overlay shows the main
window's action:

| Key | Main window (drawn) | Playlist editor |
|---|---|---|
| Up, Down | Volume up / down | Move the cursor up / down the list |
| L, Shift+L, Ctrl+L | Open file / folder / URL | Add file / folder / URL to the playlist |
| Insert | Open folder | Add folder |
| Shift+R | Manual playlist advance | not assigned |
| Ctrl+Alt+I | Edit bookmarks | not assigned (Alt+I adds the selection as a bookmark) |

Keys only in the playlist editor, not drawn: Enter (play the selection),
Delete / Ctrl+Delete / Alt+Delete / Ctrl+Shift+Delete (remove, crop, remove
missing files, clear), Space (show the playing file), Home, End, Page Up, Page
Down, Ctrl+A (select all), Ctrl+I (invert selection), Ctrl+N (new playlist),
Ctrl+E and Shift+E (edit entries), Ctrl+F, Ctrl+R (reverse), Ctrl+Shift+1/2/3/R
(sort by title, file name, path; randomize), Alt+Up / Alt+Down (move entries),
Ctrl+Alt+E (file info), Ctrl+Alt+G (generate HTML playlist).

## Process name

Windows: `winamp.exe`. Not checked on a running install.

## Icons

| File | Source | Licence |
|---|---|---|
| `previous, play, pause, stop, next, rewind, forward, startlist, endlist, repeat, openfile, openfolder, openurl, saveplaylist, jumpfile, jumptime, fileinfo, addbookmark, bookmarks, video, fullscreen, closewindow, mainmenu, newinstance, quit, preferences, refreshskin, help, about` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `stopafter, fadeout, volumeup, volumedown, shuffle, manualadv, openplaylist, mainwindow, playlisted, equalizer, windowshade, doublesize, nextwindow, minimize, skins, timemode, visselect, visconfig, vistoggle` | [Material Symbols](https://github.com/google/material-design-icons) (`ms:` names in `fetch_icons.py`) | Apache-2.0 |
| `winamp.png` (ESC mark) | the Winamp logo (winamp.com favicon, through Google's favicon service), fitted into 32x32 and cut at luma 128, dark pixels lit (`_winamp_mark` in `fetch_icons.py`) | Llama Group's mark, used only to name the app |

Alt+M is labelled "Minimize", a concept the shared renderer draws, so its cell
comes from the shared Fluent glyph (`Arrow Minimize`, MIT) and the committed `minimize.png` is not used.

**The ESC mark is the Winamp lightning bolt**: two parallel slanted strokes
with a step between them, about 15x22 lit pixels inside the 32x32 square. The
logo is a Llama Group trademark; it is used only to name the app on its own
key, as the other program marks are.

PolyKybdHost is GPL-3.0-or-later; MIT and Apache-2.0 are GPL-3.0-compatible.
No Winamp source code is copied into this repository; only the key bindings
were read from it.

## Regenerate

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/winamp/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/winamp/winamp.yaml --preview /tmp/winamp_preview
```

`fetch_icons.py` does not redraw `winamp.png` when it already exists in
`icons/`. Delete it first to trace the favicon again.
