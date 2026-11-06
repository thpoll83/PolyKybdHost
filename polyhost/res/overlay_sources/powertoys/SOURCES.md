# PowerToys overlays: sources and provenance

Reproducible record for the PowerToys keycap overlays. Re-run `fetch_icons.py`,
then `scripts/generate_app_overlays.py` on `cmdpal.yaml` and on `run.yaml`.

## Which PowerToys windows get a set

Most PowerToys features are global shortcuts that act in whatever window has
focus (Win+Shift+C Color Picker, Win+Ctrl+T Always on Top, Win+Shift+T Text
Extractor, Win+Ctrl+Shift+V paste as plain text, Win+Shift+/ Shortcut Guide).
A per-app set shows only while a PowerToys window has focus, so it cannot show
those. Keycap hints for global shortcuts are drawn by the firmware
(`qmk_firmware` `hints/os_hints.c`), not by this repo.

| window | process | set | why |
|---|---|---|---|
| Command Palette | `Microsoft.CmdPal.UI.exe` | `cmdpal.yaml`, 13 keys | keyboard-driven window with keys that are not visible in the UI (Ctrl+K, Ctrl+Enter, Alt+Left, Alt+Home, Alt+F, Ctrl+P) |
| PowerToys Run | `PowerToys.PowerLauncher.exe` | `run.yaml`, 4 keys | the same kind of window, with a smaller documented key set |
| FancyZones editor | `PowerToys.FancyZonesEditor.exe` | none | opened only to set up a layout; its keys (S, Shift+S, Delete, arrows) act on a focused zone only |
| Keyboard Manager editor | `PowerToys.KeyboardManagerEditor.exe` | none | its fields record the keys you press, so a keycap icon would be wrong |
| Settings | `PowerToys.Settings.exe` | none | no keys of its own |

Windows cuts the process name at its first dot, so the mapping keys are
`microsoft` and `powertoys`. Each entry routes only through `titles-match`
(`^Command Palette( Dev)?$`, `^PowerToys Run$`) and has no overlay of its own,
so every other window under those names, including one with an empty title,
gets nothing. ⚠️ The Command Palette title is translated (resource `AppName`),
so on a Windows that is not set to English the set does not load. The
translations are added at build time and are not in the repository, so they
cannot be listed here.

Both windows have focus only while they are open. The host accepts a window
switch after 500 ms (`NEW_WINDOW_ACCEPT_TIME_MSEC`), so the keys appear when
the user stays in the window, for example to browse results or open the
command menu, and not on a quick launch.

## Shortcuts

### Command Palette (`cmdpal.yaml`)

Microsoft Learn has no keyboard table for Command Palette, so the keys come
from the PowerToys source (microsoft/PowerToys, MIT; read, not redistributed):

- `src/modules/cmdpal/Microsoft.CmdPal.UI/Pages/ShellPage.xaml.cs`:
  Enter (primary action), Ctrl+Enter (secondary action), Ctrl+K (context
  menu), Alt+Left (back), Alt+Home (home page), Ctrl+, (settings), Alt+F
  (filter), Esc (back, or close at the root).
- `src/modules/cmdpal/Microsoft.CmdPal.Common/Helpers/WellKnownKeyChords.cs`:
  Ctrl+Shift+E open file location, Ctrl+Shift+C copy file path,
  Ctrl+Shift+R open in console, Ctrl+Shift+Enter run as administrator,
  Ctrl+Shift+U run as different user, Ctrl+P toggle pin. These work only on a
  result that offers the command (an app or a file).

Not drawn: Up/Down/PageUp/PageDown (list navigation); Alt+1..9 (numbered
results: a setting decides whether the press selects or runs the result, and
the Dock shelf uses the same keys while it is shown); Backspace on an empty
search (goes back only when a setting is on); Alt+Down and Tab (expand the
compact palette).

### PowerToys Run (`run.yaml`)

"General keyboard shortcuts" on https://learn.microsoft.com/windows/powertoys/run
(source file: MicrosoftDocs/windows-dev-docs, `hub/powertoys/run.md`):
Ctrl+Shift+Enter run as administrator, Ctrl+Shift+U run as different user,
Ctrl+Shift+E open containing folder, Ctrl+C copy path. Tab (move through
results) and Esc (close) are not drawn; the program mark is on ESC.

## Icons

PolyKybdHost is GPL-3.0-or-later.

- **Shortcut icons: Microsoft Fluent UI System Icons (MIT)**,
  `microsoft/fluentui-system-icons`, `assets/<Name>/SVG/ic_fluent_<snake>_24_regular.svg`,
  rendered by `icon_fetch.fluent()`:

  | file | Fluent folder | used for |
  |---|---|---|
  | run.png | Play | Enter, run result |
  | secondary.png | Arrow Enter | Ctrl+Enter |
  | more.png | More Horizontal | Ctrl+K |
  | back.png | Arrow Left | Alt+Left |
  | home.png | Home | Alt+Home |
  | settings.png | Settings | Ctrl+, (the shared `settings` concept draws this key) |
  | filter.png | Filter | Alt+F |
  | pin.png | Pin | Ctrl+P |
  | folder.png | Folder Open | Ctrl+Shift+E |
  | copypath.png | Document Copy | Ctrl+Shift+C, Run's Ctrl+C |
  | console.png | Window Console | Ctrl+Shift+R |
  | admin.png | Shield | Ctrl+Shift+Enter (the Windows elevation mark) |
  | otheruser.png | Person Swap | Ctrl+Shift+U |

- **ESC program marks: the apps' own icons from microsoft/PowerToys (MIT).**
  `LICENSE` is MIT; `README.md` and `NOTICE.md` have no trademark terms for
  PowerToys art (NOTICE.md lists third-party components only). Same status as
  the Windows Terminal mark.

  | file | source | frame | conversion |
  |---|---|---|---|
  | cmdpal_progmark.png | `src/modules/cmdpal/Microsoft.CmdPal.UI/Assets/Stable/icon.ico` | 64 | luma, threshold 150 (alpha and t180 fill the bolt into one shape) |
  | powertoys_progmark.png | drawn in `fetch_icons.py` (`_powertoys_mark`) after the PowerToys logo, `src/runner/svgs/icon.ico` | 32 | alpha; a square frame, four bars for the colour stripes, three keys. The icon converted at 1 bit fuses the stripes into one blob |

  Run's own `src/modules/launcher/PowerLauncher/Assets/PowerLauncher/RunAsset.ico`
  was rendered too; its magnifier does not survive the 1-bit conversion, so Run
  uses the PowerToys logo. Neither mark is redrawn once its PNG exists: a re-run
  of `fetch_icons.py` keeps the committed files. Delete a PNG to redraw it.

## Global shortcuts that suit firmware OS hints

For the firmware's `hints/os_hints.c` (Win held), if PowerToys support is
wanted there: Win+Shift+C Color Picker, Win+Shift+T Text Extractor,
Win+Ctrl+T Always on Top, Win+Ctrl+Shift+V paste as plain text,
Win+Shift+/ Shortcut Guide, Win+Alt+Space Command Palette, Win+Ctrl+Shift+M Screen
Ruler, Win+Shift+` FancyZones editor. They are PowerToys defaults, not Windows
defaults, and each can be changed or switched off, so they need an opt-in.
