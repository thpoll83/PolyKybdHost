# Terminal program overlays: sources

Ten overlay sets for programs that run inside a terminal. One icon folder
(`icons/`, written by `fetch_icons.py`) serves all of them.

| spec | program | version the keys were read from | files |
|---|---|---|---|
| `lazygit.yaml` | lazygit | v0.44.1, `pkg/config/user_config.go` | `lazygit_template.mods.png` |
| `htop.yaml` | htop | 3.3.0, `Action.c` | `htop_template.mods.png` |
| `btop.yaml` | btop | 1.3.0, `src/btop_input.cpp` | `btop_template.mods.png` |
| `mc.yaml` | Midnight Commander | 4.8.30, `mc.default.keymap` | `mc_template.mods.png`, `.combo` |
| `yazi.yaml` | Yazi | 0.3.3, `yazi-config/preset/keymap.toml` | `yazi_template.mods.png` |
| `micro.yaml` | micro | 2.0.13, `internal/action/defaults_other.go` | `micro_template.mods.png`, `.combo` |
| `helix.yaml` | Helix | 24.07, `helix-term/src/keymap/default.rs` | `helix_template.mods.png`, `.combo` |
| `less.yaml` | less (and man) | 590, `less -?` | `less_template.mods.png`, `.combo` |
| `k9s.yaml` | k9s | v0.32.5, `internal/view/*.go` | `k9s_template.mods.png` |
| `gdb.yaml` | GDB | 15.1, `gdb.texinfo` and `help <letter>` | `gdb_template.mods.png` |

Each spec's header names the exact files and functions, and what was left out.
Each set covers the program's main view only: lazygit's Files panel, htop's
and btop's process list, Midnight Commander's panels, Yazi's file list,
Helix's Normal mode, k9s's resource list, GDB's prompt.

Regenerate:

```bash
python polyhost/res/overlay_sources/tui/fetch_icons.py
python scripts/generate_app_overlays.py polyhost/res/overlay_sources/tui/<spec>.yaml \
    --preview /tmp/<spec>_preview
```

## How the host knows a program is running

None of these programs has a plugin. The host sees them in the terminal's
**window title**, as for nano and Aider (`../nano/SOURCES.md` has the shell
and terminal title formats, `../aicli/SOURCES.md` the tmux settings).

Each route in `&editor_titles` (`overlay-mapping.poly.yaml`) selects on the
command word (also `(cmd)` and `(cmd` for iTerm2, `^cmd` for Nushell) and then
requires the command at the command position, optionally after `sudo`:

```
^(?:(?:sudo\s+)?(?:cmd)(?:$|\s(?![—:-]\s)))|(?:\s[-—:]\s|\(|\]\s|>\s\^?)(?:(?:sudo\s+)?(?:cmd)(?:$|\s|\)))
```

Command names per route:

- Helix: `hx` and `helix` (Arch and Fedora install it as `helix`).
- less: `less` and `man`. man shows its page through less.
- GDB: `gdb`, `gdb-multiarch`, `gdbtui`, `arm-none-eabi-gdb`,
  `aarch64-linux-gnu-gdb`, `riscv64-unknown-elf-gdb`.

### Titles the programs write themselves

Read by running each program in a pty and recording every OSC 0 / OSC 2
escape it wrote (TERM=xterm-256color).

| program | title written |
|---|---|
| Midnight Commander 4.8.30 | `mc [user@host]:<dir>` |
| Yazi 0.3.3 | `Yazi: <dir>` |
| Vim 9.1 with `set title` | `<file> (<dir>) - VIM`, `<file> + (<dir>) - VIM` when modified |
| Neovim 0.9 with `set title` | `<file> - NVIM` |
| lazygit, htop, btop, micro, Helix, less, man, k9s, GDB (plain and `-tui`) | none |

A program that writes none leaves the shell's title in place, so the shell has
to put the command there (`polyhost/res/shell/`, or the shell's own default on
cmd.exe, Konsole, iTerm2, Nushell and xonsh).

The Vim and Neovim titles load the Normal-mode Vim set. With the plugin
(`vim-plugin/`) installed, its mode report takes priority over the title.

### GDB letter keys

The letter keys of the GDB set are the one-letter abbreviations of its prompt
commands: b break, c continue, d delete, f frame, i info, j jump, k kill,
l list, n next, p print, q quit, r run, s step, t thread, u until, x examine.
They are typed at the `(gdb)` prompt, followed by Enter. GDB writes no title,
so the host cannot tell the prompt from a running program, and the set stays
the same in both states.

The debugger keys use the IDE sets' icons: n is VS Code's step over and s its
step into (whole 72×40 cells, drawn 1:1 as in the IDE sets), u is JetBrains'
run to cursor and p is Visual Studio's QuickWatch. d (delete breakpoints) is
the b icon with an X cut out of its dot (`stamp_delete_breakpoint()` in
`fetch_icons.py`). No IDE set has a thread icon, so t is Material Symbols'
`alt_route`. f (frame) is Material Symbols' `view_day`: one frame between its
neighbours in the stack. Ctrl+L (refresh) is the shared `reload` arrow. Ctrl+X, the leader of the TUI window keys, is a two-pane
window (Fluent `Layout Row Two`) over the word TUI (`tui_key()`).

## Icons

- Microsoft Fluent UI System Icons, MIT licence.
- Material Symbols (`ms:` names in `fetch_icons.py`), Apache-2.0 licence.
- Icons the AI CLI, AI desktop app, nano, VS Code, JetBrains and Visual
  Studio sets already draw are copied byte for byte from their folders, so the icon library stores each one once.
- Program marks: htop, Helix and micro from Simple Icons (CC0), through
  `../brand_marks.py`. GDB's is a page with a folded corner and a "GDB" band
  across it (`gdb_mark()` in `fetch_icons.py`). The others are drawn letter
  frames (`../rect_mark.py`): bt, MC, YZ, LG, K9, LS. Simple Icons' `less` is the CSS preprocessor,
  not the pager, so less uses a letter frame.
