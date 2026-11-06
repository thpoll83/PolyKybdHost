# tmux overlay: sources

One overlay set for tmux (`tmux.yaml` → `tmux_template.mods.png`). Every key
uses no modifier, one modifier or Shift, so one PNG holds the set.

Regenerate:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/tmux/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py polyhost/res/overlay_sources/tmux/tmux.yaml \
    --preview /tmp/tmux_preview
```

## How the keys are drawn: the prefix table

Every tmux command key is a two-step sequence: the prefix, Ctrl+B, then a key.
A keycap shows one key combination, so the set shows the **prefix table**:

- **Ctrl+B** shows "tmux" above "PRFX": the prefix. Pressed twice, it sends
  Ctrl+B to the program in the pane (`send-prefix`).
- **Every other icon** is what the key does when it is pressed **after** the
  prefix, on the layer of the modifiers it is pressed with: `c` (new window)
  on the plain layer, `%` (Shift+5, split) on the Shift layer, Alt+1 (a
  layout) on the Alt layer, Ctrl+O (rotate the panes) on the Ctrl layer.
- Without the prefix the keys type as usual; the firmware's legend stays in
  the top-left corner of each key.

Other sets draw a sequence differently. Logseq and Todoist draw only the
first key of a sequence and name the follow-up letters in the label, and the
Emacs set leaves `C-x` sequences out, because there the second key also has a
meaning of its own that the overlay must show. In tmux nearly every command
is a prefix sequence and the keys have no other tmux meaning, so the
follow-up keys are the useful information. A character that needs Shift on a
US layout is drawn on its key's Shift variant (`%` is Shift+5, `"` Shift+',
`{` Shift+[, `:` Shift+;), as in the nano set.

The composite words: WIN = window, PANE, SESS = session, CLNT = client (one
attached terminal), BUF = paste buffer, VIEW = the visible part of a window
larger than the terminal, SZ1 / SZ5 = resize the pane by 1 or 5 cells.

## Shortcut reference

- **tmux's default key table**: `key_bindings_init()` in `key-bindings.c`,
  https://github.com/tmux/tmux/blob/3.8/key-bindings.c, tag `3.8` (commit
  `7f2a35ad3321f9ba57a1062ca73b1f3ff26aca53`, `$OpenBSD: key-bindings.c,v
  1.193`); read 2026-11-06. The prefix key and the `set-titles` default are
  in `options-table.c` at the same tag (`prefix` = `'b'|KEYC_CTRL`,
  `set-titles` = 0, `set-titles-string` =
  `#S:#I:#W - "#T" #{session_alerts}`).
- **Cross-checks**: the tmux(1) man page at the same tag
  (https://github.com/tmux/tmux/blob/3.8/tmux.1, section DEFAULT KEY
  BINDINGS), and `tmux -f /dev/null list-keys -T prefix` from tmux 3.4 (the
  Ubuntu 24.04 package) run in this container.

Only bindings that are the same in tmux 3.4 and 3.8 are drawn, so the set is
right on the versions current distributions ship.

## The keys

`tmux.yaml` is the key table; each line names the action. 85 keys and the
ESC mark (the key count is from `preview_black.py`).

- **Ctrl** (after the prefix, except Ctrl+B): Ctrl+B prefix, Ctrl+O rotate
  the panes, Ctrl+Z suspend the client, Ctrl+arrows resize the pane by 1.
- **No modifier**: `c` new window, `n` / `p` next and previous window, `l`
  last window, `w` choose a window, `f` find a window, `i` window
  information, `,` rename window, `.` move window, `'` window by index, `0`
  to `9` select that window, arrows select the pane in that direction, `o`
  next pane, `;` last pane, `z` zoom pane, `x` kill pane, `q` show pane
  numbers, `m` mark pane, Space next layout, `d` detach, `s` choose a
  session, `[` copy mode, PgUp copy mode and scroll up, `]` paste buffer,
  `=` choose a paste buffer, `-` delete the paste buffer, Delete makes the
  view follow the cursor, `/` describe a key, `t` clock, `r` redraw.
- **Shift**: `%` split left and right, `"` split top and bottom, `!` break
  the pane into a window, `&` kill window, `$` rename session, `#` list paste
  buffers, `(` / `)` previous and next client, `{` / `}` swap with the pane
  above and below, `:` command prompt, `?` list key bindings, `~` show
  messages, `<` window menu, `>` pane menu, `C` customize options, `D` choose
  a client, `E` spread panes evenly, `L` last client, `M` clear the marked
  pane, Shift+arrows move the view.
- **Alt**: Alt+1 to Alt+5 the five layouts (even-horizontal, even-vertical,
  main-horizontal, main-vertical, tiled, each drawn as its pane picture),
  Alt+N / Alt+P next and previous window with an alert, Alt+O rotate the
  panes back, Alt+arrows resize the pane by 5.

Keys that differ elsewhere: a user's `~/.tmux.conf` can change the prefix
(Ctrl+A is a common choice) and every key; the overlay shows the defaults.
The terminal can take a key before tmux sees it (Windows Terminal: Ctrl+V,
Ctrl+Shift+T); the overlay shows tmux's binding.

## Left out, and why

- **Keys that are new in tmux 3.5 to 3.8** and do nothing on 3.4: `T` change
  the pane title, Tab / Shift+Tab switch to a window or session, `*` new
  floating pane, `@` toggle a floating pane, `g` move a floating pane (and
  its `move` key table), Alt+6 / Alt+7 the mirrored layouts.
- **The copy-mode key tables** (`copy-mode` and `copy-mode-vi`): they act
  only inside copy mode, where the same keys move the cursor and select.
- **The root table**: by default it has only mouse bindings, no keys.
- **The `-r` repeat**: arrows and resize keys can repeat without a second
  prefix for `repeat-time` (500 ms). A keycap cannot show it.

## How the host knows tmux is running

tmux has no plugin that reports to the host, so it is routed by the
terminal's **window title**, like nano (`overlay-mapping.poly.yaml`, the
`tmux` keys in `&editor_titles`, on every terminal entry). The word `tmux`
(or `(tmux)` / `(tmux` for iTerm2, `^tmux` for Nushell) selects the route;
the same `title` regex as nano then requires tmux at the command position:

```
^(?:sudo\s+)?tmux(?:$|\s(?![—:-]\s))|(?:\s[-—:]\s|\(|\]\s|>\s\^?)(?:sudo\s+)?tmux(?:$|\s|\))
```

### The title while tmux runs

tmux's `set-titles` option is **off** by default. tmux then never writes the
outer terminal's title, so the title keeps what the shell or the terminal
wrote when tmux started, for the whole time tmux runs. The titles inside
tmux (a shell's prompt, nano) do not reach the outer terminal.

Checked on a pty with tmux 3.4 and bash 5.2 (Ubuntu prompt
`PS1='\[\e]0;\u@\h: \w\a\]$ '`), starting `tmux new -s work`, running
`nano --version` in it, and detaching with Ctrl+B D:

| setup | titles the outer terminal received |
|---|---|
| shell integration on, `set-titles` off (default) | `tmux … new -s work` when tmux started, nothing while it ran (also with the integration loaded in the shell inside tmux), `user@host: ~/dir` after the detach |
| shell integration off, `set-titles` off | nothing from tmux: the title stays the prompt's `user@host: ~/dir`, so the set does not load |
| shell integration on, `set -g set-titles on` | `work:0:bash - "vm" ` (tmux's `set-titles-string`, which does not name tmux): the set does not load |
| `set-titles on` and `set-titles-string '#T'` | the pane's own title (`vm`, then `nano --version`): the program in the pane loads its own set, the tmux set does not |

So with the integration and the defaults, the keyboard shows the tmux set
for the whole session, including while nano or an AI CLI runs in a pane.
Who wants the program's own set instead sets the two lines of the last row,
as `../nano/SOURCES.md` describes. A vim or emacs mode report takes
priority over the title in both cases.

Title formats by program (only the bash row was read on a pty; the others
are the same formats `../nano/SOURCES.md` lists, with tmux as the command):

| program | title while tmux runs | shows the command without setup |
|---|---|---|
| bash, plain zsh, PowerShell with the script in `res/shell/` | `tmux new -s work` | no: install the shell integration |
| zsh with oh-my-zsh | `tmux new -s work` | yes |
| fish | `tmux ~/s/docs` | yes |
| macOS Terminal.app | `Documents — tmux — 80×24` | yes |
| iTerm2 | `Default (tmux)` | yes |
| Konsole | `~/src : tmux — Konsole` | yes |
| Nushell | `~/docs> tmux` | yes |
| xonsh | `tmux \| me@pc: ~/docs \| xonsh` | yes |

### Platforms

tmux runs on Linux, macOS and other Unix systems, and on Windows inside WSL
(in Windows Terminal, whose entry has the same route; Windows Terminal's own
set is then drawn dimmed under the tmux set). The keys are the same on every
system, and on macOS Ctrl is the Control key, so there is one set and no
`os:` branch. tmux started over SSH on another machine is routed the same way
when the remote shell writes the command into the title (fish does by
default). iTerm2's tmux integration (`tmux -CC`) shows tmux windows as
native iTerm2 tabs and was not considered.

### Titles that do not load the set

Checked in `tests/handler/tmux_routing_test.py`: `user@host: ~/tmux`,
`user@host: tmux`, `man tmux`, `vim .tmux.conf`, `vim tmux`, `cd tmux`,
`ssh host -t tmux a`, Terminal.app or Konsole in a directory named `tmux`,
tmux's own `set-titles-string`.

Missed: tmux started through a wrapper (`env tmux`, a shell alias such as
`ta`, a terminal profile that starts tmux directly, which writes no command
title), and a session resumed with `fg`.

None of the terminal app names was checked on an install.

## Icons

**Esc (program mark)**: the tmux logomark, `logo/icons/128x128/tmux.png` from
the tmux repository at the 3.8 tag
(https://raw.githubusercontent.com/tmux/tmux/7f2a35ad3321f9ba57a1062ca73b1f3ff26aca53/logo/icons/128x128/tmux.png).
`fetch_icons.py` (`_tmux_mark()`) crops it to its opaque pixels and scales
it to 32x32. The dark screen (luma 100 or less) is lit where a pixel is at
least half covered, so the pane split lines stay unlit. The green status bar
is lit on a diagonal hatch ((x + y) % 3 == 0) directly under the screen. Two
pixel fixes follow the trace: the horizontal split runs straight to the right
edge, and the screen's last row is full width, so the bar follows it with no
notch. The rounded corners of the logo stay.

The logo's licence (`logo/LICENSE` in the tmux repository):

```
Copyright (c) 2015, Jason Long <jason@jasonlong.me>

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.
```

This ISC-style licence is compatible with GPL-3.0-or-later.

| file | source | licence |
|---|---|---|
| `tmux.png` | tmux logomark, 1-bit trace | ISC-style, Jason Long (above) |
| `split_h.png`, `split_v.png`, `layout_*.png`, `win0.png` … `win9.png` | drawn in `fetch_icons.py`: a window frame with the panes, or with a title bar and the window number (Liberation Sans Bold) | GPL-3.0-or-later; font SIL OFL 1.1 |
| composites (`win_*`, `pane_*`, `size*_*`, `view_*`, `sess_*`, `client_*`, `buf_*`, `copymode*`, `describekey`, `layout_next`, `layout_even`, `prefix`) | drawn by `../emacs/fetch_icons.py` `composite()`, Liberation Sans Bold for the words | GPL-3.0-or-later; font SIL OFL 1.1 |

### Microsoft Fluent UI System Icons (MIT)

`microsoft/fluentui-system-icons`, `assets/<Folder>/SVG/ic_fluent_<name>_<size>_regular.svg`.

| file | Fluent folder |
|---|---|
| `newwindow.png` | Window New |
| `detach.png` | Plug Disconnected |
| `zoom.png` | Full Screen Maximize |
| `paste.png` | Clipboard Paste |
| `clock.png` | Clock |
| `info.png` | Info |
| `redraw.png` | Arrow Sync |
| `customize.png` | Settings |
| `suspend.png` | Arrow Minimize |
| `listkeys.png` | Question Circle |
| `_history.png` (last window / pane / client) | History |
| `_bullets.png` (list paste buffers) | Text Bullet List |
| `_dismiss.png` (kill) | Dismiss |
| `_rename.png` | Rename |
| `_move.png` | Arrow Move |
| `_delete.png` | Delete |
| `_keyboard.png` | Keyboard |
| `_rotate.png`, `_rotateccw.png` | Arrow Rotate Clockwise, Arrow Rotate Counterclockwise |
| `_bell.png` (window with an alert) | Alert |
| `_copy.png` (copy mode) | Copy |

### Material Symbols (Apache-2.0)

`google/material-design-icons`, Material Symbols Outlined, weight 300.

| file | symbol |
|---|---|
| `command.png` | `terminal` |
| `messages.png` | `chat` |
| `_choose.png` (choose a window, session, client, buffer) | `checklist` |
| `_menu.png` | `menu` |
| `_cycle.png` (next pane) | `cycle` |
| `_center.png` (view follows the cursor) | `center_focus_strong` |
| `_opennew.png` (break pane) | `open_in_new` |
| `_layout.png` | `dashboard` |
