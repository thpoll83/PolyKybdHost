# Steam client overlay: sources

Two sets: `steam.yaml` (the desktop client) and `steam_bigpicture.yaml` (Big
Picture mode, chosen by the window title). Rebuild with `fetch_icons.py`, then
`scripts/generate_app_overlays.py` on each spec.

## Shortcuts

Valve publishes no shortcut list for the client. Both sets come from the
client's own UI code, `steamui/sp.js`, as mirrored by SteamDatabase's
SteamTracking repository
(`https://raw.githubusercontent.com/SteamDatabase/SteamTracking/master/ClientExtracted/steamui/sp.js`,
read 2026-11-05).

| Set | Keys | Where in `sp.js` |
|---|---|---|
| Desktop | Ctrl+F find in page | the find bar of a browser view: `key == "f" && ctrlKey` starts `StartFind()` |
| Desktop | Ctrl+Tab or Ctrl+PgDn next chat, Ctrl+Shift+Tab or Ctrl+PgUp previous chat, Ctrl+W close chat | the chat window's `OnHTMLKeyEvent`: `ActivateNextTab`, `ActivatePreviousTab`, `RemoveTab` (key codes 9, 33, 34 from the key-code module) |
| Big Picture | Enter, F1–F4, F6–F9, Shift+F6/F7, Ctrl+F6/F7, Backspace, Ctrl+0–8, Ctrl+Shift+4/5 | the keyboard-to-controller table (`{ strKey: "F1", button: STEAM_GUIDE }` …) used by the keyboard simulator of the gamepad UI |

The Big Picture table matches a Steam Community post of 2024-01-05 that lists
Ctrl+1 as the Steam menu, Ctrl+2 as Quick Access, Ctrl+Backspace as X and Ctrl+8
as Y (`https://steamcommunity.com/discussions/forum/1/4030224579615269667`).

The window title "Steam Big Picture Mode" is the English string
`SP_WindowTitle_BigPicture` in
`ClientExtracted/steamui/localization/steamui_english.json` of the same
repository. In another client language the title is translated, and the
desktop set is shown instead.

Left out:

- Esc is Back (B) in Big Picture mode, but the ESC cell shows the program mark.
- The arrow keys are the D-pad in Big Picture mode.
- Two Ctrl key handlers in the library code (Ctrl+Up and Ctrl+\) whose action
  the minified code does not name.
- The in-game overlay keys (Shift+Tab, F12 screenshot). They act inside the
  game window, which is not the Steam client.

## Icons

| File | Source | Licence |
|---|---|---|
| `find.png` | Fluent UI System Icons, `Search` | MIT |
| `chat.png` | Fluent UI System Icons, `Chat Empty` | MIT |
| `nextchat.png`, `prevchat.png` | `chat.png` with a chevron drawn in `fetch_icons.py` | MIT (base) |
| `closechat.png` | Fluent UI System Icons, `Chat Dismiss` | MIT |
| `quickaccess.png` | Fluent UI System Icons, `More Horizontal` | MIT |
| `viewbutton.png` | Fluent UI System Icons, `Square Multiple` | MIT |
| `menubutton.png` | Fluent UI System Icons, `Navigation` | MIT |
| `btn_*.png` | controller button names drawn in `fetch_icons.py` (Liberation Sans Bold) | drawn here, GPL-3.0-or-later with the repository |
| `steam.png` | Simple Icons, `steam` | CC0-1.0 artwork |

Fluent UI System Icons: `https://github.com/microsoft/fluentui-system-icons`.

The Steam logo is a Valve trademark. The CC0 licence of the Simple Icons
artwork grants no trademark rights; it is used to identify the Steam client
the overlay is for (nominative use), as described in `../brand_marks.py`. It is
the ESC mark of both sets and the icon of the Steam menu keys (F1 and Ctrl+1)
in Big Picture mode, where it shows the Steam button.
