# kitty overlay: sources

One spec, `bindings.yaml`, with two artwork sets: `kitty_template.*` (Linux;
kitty has no Windows build) and `kitty_template_mac.*` (macOS). Rebuild with
`fetch_icons.py`, then `scripts/generate_app_overlays.py` on the spec.

## Shortcuts

kitty's default shortcuts, read from its source at commit
`da8cac3264241ac2ae667ffe884c45cc0ec54ae5` of
`https://github.com/kovidgoyal/kitty` (read 2026-11-06):

- `kitty/options/definition.py`: every `map(...)` entry. `kitty_mod` is
  `ctrl+shift` (`opt('kitty_mod', 'ctrl+shift', ...)`). Entries with
  `only='macos'` are added on macOS only. The one map with
  `add_to_default=False` (`ctrl+shift+alt+h` "send text") is an example and
  not a default (`kitty/conf/types.py` writes it commented out).
- The same table is the "Keyboard shortcuts" section of kitty's documentation,
  generated from that file (`https://sw.kovidgoyal.net/kitty/conf/`).

In kitty a "window" is a pane inside a tab, and an "OS window" is a desktop
window; the labels keep kitty's words.

| Key (Linux) | Key (macOS) | Action | Drawn as |
|---|---|---|---|
| Ctrl+Shift+C / V | Cmd+C / V | copy, paste | Copy, Paste (shared concepts) |
| Ctrl+Shift+S, Shift+Insert | the same | `paste_from_selection` | Clipboard Arrow Right |
| Ctrl+Shift+O | the same | `pass_selection_to_program` | Open |
| Ctrl+Shift+Up / K, Down / J | Cmd+Up / Down, Cmd+Option+PgUp / PgDn, and K / J | scroll line | Arrow Sort Up / Down |
| Ctrl+Shift+PgUp / PgDn | Cmd+PgUp / PgDn | scroll page | Arrow Circle Up / Down |
| Ctrl+Shift+Home / End | Cmd+Home / End | scroll to top / bottom | Arrow Upload / Download |
| Ctrl+Shift+Z | the same | `scroll_to_prompt -1` | Arrow Circle Up Left |
| Ctrl+Shift+H | the same | `show_scrollback` | Book Open |
| Ctrl+Shift+G | the same | `show_last_command_output` | Document Text |
| Ctrl+Shift+/ | the same | `search_scrollback` | Search |
| Ctrl+Shift+Enter | Cmd+Enter | `new_window` | Add Square |
| Ctrl+Shift+N | Cmd+N | `new_os_window` | Window New |
| Ctrl+Shift+W | Cmd+Shift+D | `close_window` | Dismiss Square |
| Ctrl+Shift+] / [ | the same | next / previous window | Arrow Circle Right / Left |
| Ctrl+Shift+F / B | the same | move window forward / backward | Arrow Forward / Reply |
| Ctrl+Shift+` | the same | `move_window_to_top` | Arrow Up |
| Ctrl+Shift+R | Cmd+R | `start_resizing_window` | Resize |
| Ctrl+Shift+1..9, 0 | Cmd+1..9, Ctrl+Shift+0 | first .. tenth window | Square with the digit |
| Ctrl+Shift+F7 / F8 | the same | `focus_visible_window`, `swap_with_window` | Target, Arrow Swap |
| Ctrl+Shift+Right, Ctrl+Tab / Ctrl+Shift+Left, Ctrl+Shift+Tab | Cmd+Shift+] / [, Ctrl+Tab, Ctrl+Shift+Tab | next / previous tab | Chevron Right / Left |
| Ctrl+Shift+T | Cmd+T | `new_tab` | Tab Add |
| Ctrl+Shift+Q | Cmd+W | `close_tab` | Dismiss Circle |
| - | Cmd+Shift+W | `close_os_window` | Window Multiple |
| Ctrl+Shift+. / , | the same | move tab forward / backward | Arrow Next / Previous |
| Ctrl+Shift+Alt+T | Cmd+Shift+I | `set_tab_title` | Rename |
| Ctrl+Shift+L | the same | `next_layout` | Grid |
| Ctrl+Shift+= / - / Backspace | Cmd+= (and Cmd+Shift+=) / Cmd+- (and Cmd+Shift+-) / Cmd+0 | font size | Font Increase / Decrease, Text Font Size |
| Ctrl+Shift+E | the same | `open_url_with_hints` | Link |
| Ctrl+Shift+P | the same | hints prefix: then F, Shift+F, C, D, L, W, H, N, Y | Cursor Click |
| Ctrl+Shift+A | the same | opacity prefix: then M, L, 1, D | Transparency Square |
| Ctrl+Shift+F11 | Cmd+Ctrl+F | `toggle_fullscreen` | Full Screen Maximize |
| Ctrl+Shift+F10 | the same | `toggle_maximized` | Maximize |
| Ctrl+Shift+U | Cmd+Ctrl+Space | unicode input | Emoji |
| Ctrl+Shift+F2 | Cmd+, | `edit_config_file` | Settings |
| Ctrl+Shift+Delete | Cmd+Option+R | `clear_terminal reset` | Arrow Reset |
| Ctrl+Shift+F5 / F6 | the same | reload / debug config | Arrow Sync, Bug |
| - | Cmd+Option+S | secure keyboard entry | Shield Keyhole |
| - | Cmd+K, Cmd+Option+K, Cmd+L, Cmd+Ctrl+L | clear to start, scrollback, last command, screen | Eraser, Broom, Arrow Undo, Eraser Segment |
| - | Cmd+H, Cmd+Option+H, Cmd+M, Cmd+Q | hide, hide others, minimize, quit | Eye Off, Eye Tracking Off, Arrow Minimize, Power |

On macOS kitty keeps every Ctrl+Shift key. The macOS set draws the Cmd key
where kitty has one for the same action and leaves out the Ctrl+Shift copy.

Not drawn: Ctrl+Shift+Esc (`kitty_shell`), because the ESC key shows the
program mark on every layer. Ctrl+Shift+keypad + and - have no overlay cell.
The second key of the Ctrl+Shift+P and Ctrl+Shift+A sequences is not drawn,
because the overlay cannot show a state after the first key.

## Icons

Shortcut icons: Microsoft Fluent UI System Icons,
`https://github.com/microsoft/fluentui-system-icons` (MIT). The folder name of
each icon is in `fetch_icons.py` (`FLUENT`). `win1.png` .. `win9.png` and
`win0.png` are Fluent `Square` with the digit drawn in by `../number_badge.py`.

## ESC program mark

`icons/kitty.png`: kitty's own logo, `logo/kitty.png` at commit `da8cac32` of
kovidgoyal/kitty. kitty is GPL-3.0 (`LICENSE`), the same licence as this host.

`fetch_icons.py` composites the logo over white, contain-fits it to 32x32 with
LANCZOS and lights luma 128 or darker: the cat's outline with the eyes and the
`>_` prompt cut out. With `program_icon_region: [37, 32]` the generator places
it 1:1. The script writes the mark only when `kitty.png` is missing; delete it
to rebuild it.
