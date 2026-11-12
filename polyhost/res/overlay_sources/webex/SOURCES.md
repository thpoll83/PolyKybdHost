# Cisco Webex overlays — sources

`gen_specs.py` writes two specs from one table, and
`scripts/generate_app_overlays.py` renders them; `fetch_icons.py` rebuilds
`icons/`.

| Spec | Set | Loads for |
|---|---|---|
| `app.yaml` | `webex_template` (3 files), `_mac` (4 files) | the Webex App: `CiscoCollabHost` on Windows and Linux, "Webex" on macOS |
| `meetings.yaml` | `webex_meetings_template` (3 files), `_mac` (4 files) | the older Webex Meetings desktop app: `atmgr` on Windows, "Cisco Webex Meetings" / "Webex Meetings" on macOS |

App names: the Webex App 46.10.0.36042 Linux package (`Webex.deb`, run under
Xvfb on 2026-10-22) runs as `CiscoCollabHost`, and its desktop file starts
`/opt/Webex/bin/CiscoCollabHost`. Its window has the title "Webex" and an empty
WM_CLASS. The Windows, macOS and Webex Meetings names were not checked on an
install.

The Webex App has one set for all its windows: Cisco gives no window titles, and
the meeting window was not opened (it needs an account).

## Shortcut references

- Cisco Webex Help Center, "Webex App | Keyboard navigation and shortcuts"
  (article 7wr87q, 2026-03-07),
  <https://help.webex.com/en-us/article/7wr87q>, read 2026-10-22 with headless
  Chromium. It has a Mac and a Windows column for general, messaging, meeting
  and calling, and formatting keys. Its meeting keys apply to the Webex Suite
  meeting platform. The Linux client is not in the article; it gets the Windows
  keys.
- Cisco Webex Help Center, "Accessibility features for meetings and webinars"
  (article 84har3),
  <https://help.webex.com/en-us/article/84har3>, read 2026-10-22: the Windows
  and Mac tabs of "Default keyboard shortcuts" for the Webex Meetings desktop
  app.

### Left out

- Keys the system or every app owns: Cmd+Q, Cmd+W, Cmd+M, Cmd+H, Option+Cmd+H,
  Alt+F4, Ctrl+Q (quit), and the window keys (Command+Up/Down on Windows, as
  printed).
- Keys with no overlay cell or that act only in one dialog: Tab, Shift+Tab,
  Enter, Shift+Enter, Shift+F10, Esc, F6, Ctrl+Tab, Shift+Up (edit the last
  message), PgUp and PgDn (slides), Shift+A (focus the captions menu).
- Webex App, Mac: ⌃⌘- ("Zoom application window"), ⌘N ("Maximizes the
  window") and ⌃⌘K ("Set local share control keywindow"), whose meanings are
  unclear.
- Webex Meetings: the panel sizes (Ctrl+2..5), the Mac zoom levels (⌘1, ⌘2, ⌘4),
  the whiteboard font size and pointer keys, and Mac "Open meeting settings",
  whose key is cut off on the page ("Command +").
- Webex Meetings, Mac: ⌥⌘W is listed twice, for "Close a shared file or
  whiteboard" and for the interpretation dialog, so neither is drawn.

### Choices

- Webex App, Windows: Ctrl+Shift+Y opens the reactions panel; the page gives
  Ctrl+Alt+Y for reloading a space, so the two do not clash.
- Ctrl++ and Ctrl+- enlarge the messages or the shared content; they are drawn
  as the shared Zoom in and Zoom out concepts.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- Bold, Italic, Underline, Zoom in, Zoom out, Undo and Redo are drawn by the
  shared concept renderer.
- ESC: the Webex mark from Simple Icons (CC0-1.0 artwork,
  <https://simpleicons.org>), used to name the application
  (`../brand_marks.py`).
