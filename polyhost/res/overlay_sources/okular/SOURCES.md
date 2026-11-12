# Okular overlay — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `okular_template` (2 files) | Okular on Linux (`okular`) and the Windows build (`okular.exe`); `org.kde.okular` is the Flatpak id and the Wayland app id |

App names: the Ubuntu package 4:23.08.5 (run under Xvfb on 2026-10-22) runs as
the process `okular`, with WM_CLASS `okular` / `okular` and the window title
"Okular". `org.kde.okular` (Flatpak, Wayland) and the Windows name were not
checked on an install. There is no macOS set: KDE's macOS builds are rare and
their Cmd mapping was not checked.

## Shortcut references

- Okular source, `master` at invent.kde.org/graphics/okular, read 2026-10-22:
  `part/part.cpp` (`Part::setupActions`), `part/pageview.cpp`
  (`PageView::setupActions`), `part/annotationactionhandler.cpp` and
  `shell/shell.cpp`. `Part::setViewerShortcuts` and
  `PageView::setupViewerActions` are the embedded-viewer keys (Okular inside
  another app) and are not used here.
- KDE Frameworks `kconfig/src/gui/kstandardshortcut.cpp` (`master`), for the
  standard actions Okular takes over unchanged: Open Ctrl+O, Save Ctrl+S, Save
  As Ctrl+Shift+S, Print Ctrl+P, Close Ctrl+W, Quit Ctrl+Q, Find Ctrl+F, Find
  Next F3, Find Previous Shift+F3, Go to Line (page) Ctrl+G, Begin Ctrl+Home,
  End Ctrl+End, Document Back/Forward Alt+Shift+Left/Right, Add Bookmark
  Ctrl+B, Preferences Ctrl+Shift+, , Reload F5, Copy Ctrl+C, Select All Ctrl+A,
  Undo Ctrl+Z, Redo Ctrl+Shift+Z, Full Screen Ctrl+Shift+F (Okular adds F11),
  Show Menubar Ctrl+M, Next/Previous Tab Ctrl+Page Down/Up, Zoom In Ctrl+= ,
  Zoom Out Ctrl+-, Actual Size Ctrl+0, Help F1.
- Okular's own keys: Alt+Return properties, F7 sidebar, F6 annotation toolbar,
  Ctrl+Shift+P presentation, Ctrl+J fit window to page, Ctrl+1..6 mouse modes
  (browse, zoom, area selection, text selection, table selection, magnifier),
  Alt+1..9 and Alt+0 annotation tools, Ctrl+Shift+T reopen closed tab.

Every action above was checked to exist in the measured 23.08.5 build (its
action names in `okularpart.so` and `okular`).

## Left out

- Keys that `master` has but 23.08.5 does not: Ctrl+Shift+C (copy without line
  breaks), Ctrl+V (paste annotation), Ctrl+Shift+B (add the current tool to the
  quick annotations) and Shift+Alt+1..9 (switch to tab N). Add them when the
  common distributions ship a release that has them.
- Single letters with no modifier: `/` (find), B (black screen in presentation).
- Keys with no overlay cell or that act only in one place: Space, Shift+Space,
  Shift+Up/Down, Esc, Page Up/Down, the arrows alone.
- The second tab keys Ctrl+] / Ctrl+[ (Ctrl+Page Down/Up are drawn) and the
  second close key Ctrl+Esc.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- Open, Save, Print, Close, Find, Copy, Select all, Undo, Redo, Zoom in and Zoom
  out are drawn by the shared concept renderer.
- ESC: the generic program mark (the app's own icon).
