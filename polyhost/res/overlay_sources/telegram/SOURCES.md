# Telegram Desktop overlays — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `telegram_template` (2 files) | `Telegram.exe` on Windows; `telegram`, `telegram-desktop`, `telegramdesktop` or `org.telegram.desktop` on Linux |
| `telegram_template_mac` (3 files) | "Telegram Lite" and "Telegram Desktop" on macOS |

App names: none was checked on an install. Windows reports the executable
(`Telegram.exe`). On Linux the official tarball binary is `Telegram` with
WM_CLASS `TelegramDesktop`, distribution packages install `telegram-desktop`,
and the Flatpak app id is `org.telegram.desktop`.

⚠️ **macOS gets the set only under the names "Telegram Lite" and "Telegram Desktop".** Two different
Mac apps call themselves "Telegram": Telegram Desktop downloaded from
telegram.org (the Qt app these keys come from), and "Telegram" from the Mac App
Store, which is a separate native client with its own keys. The mapping cannot
tell them apart, so the `telegram` entry has only `windows` and `linux`
branches and no default overlay: on macOS a window named "Telegram" matches
nothing and gets generic icons, not Windows keys. The Mac App Store build of
the Qt app is named "Telegram Lite" (`BinaryName` of the `macstore` target in
tdesktop's `Telegram/build/build.sh`) and gets the macOS set, as does a window
named "Telegram Desktop".

## Shortcut reference

Telegram Desktop is GPL-3.0 (<https://github.com/telegramdesktop/tdesktop>,
`dev` branch, read 2026-11-05). The keys are the app's defaults:

- `Manager::fillDefaults()` in `Telegram/SourceFiles/core/shortcuts.cpp`
  (window, search, chat list, folders, pinned chats, archive, contacts, chat
  menu and preview, voice recording);
- the formatting sequences in lib_ui `ui/widgets/fields/input_field.h`
  (<https://github.com/desktop-app/lib_ui>): Ctrl+Shift+X strikethrough,
  Ctrl+Shift+M monospace, Ctrl+Shift+. quote, Ctrl+Shift+P spoiler,
  Ctrl+Shift+N clear formatting, Ctrl+K link; bold, italic and underline are
  Qt's standard sequences.

Qt spells the Cmd key "ctrl" on macOS, so every `ctrl+` default is `CMDCTRL`.
The folder keys use `meta+` on macOS, which is the Control key.

### Choices

- Ctrl+1..8 on Windows and Linux: the folder handler and the pinned-chat
  handler both register the key, and the folder handler is asked first
  (`Dialogs::InnerWidget::setupShortcuts`, `dialogs_inner_widget.cpp`). So
  Ctrl+1..6 is drawn as Folder 1..6, Ctrl+7 as the last folder, and Ctrl+8 as
  pinned chat 8. A user with no folders gets pinned chat N on Ctrl+1..7.
- macOS: Cmd+1..8 is pinned chat 1..8 and Ctrl+1..7 is the folder row.
- Ctrl+R records a voice message while a chat is open (HistoryWidget handles it
  at priority 1). In the chat list the same key marks the selected chat read.
  It is drawn as the microphone.

### Left out

- Media keys (play, pause, stop, previous, next): no cell on the keyboard.
- Support-mode keys (F5, Ctrl+Delete, Ctrl+Insert, Ctrl+Shift+X/C as history
  back and forward): active only for Telegram support staff.
- Ctrl+S (stash the draft) and Ctrl+Shift+D (insert a date): rarely used, and
  the date sequence is registered for only one of the two formatting lists.
- macOS Ctrl+E (copy the selection to the find buffer): a system service, not
  a Telegram command.

## Icons

| File | Source | Licence |
|---|---|---|
| `closewindow`, `closeothers`, `reopenwindow`, `lock`, `quit`, `search`, `nextchat`, `prevchat`, `nextfolder`, `prevfolder`, `saved`, `archive`, `contacts`, `chatmenu`, `chatpreview`, `voice`, `bold`, `italic`, `underline`, `strike`, `mono`, `quote`, `spoiler`, `clearformat`, `link` | Microsoft Fluent UI System Icons (<https://github.com/microsoft/fluentui-system-icons>), names in `fetch_icons.py` | MIT |
| `minimize`, `firstchat`, `lastchat`, `lastfolder` | Material Symbols (<https://github.com/google/material-design-icons>) | Apache-2.0 |
| `folder1..folder6`, `chat1..chat8` | Fluent `Folder` and `Chat Empty` with a Liberation Sans Bold digit (`../number_badge.py`) | MIT (glyph), SIL OFL (font) |
| `telegram.png` (ESC mark) | Simple Icons `telegram` (<https://github.com/simple-icons/simple-icons>) | CC0-1.0 artwork; trademark used nominatively to name the app |
