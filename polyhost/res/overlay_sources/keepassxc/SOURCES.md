# KeePassXC overlay: sources and licences

## Shortcuts

All keys are KeePassXC's defaults at tag `2.8.0` (identical in `develop` on
2026-11-05):

- The shortcut page in the KeePassXC repository:
  `docs/topics/KeyboardShortcuts.adoc`
  (https://github.com/keepassxreboot/keepassxc/blob/2.8.0/docs/topics/KeyboardShortcuts.adoc).
- The source that sets them, read for the keys the page leaves out or gives per
  platform:
  - `src/gui/MainWindow.ui`: the menu shortcuts, including Copy title
    (Ctrl+I), Restore entry (Ctrl+R), Download favicon (Ctrl+Shift+D) and
    Always on top (Ctrl+Shift+A), which the page does not list.
  - `src/gui/MainWindow.cpp`: Ctrl+M / Ctrl+Shift+M, the database tab keys
    (Ctrl+Tab, or Option+Tab on macOS; Ctrl+PgDn / PgUp; tab 1..9 with Ctrl on
    Windows, Cmd on macOS and Alt on Linux), real Ctrl+H for the SSH agent on
    macOS, and F1 / F2 / F3 / F6.
  - `src/gui/entry/EntryView.cpp`: Ctrl+Shift+J jump to group.
  - `src/gui/group/GroupView.cpp`: Ctrl+Down / Ctrl+Up sort groups,
    Ctrl+Shift+PgDn / PgUp next and previous group.

Qt maps the Ctrl in these files to Cmd on macOS, so the bindings use `CMDCTRL`.
Ctrl+F4 (close database) comes from `QKeySequence::Close` and is drawn on
Windows only.

Left out:

- Esc (clear search): the ESC key shows the program mark.
- Ctrl+J in the search field (toggle search help): it acts only while the
  search field has the focus.
- Auto-Type submenu entries without a default key, and every menu action
  without a shortcut.

## Process names

- Windows: `KeePassXC.exe`, matched as `keepassxc`.
- macOS: the app is named `KeePassXC` (`Application::setApplicationName` in
  `src/main.cpp`), matched as `keepassxc`.
- Linux X11: `keepassxc`. Wayland and the Flatpak report the desktop file name,
  which `src/main.cpp` sets to `org.keepassxc.KeePassXC`. Mapping keys are
  matched lowercased.

## Icons

| Files | Source | Licence |
|---|---|---|
| `kp_*.png` except those below | KeePassXC 2.8.0, `share/icons/application/scalable/actions/` and `apps/utilities-terminal.svg` | Apache-2.0 (Pictogrammers Material Design Icons, modified by KeePassXC; see KeePassXC `COPYING`) |
| `kp_agentadd.png`, `kp_agentremove.png` | `kp_terminal.png` with a plus or minus drawn by `fetch_icons.py` | as above |
| `kp_nexttab`, `kp_prevtab`, `kp_nextgroup`, `kp_prevgroup`, `kp_jumpgroup`, `kp_focusgroups`, `kp_focusentries`, `kp_ontop`, `kp_minimize`, `kp_database` | Microsoft Fluent UI System Icons | MIT |
| `kp_db1..kp_db9.png` | `kp_database.png` with a digit (Liberation Sans Bold), `number_badge.py`, digit size 44/96 centred at 64% height so it clears the rim | MIT (glyph), SIL OFL 1.1 (font) |
| `kp_closedb.png` | `kp_database.png` with a bold X drawn by `fetch_icons.py` | MIT |
| `kp_hidewindow.png` (`select_window_off`), `kp_hideuser.png` (`person_off`) | Google Material Symbols | Apache-2.0 |
| `progmark.png` | KeePassXC 2.8.0, `share/icons/application/scalable/apps/keepassxc-monochrome-light.svg` (the monochrome tray icon) | GPL-2 or GPL-3 (KeePassXC `COPYING` lists no separate licence for this file, so the repository licence applies) |

This host is GPL-3.0-or-later, which is compatible with all of these licences.
`fetch_icons.py` rebuilds every file except `progmark.png`, which it leaves as
committed.

## KeePass 2.x (`keepass.yaml`)

The original KeePass shares this icon folder. Its set is built from the same
KeePassXC icons where the action is the same, plus the `kp2_*` icons below.

- **Keys:** KeePass 2.59 source, `KeePass/Forms/MainForm_Functions.cs`: the
  `AssignShortcut` calls and the key handlers `HandleMainWindowKeyMessage`,
  `HandleGroupKeyEvent` and `HandleEntryKeyEvent`. Read from the GitHub mirror
  of the SourceForge releases,
  https://github.com/dlech/KeePass2.x/blob/master/KeePass/Forms/MainForm_Functions.cs.
- **Differences from KeePassXC:** Ctrl+I adds an entry (Ctrl+N is a new
  database), Ctrl+K duplicates an entry, Ctrl+U opens the URL and Ctrl+Shift+U
  copies it, Ctrl+R synchronizes with a file, Ctrl+D compares entries.
- **Linux:** under Mono the move keys are Ctrl+Shift+F5..F8 instead of
  Alt+Home/Up/Down/End (`MonoWorkarounds` 1245), so the Linux set swaps them.
  There is no macOS set.
- **Left out:** Ctrl+Num* and Ctrl+Num/ (expand and collapse groups; keypad keys
  have no cell) and the global auto-type hotkey Ctrl+Alt+A (it works while
  another app has focus, when this overlay is not shown).

| File | Source | Licence |
|---|---|---|
| `kp2_progmark.png` | KeePass 2.x `KeePass/KeePass.ico`, 64 px frame (the 32 px frame is different art) | GPL-2.0-or-later |
| `kp2_openurl`, `kp2_print`, `kp2_sync`, `kp2_syncurl`, `kp2_selectall`, `kp2_copyentries`, `kp2_pasteentries`, `kp2_findgroup`, `kp2_help` | Microsoft Fluent UI System Icons | MIT |
| `kp2_compare`, `kp2_markcompare`, `kp2_movetop`, `kp2_movebottom` | Google Material Symbols | Apache-2.0 |
