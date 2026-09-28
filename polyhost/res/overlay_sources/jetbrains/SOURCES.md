# JetBrains overlay sources

`bindings.yaml` generates five artwork sets, one per default keymap JetBrains
ships:

| Set | Platform | JetBrains keymap |
|---|---|---|
| `jetbrains_template.*` | Windows | `$default` |
| `jetbrains_mac_template.*` | macOS | `Mac OS X 10.5+` |
| `jetbrains_gnome_template.*` | Linux, GNOME | `Default for GNOME` |
| `jetbrains_kde_template.*` | Linux, KDE | `Default for KDE` |
| `jetbrains_linux_template.*` | Linux, any other desktop | `Default for XWin` |

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/jetbrains/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/jetbrains/bindings.yaml --preview /tmp/jetbrains_preview
```

## What was wrong before

The previous overlay was one hand-drawn set (GIMP, no `bindings.yaml`) loaded on
every platform, and its chords were the GNOME keymap:

| Action | Old cell (GNOME) | Windows | macOS |
|---|---|---|---|
| Find Usages | Alt+Shift+7 | Alt+F7 | ⌥F7 |
| Back / Forward | Alt+Shift+←/→ | Ctrl+Alt+←/→ | ⌘[ / ⌘] |
| Go to File | Ctrl+Shift+N | Ctrl+Shift+N | ⌘⇧O |
| Settings | Ctrl+Alt+S | Ctrl+Alt+S | ⌘, |
| Run / Debug | Shift+F10 / Shift+F9 | same | ⌃R / ⌃D |

On macOS nearly every cell sat on a Ctrl chord that JetBrains binds to Cmd.

It also had no tool-window row (Alt+1…Alt+0, ⌘1…⌘0) and only 36 shortcuts. The
set now carries about 100 per platform.

## Shortcut source

Every chord comes from the keymap XML in
[JetBrains/intellij-community](https://github.com/JetBrains/intellij-community),
`platform/platform-resources/src/keymaps/`:

- `$default.xml`, `Mac OS X 10.5+.xml`, `Default for XWin.xml`,
  `Default for GNOME.xml`, `Default for KDE.xml`.
- The parent chain is applied (GNOME → XWin → `$default`, and KDE → XWin →
  `$default`). A child `<action>`
  replaces the parent's shortcuts for that action.
- macOS inherits from `$default` through the Ctrl↔Cmd swap in
  `platform/platform-impl/.../keymap/impl/MacOSDefaultKeymap.kt`, then applies
  its own overrides.
- Commit (Ctrl+K) and Update Project (Ctrl+T) come from
  `platform/vcs-impl/resources/META-INF/VcsActions.xml`. Push (Ctrl+Shift+K) comes
  from `platform/dvcs-impl/resources/intellij.platform.vcs.dvcs.impl.xml`.

Each binding was checked against the resolved keymap for every platform it is
drawn on, KDE included, and each set's cells were checked for collisions
(2026-09-28, intellij-community `master`).

## Icons

- **Reclaimed (37)**: the 36 shortcut icons and the ESC mark of the old set, cut
  pixel-for-pixel out of the old PNGs as 72×40 white-on-transparent cells. They
  render 1:1 (`region: [72, 40]`, `anchor: center`), so the GNOME set is
  byte-identical to the old overlay on every old cell. There is no other source
  for them. Restore them from git if lost. The five Ctrl+Alt+Shift icons came
  from the shared `overlay_sources/icons/` set via the retired
  `build_extra_layer.py`.
- **Fetched**: Microsoft Fluent UI System Icons (MIT) or Google Material Symbols
  (Apache-2.0). `fetch_icons.py` names each one.
- **Shared concepts**: Save, Undo, Redo, Copy, Cut, Paste, Select all and Replace
  carry no icon. The generator draws them with the shared concept renderer, so
  they are the same bytes as in every other app's overlay.

## KDE

JetBrains' `Default for KDE` keymap moves 14 of the drawn actions away from the
GNOME chords, mostly off the F-keys and Ctrl+Alt chords KDE Plasma claims:

| Action | GNOME set | KDE set |
|---|---|---|
| Stop | Ctrl+F2 | Ctrl+2 |
| Close tab / Rerun | Ctrl+F4 / Ctrl+F5 | Ctrl+4 / Ctrl+5 |
| Toggle breakpoint / Build | Ctrl+F8 / Ctrl+F9 | Ctrl+8 / Ctrl+9 |
| View breakpoints | Ctrl+Shift+F8 | Ctrl+Shift+8 |
| File structure | Ctrl+F12 | Ctrl+0 |
| Reformat code | Ctrl+Alt+L | Alt+Shift+L |
| Introduce variable | Ctrl+Alt+V | Alt+Shift+V |
| Back / Forward | Alt+Shift+←/→ | Ctrl+Alt+←/→ |
| Select in | Alt+F1, Alt+Shift+1 | Alt+Shift+1 |
| Move line up/down | (unbound) | Alt+Shift+↑/↓ |

In `bindings.yaml` the chord KDE moves away from carries `except: [linux_kde]`
and the KDE chord `only: [linux_kde]`. See `overlay_specification.md` § Linux
desktops.

## Other Linux desktops

XFCE, Cinnamon, MATE and the rest run `Default for XWin`, which is `$default`
plus a few Linux-safe moves (Run to Cursor on Alt+Shift+9, Surround With on
Ctrl+Alt+Shift+B). Against GNOME it keeps Find Usages (Alt+F7), Select In
(Alt+F1), Evaluate (Alt+F8), Show Execution Point (Alt+F10), Back/Forward
(Ctrl+Alt+←/→) and Move Line (Alt+Shift+↑/↓). The plain `linux` set draws that
keymap; `bindings.yaml` gives GNOME's chords `only: [linux_gnome]`.

## Known gaps

- **Rerun** (Ctrl+F5) is not drawn on macOS. Its chord there is ⌘R, which the
  editor gives to Replace.
- Two-stroke chords and double-Shift (Search Everywhere) cannot be drawn on a
  keycap.
