# WezTerm overlay: sources

One spec, `bindings.yaml`, with two artwork sets: `wezterm_template.*`
(Windows and Linux) and `wezterm_template_mac.*` (macOS). Rebuild with
`fetch_icons.py`, then `scripts/generate_app_overlays.py` on the spec.

## Shortcuts

WezTerm's default key assignments, read from its source at commit
`e68a8ec27727fbbda15e07f0a0737cd5e16481f6` of `https://github.com/wez/wezterm`
(read 2026-11-06):

- `wezterm-gui/src/commands.rs`: `compute_default_actions()` lists the default
  actions, each `CommandDef` names its keys, and `permute_keys()` adds a
  Ctrl+Shift copy of every SUPER key (and the US-shifted character for a key
  such as `'` -> `"`). `HideApplication`, `QuitApplication` are macOS only, the
  primary-selection copy and paste are not on macOS.
- Checked against `docs/config/default-keys.md` at the same commit
  (`https://github.com/wez/wezterm/blob/e68a8ec27727fbbda15e07f0a0737cd5e16481f6/docs/config/default-keys.md`),
  which is the same table.

| Key (Windows/Linux) | Key (macOS) | Action | Drawn as |
|---|---|---|---|
| Ctrl+Shift+C / V | Cmd+C / V | `CopyTo`, `PasteFrom` Clipboard | Copy, Paste (shared concepts) |
| Ctrl+Insert, Shift+Insert | - | primary selection copy / paste | Copy Select, Clipboard Arrow Right |
| Ctrl+Shift+N | Cmd+N | `SpawnWindow` | Window New |
| Ctrl+Shift+T | Cmd+T, Cmd+Shift+T | `SpawnTab` (current pane domain / default domain) | Tab Add |
| Ctrl+Shift+W | Cmd+W | `CloseCurrentTab` | Dismiss Square |
| Ctrl+Shift+1..8, 9 | Cmd+1..8, 9 | `ActivateTab` 0..7, last | Tab with the digit, Arrow Download |
| Ctrl+Tab, Ctrl+PgDn / Ctrl+Shift+Tab, Ctrl+PgUp | the same, plus Cmd+Shift+] / [ | `ActivateTabRelative` | Chevron Right / Left |
| Ctrl+Shift+PgUp / PgDn | the same | `MoveTabRelative` | Arrow Previous / Next |
| Shift+PgUp / PgDn | the same | `ScrollByPage` | Arrow Circle Up / Down |
| Ctrl+= / - / 0 | Cmd+= / - / 0 | font size | Font Increase / Decrease, Text Font Size |
| Alt+Enter | Option+Enter | `ToggleFullScreen` | Full Screen Maximize |
| Ctrl+Shift+R | Cmd+R | `ReloadConfiguration` | Arrow Sync |
| Ctrl+Shift+K | Cmd+K | `ClearScrollback` | Broom |
| Ctrl+Shift+F | Cmd+F | `Search` | Search |
| Ctrl+Shift+P | the same | `ActivateCommandPalette` | Apps List |
| Ctrl+Shift+X | the same | `ActivateCopyMode` | Highlight |
| Ctrl+Shift+Space | the same | `QuickSelect` | Lasso |
| Ctrl+Shift+U | the same | `CharSelect` | Emoji |
| Ctrl+Shift+L | the same | `ShowDebugOverlay` | Bug |
| Ctrl+Shift+Z | the same | `TogglePaneZoomState` | Arrow Expand |
| Ctrl+Shift+arrows | the same | `ActivatePaneDirection` | Arrow Up / Down / Left / Right |
| Ctrl+Alt+Shift+' (") | the same | `SplitVertical` (top/bottom) | Split Horizontal |
| Ctrl+Alt+Shift+5 (%) | the same | `SplitHorizontal` (left/right) | Split Vertical |
| Ctrl+Alt+Shift+arrows | the same | `AdjustPaneSize` | Resize |
| - | Cmd+M, Cmd+H, Cmd+Q | `Hide`, `HideApplication`, `QuitApplication` | Arrow Minimize, Eye Off, Power |

On Windows and Linux WezTerm also binds the SUPER (Win) form of every key in
the macOS column. The desktop takes most Win+letter keys, so those are not
drawn. On macOS the Ctrl+Shift copies of the Cmd keys also work; the macOS set
draws only the Cmd key.

Not drawn: `ShowLauncher` and `ShowTabNavigator` have no default key. The
Copy and Paste keys of some keyboards have no overlay cell.

## Icons

Shortcut icons: Microsoft Fluent UI System Icons,
`https://github.com/microsoft/fluentui-system-icons` (MIT). The folder name of
each icon is in `fetch_icons.py` (`FLUENT`). `tab1.png` .. `tab8.png` are
Fluent `Tab` with the digit drawn in by `../number_badge.py`.

## ESC program mark

`icons/wezterm.png`: WezTerm's own icon, `assets/icon/terminal.png` at commit
`e68a8ec2` of wez/wezterm. WezTerm is MIT licensed (`LICENSE.md`, Copyright
2018-Present Wez Furlong), which is compatible with this GPL-3.0-or-later host.

The icon is a dark tile with a blue "$W". The tile has luma 24..55 and the
glyph 88..95, with no pixels between 56 and 87. Composited over white, the mark
lights luma 72 or darker: the tile is lit with its rounded corners and the "$W"
is cut out of it. `fetch_icons.py` contain-fits it to 32x32 with LANCZOS and
thresholds it; with `program_icon_region: [37, 32]` the generator places it 1:1.
The script writes the mark only when `wezterm.png` is missing; delete it to
rebuild it.
