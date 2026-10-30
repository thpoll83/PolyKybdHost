# PolyKybd mode reporter (Vim and Neovim plugin)

Tells PolyKybdHost which **mode** Vim is in, so the keycaps show the keys of
that mode: the motions and operators in Normal mode, the CTRL keys of Insert
mode, the selection commands in Visual mode, the editing keys of the command
line. Without it a terminal shows its own overlay, or the shortcuts the host
finds for it, whatever runs inside.

One plugin for both editors:

- **Vim 8.2.3430 or later, or Vim 9** (the version that added `ModeChanged`),
  built with `+channel` and `+timers` (`:version` lists both). It sends with
  `ch_open()` in raw mode; no Python and no curl.
- **Neovim 0.7 or later.** It sends over a libuv TCP handle (`vim.uv`, or
  `vim.loop` before 0.10).

Tested with Vim 9.1 and Neovim 0.9.5 on Linux, in a terminal. GUI Vim was not
tested.

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), on every mode change,
on focus in and focus out, and as a keep-alive every 3 s while nothing changes:

```json
{ "app": "vim", "url": "vim://insert", "focused": true,
  "pid": 4242, "input_age": 0.4 }
```

- `url` is `vim://<mode>`, from `mode(1)`:

  | `mode(1)` | `url` |
  |---|---|
  | `n` and its variants (`no`, `nov`, `niI`, `nt` ...) | `vim://normal` |
  | `v`, `V`, CTRL-V, and Select mode `s`, `S`, CTRL-S | `vim://visual` |
  | `i`, `ic`, `ix` | `vim://insert` |
  | `R`, `Rv`, `Rc` ... | `vim://replace` |
  | `c`, `cv`, `ce`, `r`, `rm`, `r?`, `!` | `vim://cmdline` |
  | `t` | `vim://terminal` |

- `app` is `"vim"` for Vim and Neovim alike.
- `pid` is the editor's process id and `input_age` the seconds since its last
  key press or cursor move. With several editors open, the host follows the
  one with the most recent input, so the keep-alive of a Vim in another window
  cannot replace the mode of the one you are typing in.
- **Nothing else.** No file name, buffer text or window title.
- `token` is added only if you set one (see below).

On focus out it sends `"focused": false`, and when Vim exits, or you turn the
reporting off, one last report with `"url": null, "focused": false`. A terminal
window with a plain shell then gets the terminal's own overlay again.

The send never blocks the editor: the connect, write and read run in Vim's
channel loop or Neovim's event loop, one request at a time, and if
PolyKybdHost is not running every error is ignored without a message. Only the
last report at exit waits, at most 200 ms.

## Focus events in a terminal

Vim learns that its terminal window lost or got the focus only from the
terminal's focus reporting (the `ESC [ O` / `ESC [ I` sequences). Most
terminals send them when asked, and Vim 9 and Neovim ask on their own:

- **tmux** passes them on only with `set -g focus-events on` in `~/.tmux.conf`.
- **GNU screen** does not pass them on.
- In **Vim** with a terminal it does not recognise as xterm-like, set
  `t_fe` and `t_fd` (`:help t_fe`).

Without focus events Vim keeps reporting "focused" while you work in another
tab of the same terminal. Another terminal APP is not affected: the host uses
a report only while a terminal is the focused application.

## Install

Copy or link the `vim-plugin` folder as a package, or use a plugin manager.

```bash
# Vim
mkdir -p ~/.vim/pack/polykybd/start
cp -r vim-plugin ~/.vim/pack/polykybd/start/polykybd
vim -c 'helptags ~/.vim/pack/polykybd/start/polykybd/doc' -c q

# Neovim
mkdir -p ~/.local/share/nvim/site/pack/polykybd/start
cp -r vim-plugin ~/.local/share/nvim/site/pack/polykybd/start/polykybd
nvim -c 'helptags ~/.local/share/nvim/site/pack/polykybd/start/polykybd/doc' -c q
```

`~/.config/nvim/pack/polykybd/start/polykybd` works for Neovim too. On Windows
the Vim folder is `%USERPROFILE%\vimfiles\pack\polykybd\start\polykybd`.

With a plugin manager, point it at this folder of the PolyKybdHost repository,
for example vim-plug: `Plug 'thpoll83/PolyKybdHost', { 'rtp': 'vim-plugin' }`;
lazy.nvim: `{ dir = "/path/to/PolyKybdHost/vim-plugin" }`.

## Settings

Set these in your vimrc or `init.vim` (`vim.g.polykybd_port = 50164` in
`init.lua`). The port and token are read at each send.

| setting | default | |
|---|---|---|
| `g:polykybd_enabled` | `1` | `0` turns the reporting off; `:PolyKybdToggle` switches it |
| `g:polykybd_port` | `50164` | PolyKybdHost's `browser_report_port` (the receiver the browser extension and the Blender add-on use) |
| `g:polykybd_token` | `''` | only if PolyKybdHost has `browser_report_token` set: the same value |

On the host side it is the `browser_url_detection` /
`browser_report_local_enabled` feature (both on by default).

## Which overlays

The host's mapping routes `vim://<mode>` to one overlay per mode, from Vim's
own command index (`:help index`):
`polyhost/res/overlay_sources/vim/` (`keys.yaml`, `SOURCES.md`). Every
terminal entry has the routes, and so does the entry for GUI Vim (`gvim`,
`macvim`, `neovide`), which shows the Normal mode set until the first report.

An editor in an SSH session cannot reach the host's loopback receiver, so it
reports nothing.
