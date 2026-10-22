# Microsoft Teams overlays — sources

`gen_specs.py` writes two specs from one table, and
`scripts/generate_app_overlays.py` renders them; `fetch_icons.py` rebuilds
`icons/`.

| Spec | Set | Loads for |
|---|---|---|
| `bindings.yaml` | `teams_template` (3 files), `_mac` (4 files) | the desktop app: `ms-teams.exe` / `Teams.exe` on Windows, "Microsoft Teams" (earlier "Microsoft Teams (work or school)", "Microsoft Teams classic") on macOS |
| `web.yaml` | `teams_web_template` (3 files), `_mac` (4 files) | Teams in a browser (teams.microsoft.com, teams.cloud.microsoft, teams.live.com, or a title containing "Microsoft Teams"), and teams-for-linux |

Teams has no Linux desktop app. teams-for-linux (an unofficial app that wraps
the web app) gets the web set. None of the app names was checked on an install.

## Shortcut reference

Microsoft Support, "Keyboard shortcuts for Microsoft Teams",
<https://support.microsoft.com/en-us/office/keyboard-shortcuts-for-microsoft-teams-2e8e2a70-e8d8-4a19-949b-4c36dd5292d2>,
read 2026-10-22 with headless Chromium (plain HTTP gets a 403). Its Windows and
macOS tabs each have a desktop-app column and a web-app column; the four columns
are the four sets. The web keys differ because the browser keeps many Ctrl keys:
Search is Ctrl+E on the desktop and Ctrl+Alt+E on the web, the app bar Ctrl+1..9
and Ctrl+Shift+1..9.

The earlier overlay (2026-06) was built from aggregator sites, and four of its
keys disagree with this page: Ctrl+Shift+C (it drew Start audio call; the page
gives Insert inline code, and Alt+Shift+A for the call), Ctrl+Shift+U (Start
video call; the page gives Toggle speaker, and Alt+Shift+V for the call), Ctrl+O
(Attach file; the page gives Open in new window, and Alt+Shift+O to attach) and
Ctrl+Shift+P (Background blur; not on the page). They follow the page now.

- **App bar 1..9.** Ctrl+N opens the Nth app of the user's own app bar, and the
  page itself gives the calendar as both the 3rd and the 4th app, so the keys show
  the number, not an app.
- **Chat tabs 1..9.** Alt+1..9 (Control+1..9 on macOS) open the Nth tab of a chat
  header; in the calendar the same keys show 1..7 days. The set shows the chat
  meaning.
- **macOS clash.** Option+Cmd+Left/Right pans shared content and also moves the
  calendar to the previous/next period; the set shows the calendar meaning.

### Left out

- Keys the page itself gives two meanings in one column: web Alt+N (New chat and
  Schedule meeting; drawn as New chat), web Alt+Shift+A (Accept video call and
  Start audio call; drawn as Start audio call), macOS Cmd+Shift+A (Accept audio
  call and Toggle live captions; drawn as Accept audio call), macOS Shift+Cmd+T
  (Pin window and Focus toast; drawn as Pin window), and Accept/Decline screen
  share (the call keys).
- Keys on Esc (Close, Shift+Esc Mark all read): the ESC key carries the program
  mark. Enter, Delete, Tab, Shift+Tab, Shift+Enter, `?` and the calendar
  dialog's keys.
- Win+Shift+Y (focus notification), the screen-reader announcement keys, the
  debug log key (Ctrl+Alt+Shift+1), the calendar "Show N days" keys (the chat-tab
  keys), and Alt+/ (the second Keyboard shortcuts key).

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>: the `MS_ICONS` paths in
  `fetch_icons.py`.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: every `ms:`
  entry in `MORE`.
- `app1..app9.png`: Fluent `Square` with a digit; `tab1..tab9.png`: Material
  `chat_bubble` with a digit, both from `../number_badge.py`.
- Bold, Italic, Underline, Cut, Copy, Paste, Undo, Select All, Zoom In and Zoom
  Out are drawn by the shared concept renderer.
- Program icon (ESC, desktop sets): `teams_logo.png`, a generic mark drawn by
  `_draw_teams_logo()` (no Microsoft logo). The web set has none: in a browser
  the host draws the browser's mark.
