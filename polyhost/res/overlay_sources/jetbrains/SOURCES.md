# JetBrains overlay sources

`bindings.yaml` generates three artwork sets, one per default keymap JetBrains
ships:

| Set | Platform | JetBrains keymap |
|---|---|---|
| `jetbrains_template.*` | Windows | `$default` |
| `jetbrains_mac_template.*` | macOS | `Mac OS X 10.5+` |
| `jetbrains_linux_template.*` | Linux | `Default for GNOME` |

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
- The parent chain is applied (GNOME → XWin → `$default`). A child `<action>`
  replaces the parent's shortcuts for that action.
- macOS inherits from `$default` through the Ctrl↔Cmd swap in
  `platform/platform-impl/.../keymap/impl/MacOSDefaultKeymap.kt`, then applies
  its own overrides.
- Commit (Ctrl+K) and Update Project (Ctrl+T) come from
  `platform/vcs-impl/resources/META-INF/VcsActions.xml`. Push (Ctrl+Shift+K) comes
  from `platform/dvcs-impl/resources/intellij.platform.vcs.dvcs.impl.xml`.

Each binding was checked against the resolved keymap for every platform it is
drawn on, and each platform's cells were checked for collisions (2026-09-28,
intellij-community `master`).

## Icons

- **Reclaimed (37)**: the 36 shortcut icons and the ESC mark of the old set, cut
  pixel-for-pixel out of the old PNGs as 72×40 white-on-transparent cells. They
  render 1:1 (`region: [72, 40]`, `anchor: center`), so the Linux set is
  byte-identical to the old overlay on every old cell. There is no other source
  for them. Restore them from git if lost. The five Ctrl+Alt+Shift icons came
  from the shared `overlay_sources/icons/` set via the retired
  `build_extra_layer.py`.
- **Fetched**: Microsoft Fluent UI System Icons (MIT) or Google Material Symbols
  (Apache-2.0). `fetch_icons.py` names each one.
- **Shared concepts**: Save, Undo, Redo, Copy, Cut, Paste, Select all and Replace
  carry no icon. The generator draws them with the shared concept renderer, so
  they are the same bytes as in every other app's overlay.

## Known gaps

- **KDE** runs JetBrains' `Default for KDE` keymap, but the host has one Linux
  set. KDE shares GNOME's Find Usages, Select In, Evaluate and Execution Point
  chords. It differs on Back/Forward (Ctrl+Alt+←/→), Reformat (Alt+Shift+L),
  Stop (Ctrl+2), Toggle Breakpoint (Ctrl+8), View Breakpoints (Ctrl+Shift+8) and
  File Structure (Ctrl+0). A `linux_kde:` mapping branch would need the
  generator to emit a fourth set.
- **Other Linux desktops** run `Default for XWin`. It matches GNOME except Back,
  Forward, Find Usages and Select In, which stay on the `$default` chords there.
- **Rerun** (Ctrl+F5) is not drawn on macOS. Its chord there is ⌘R, which the
  editor gives to Replace.
- Two-stroke chords and double-Shift (Search Everywhere) cannot be drawn on a
  keycap.
