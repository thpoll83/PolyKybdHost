# DBeaver overlays — sources

`gen_spec.py` writes `bindings.yaml` from one table, and
`scripts/generate_app_overlays.py` renders it; `fetch_icons.py` rebuilds
`icons/`.

| Set | Loads for |
|---|---|
| `dbeaver_template` (3 files), `_mac` (3 files), `_linux` (3 files) | `dbeaver.exe` on Windows, "DBeaver" on macOS, DBeaver on Linux (see below) |

The Linux set differs from the Windows set in two keys: Commit and Rollback are
Ctrl+4 and Ctrl+8 on Linux and macOS, Ctrl+Alt+Shift+K and Ctrl+Alt+Shift+R on
Windows.

## App names

DBeaver CE 26.2.3 (`dbeaver-ce-latest-linux.gtk.x86_64.tar.gz`, run under Xvfb
on 2026-10-22): the launcher process is `dbeaver`, but every window belongs to
the bundled JVM, process `java`, with WM_CLASS `DBeaver` / `DBeaver` and the
title "DBeaver <version> - <workspace or editor>". On X11 the host reads the
process name (`ps -o comm=`), so it sees `java`. The mapping's `java` entry
sends a Linux window whose title starts with "DBeaver" to the DBeaver Linux set
and every other `java` window to the JetBrains set, as before. On KDE
(resourceClass) and GNOME (wm_class) the name is the WM_CLASS. The Windows and macOS names were not checked on an install.

## Shortcut references

- The key bindings in the `plugin.xml` of every `org.jkiss.dbeaver.*` plugin
  of DBeaver CE 26.2.3 (119 bindings in the default scheme). These are the
  keys the app registers. Eclipse writes `M1` for Ctrl on Windows/Linux and Cmd
  on macOS (here `CMDCTRL`); a literal `CTRL` is Control on macOS too, so most
  DBeaver keys are the same on every platform. `platform="cocoa"` / `"gtk"` /
  `"win32"` lines give the per-platform keys (Commit, Rollback, Database tools,
  Execute statement).
- DBeaver Documentation, "Shortcuts", <https://dbeaver.com/docs/dbeaver/Shortcuts/>,
  read 2026-10-22 with headless Chromium. It is the source for the Eclipse
  platform keys that are not in DBeaver's plugins: Save, Save all, Close, Close
  all, New, Find, Rename (F2), Refresh (F5), Properties, Find actions, Key
  assist, Search, Open item, Maximize view, next/previous editor and tab,
  Back, Forward and Full screen.

### Choices

- Ctrl+Enter is "Execute statement" in the SQL editor and "Open recent script"
  in the navigator; it is drawn as Execute statement.
- Ctrl+S is "Save" in an editor and "Apply data changes" in a result set; it is
  drawn as Save.
- Ctrl+Shift+E is "Explain execution plan" in the SQL editor and Eclipse's
  "Switch to editor" on Windows/Linux; it is drawn as Explain plan.

### Left out

- Keys with two meanings the set cannot tell apart: Ctrl+D (copy the value from
  the row above in a result set; delete the line in a text editor) and Ctrl+L.
- Keys without a modifier or a cell: Enter, Esc, Tab, Delete, the arrow keys.
- The ER diagram, Visual Query Builder, Run/Debug, Git and Oracle keys, the
  "Keyboard Only" key scheme, the Ctrl+Alt+F2..F6 result panels and the text
  editor line keys.
- Cut, Copy, Paste, Undo, Redo and Select all: the standard editing keys.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- Save, Close, New and Find are drawn by the shared concept renderer.
- ESC: the DBeaver mark from Simple Icons (CC0-1.0 artwork,
  <https://simpleicons.org>), used to name the application
  (`../brand_marks.py`).
