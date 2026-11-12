# Zellij overlay: sources

One spec, `zellij.yaml`, with one artwork set: `zellij_template.mods.png` and
`zellij_template.combo.mods.png`. It serves Linux and macOS. Rebuild with
`fetch_icons.py`, then `scripts/generate_app_overlays.py` on the spec:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/zellij/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/zellij/zellij.yaml --preview /tmp/zellij_preview
```

## Shortcuts

- **Source:** Zellij's default config,
  `zellij-utils/assets/config/default.kdl`, at tag `v0.45.1`
  (commit `efd8fd5a89a20c07a111d248ad7fce53848d2c18`, 2026-08-28):
  `https://github.com/zellij-org/zellij/blob/v0.45.1/zellij-utils/assets/config/default.kdl`.
  `zellij-utils/src/setup.rs` loads this file as the default configuration.
- **How it was read:** Zellij is modal. In Normal mode the keys of the
  `shared_except "locked"` block apply, together with each
  `shared_except "<mode>" "locked"` block that switches to a mode. These are
  the keys drawn here.

| Key | Action in `default.kdl` | Drawn as |
|---|---|---|
| Ctrl+G | `SwitchToMode "Locked"` | Lock mode |
| Ctrl+Q | `Quit` | Quit Zellij |
| Ctrl+P | `SwitchToMode "Pane"` | Pane mode |
| Ctrl+T | `SwitchToMode "Tab"` | Tab mode |
| Ctrl+N | `SwitchToMode "Resize"` | Resize mode |
| Ctrl+S | `SwitchToMode "Scroll"` | Scroll mode |
| Ctrl+O | `SwitchToMode "Session"` | Session mode |
| Ctrl+H | `SwitchToMode "Move"` | Move mode |
| Ctrl+B | `SwitchToMode "Tmux"` | Tmux mode |
| Alt+N | `NewPane` | New pane |
| Alt+F | `ToggleFloatingPanes` | Toggle floating panes |
| Alt+H, Alt+Left | `MoveFocusOrTab "Left"` | Focus left or previous tab |
| Alt+L, Alt+Right | `MoveFocusOrTab "Right"` | Focus right or next tab |
| Alt+J, Alt+Down | `MoveFocus "Down"` | Focus down |
| Alt+K, Alt+Up | `MoveFocus "Up"` | Focus up |
| Alt+I, Alt+O | `MoveTab "Left"`, `MoveTab "Right"` | Move tab left / right |
| Alt+=, Alt+- | `Resize "Increase"`, `Resize "Decrease"` | Increase / decrease pane size |
| Alt+[, Alt+] | `PreviousSwapLayout`, `NextSwapLayout` | Previous / next swap layout |
| Alt+P | `TogglePaneInGroup` | Toggle pane in group |
| Alt+Shift+P | `ToggleGroupMarking` | Toggle group marking |

27 keys, plus the program mark on Esc.

Left out:

- **The keys of the other modes** (Pane, Tab, Resize, Scroll, Search,
  Session, Move, Tmux, Rename). In those modes bare letters and arrows do
  other things (`n` new pane in Pane mode, `x` close tab in Tab mode, ...).
  The window title does not say which mode is active, so the host cannot
  choose a set per mode, and drawing them on the Normal-mode set would show
  wrong actions while you type in a pane. Zellij does not write the mode into
  the title either; a per-mode set would need a Zellij plugin that reports
  the mode, as the Vim plugin does.
- **Locked mode.** With Ctrl+G every key goes to the program in the pane
  except Ctrl+G. The title does not change, so the set stays on the keycaps.
- **Alt++** (`bind "Alt =" "Alt +"`): `+` is Shift+= on a US layout and a key
  of its own on others, so only Alt+= is drawn.
- **Esc and Enter** return to Normal mode from the other modes; Esc shows the
  program mark.
- **Alt+C** (Copy) is commented out in `default.kdl`.

On macOS, Zellij sees Alt only if the terminal sends Option as Meta
(Terminal.app: Settings > Profiles > Keyboard > "Use Option as Meta key";
iTerm2: Profiles > Keys > Left Option key "Esc+"). The Ctrl keys are Control
on both systems. A user who chose another preset at first start (the
"unlock-first" preset, where Ctrl+G must be pressed first) or changed the
keys sees the defaults here.

## How the host knows Zellij is running

Zellij runs inside a terminal and has no plugin that reports to the host, so
the host sees it only in the terminal's **window title**. Zellij writes that
title itself (an OSC 0 sequence from `make_terminal_title()` in
`zellij-utils/src/shared.rs`) for the focused pane, and the format changed:

| Zellij version | title | read from |
|---|---|---|
| up to 0.42.2 | `Zellij (<session>) - <pane title>` | `shared.rs` at v0.38.0, v0.40.1, v0.42.0, v0.42.2 |
| 0.43.0 | `Zellij (<session>) ` with an empty pane title, otherwise the pane title alone | `shared.rs` at v0.43.0 |
| 0.43.1 and later | `<session> \| <pane title>`, or `<session>` with an empty pane title | `shared.rs` at v0.43.1 and v0.45.1 (changelog: "fix: terminal title regression", PR 4352) |

The pane title is the pane's name if it has one, otherwise the title the
program in the pane set (the shell's title, or nano's command line written by
the shell scripts in `polyhost/res/shell/`), otherwise empty. Zellij does not
restore the terminal's title when it exits.

The mapping (`overlay-mapping.poly.yaml`) has two routes, on Windows
Terminal's entry and on the entry for the other terminals:

1. **`titles-contains`** (in the shared `&editor_titles` list), keys
   `Zellij`, `zellij`, `(zellij)`, `(zellij` and `^zellij`, with this
   `title` regex:

   ```
   ^(?:Zellij \(|zellij(?:$|\s(?![—:-]\s)))|(?:\s[-—:]\s|\(|\]\s|>\s\^?)zellij(?:$|\s|\))
   ```

   That is the 0.42 format (`Zellij (` at the start), or `zellij` at the
   command position, as the nano route requires nano (see
   `overlay_sources/nano/SOURCES.md`).
2. **`titles-match`** (`&multiplexer_titles`): a session name that Zellij
   generated, at the start of the title, followed by ` | ` or the end of the
   title. A session started without `-s`/`--session` gets a name
   `<adjective>-<noun>` from the two fixed lists `ADJECTIVES` and `NOUNS` in
   `zellij-utils/src/sessions.rs` (65 words each). `gen_session_regex.py`
   reads both lists at v0.43.1 and v0.45.1 and prints the regex (v0.45.1
   corrected `iguanadon` to `iguanodon`, so both spellings are in it);
   `gen_session_regex.py --check` tells whether the mapping still has it.
   The key is longer than the 1024 characters YAML allows for a plain key, so
   the mapping writes it as an explicit key (`? '...'`).

### Without the shell integration

| situation | title | set loads |
|---|---|---|
| Zellij 0.42 or earlier | `Zellij (work) - user@host: ~` | yes |
| Zellij 0.43.1+, generated session name | `zippy-zebra` or `zippy-zebra \| user@host: ~` | yes |
| Zellij 0.43.1+, named session (`zellij -s work`) | `work \| user@host: ~` | no, except in a terminal that shows the process name (below) |
| Konsole, any version | `~/src : zellij — Konsole` (tab title format `%d : %n`) | yes |
| iTerm2, any version | `Default (zellij)` (session name and job) | yes, if the profile shows the job |
| Terminal.app, any version | `Documents — zellij — 80×24` | yes, if the profile shows the process |
| after Zellij exits | Zellij's last title stays until something writes a new one | yes, until then |

### With the shell integration

The tray's Updates > "Set up the terminal and editors…" (or
`polyctl shell-integration install`) installs the scripts in
`polyhost/res/shell/`. The shell that starts Zellij writes `zellij` (or
`zellij attach work`) into the title, which loads the set until Zellij writes
its own title a moment later. When Zellij exits, the next prompt writes
`user@host: ~/dir`, so the set does not stay on the keycaps. Inside Zellij the
shells in the panes write their command line into the pane title, so the
title is `zippy-zebra | nano notes.txt`. The set still loads for a generated
session name; a named session is still not recognised.

### Zellij and the program in its pane

Zellij reads its Normal-mode keys (Ctrl+P, Ctrl+O, Alt+N, ...) before the
program in the pane does, so the Zellij set is chosen over a program found in
the same title: `Zellij (work) - nano notes.txt` loads Zellij, not nano. A
mode report from the Vim plugin or the Emacs package is still chosen over
Zellij, as it is over every title route. The terminal's own shortcuts stay
dimmed under the Zellij set (`hosted_in_terminal`), except Windows Terminal's
own set, which a `titles-match` route replaces.

### Titles that do not load the set

Checked in `tests/handler/zellij_routing_test.py`: a named session
(`work | user@host: ~/src`, `work`), hyphenated commands (`docker-compose up`,
`git-lfs`), a generated name with more letters (`adamant-aardvarks`), an
adjective not in Zellij's list (`sleepy-tiger | user@host: ~`),
`user@host: ~/zellij`, `vim zellij.kdl`, `vim zellij`, `man zellij`,
`cd zellij`, `Notes about Zellij`.

Remaining false positive: a title some other program chose that starts with
one of Zellij's 4290 generated names (`brave-tiger`), alone or followed by
` | `.

None of the formats was checked on an install. The Zellij formats are read
from its source at the tags above; the Konsole, iTerm2 and Terminal.app
formats are their documented defaults, as for nano.

## Icons

Glyphs are Microsoft Fluent UI System Icons (MIT,
`https://github.com/microsoft/fluentui-system-icons`) and Google Material
Symbols (Apache-2.0, `https://github.com/google/material-design-icons`), both
through `icon_fetch`.

| File | Source |
|---|---|
| `lock.png` | Fluent `Lock Closed` |
| `quit.png` | Fluent `Power` |
| `pane.png` | Fluent `Split Vertical` |
| `tab.png` | Material `tab` |
| `resize.png` | Fluent `Resize` |
| `scroll.png` | Material `height` |
| `session.png` | Material `dns` |
| `move.png` | Fluent `Arrow Move` |
| `floating.png` | Material `picture_in_picture` |
| `newpane.png` | Material `splitscreen_vertical_add` |
| `left.png`, `right.png`, `up.png`, `down.png` | Fluent `Arrow Left` / `Arrow Right` / `Arrow Up` / `Arrow Down` |
| `grow.png`, `shrink.png` | Fluent `Arrow Maximize` / `Arrow Minimize` |
| `layout.png` | Fluent `Board` (only the source of the two composites below) |
| `group.png` | Fluent `Checkbox Checked` |
| `groupmark.png` | Material `checklist` |
| `tableft.png`, `tabright.png` | drawn in `fetch_icons.py`: Material `tab` with an arrow under it |
| `layoutprev.png`, `layoutnext.png` | drawn in `fetch_icons.py`: Fluent `Board` with an arrow under it |
| `tmux.png` | drawn in `fetch_icons.py`: the word "tmux" in DejaVu Sans Bold, 1-bit at 36x32, placed 1:1 |

### Program mark (Esc)

`zellij.png` is the Zellij logo, `assets/logo.png` in the Zellij repository
at tag v0.45.1 (MIT License, "Copyright (c) 2020 Zellij contributors"):
`https://raw.githubusercontent.com/zellij-org/zellij/efd8fd5a89a20c07a111d248ad7fce53848d2c18/assets/logo.png`.
`_zellij_mark()` composites it over white, fits it into 32x32 with LANCZOS,
and lights the pixels with luma 128 or darker: the dark hexagon outlines and
the `>_` prompt, with the coloured segments unlit. Lighting the light pixels
instead fills the hexagon and loses the prompt. The spec places it 1:1
(`program_icon_mode: alpha`, anchor right, region `[37, 32]`, margin 0).

The drawn icons and the mark are guarded: `fetch_icons.py` leaves an existing
PNG as it is. To redraw one, delete it first.
