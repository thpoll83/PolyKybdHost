# Google Meet overlays — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `meet_template` (2 files), `_mac` (3 files) | a browser tab on meet.google.com, or a window title containing "Google Meet" when no URL is known |

Meet has no desktop app, so the set is under the browser entries (Chrome and the
other Chromium browsers, and Firefox through the shared `&web_urls` map). The
title fallback needs "Google Meet": the tab of a running meeting is titled
"Meet - <code>", and the word "Meet" alone is too common to match on.

## Shortcut reference

Google Workspace Learning Center, "Use Meet keyboard shortcuts",
<https://support.google.com/a/users/answer/9896256>, read 2026-10-22 with
headless Chromium. It has a Mac column and a Windows/ChromeOS column; Linux uses
the Windows/ChromeOS keys.

| Action | Windows / Linux | macOS |
|---|---|---|
| Mute or unmute | Ctrl+D | ⌘D |
| Camera on or off | Ctrl+E | ⌘E |
| Present | Ctrl+Alt+T | ⌃⌘T |
| Chat | Ctrl+Alt+C | ⌃⌘C |
| People | Ctrl+Alt+P | ⌃⌘P |
| Raise or lower hand | Ctrl+Alt+H | ⌃⌘H |
| More / fewer participant tiles | Ctrl+Alt+K / J | ⌃⌘K / J |
| Minimize or expand your video | Ctrl+Alt+M | ⌃⌘M |
| Announce the speaker (screen reader) | Ctrl+Alt+S | ⌃⌘S |
| Announce room information (screen reader) | Ctrl+Alt+I | ⌃⌘I |

The page notes that on a keyboard layout other than US English, Ctrl+Alt acts
as AltGr, so the Ctrl+Alt keys may type a character there instead.

### Left out

- `c` and Shift+C (captions), Shift+M (picture-in-picture) and Shift+R
  (reaction sounds): single letters and Shift+letter would replace the letter
  legends while the user types in the chat.
- Space (push to talk): off by default, and the space bar has no overlay cell.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- ESC: the Google Meet mark from Simple Icons (CC0-1.0 artwork,
  <https://simpleicons.org>), used to name the application
  (`../brand_marks.py`).
