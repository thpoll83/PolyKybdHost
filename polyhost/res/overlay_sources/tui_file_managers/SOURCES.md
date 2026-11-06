# yazi, ranger and lf overlays: sources

Three overlay sets for three terminal file managers, one per program, with one
shared icon folder:

| spec | output | platforms | keys + ESC mark |
|---|---|---|---|
| `yazi.yaml` | `yazi_template.mods.png` | Windows, macOS, Linux | 75 + mark |
| `ranger.yaml` | `ranger_template.mods.png` | macOS, Linux | 92 + mark |
| `lf.yaml` | `lf_template.mods.png` | Windows, macOS, Linux | 54 + mark |

Regenerate:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/tui_file_managers/fetch_icons.py
for s in yazi ranger lf; do
  .venv/bin/python scripts/generate_app_overlays.py \
      polyhost/res/overlay_sources/tui_file_managers/$s.yaml --preview /tmp/${s}_preview
done
```

A second run of `fetch_icons.py` and the generator changes no bytes.

## Where the keys come from

All three are read from the program's own source at its newest release tag.

| program | file | release | commit |
|---|---|---|---|
| yazi | [`yazi-config/preset/keymap-default.toml`](https://github.com/sxyazi/yazi/blob/8dd895c695a5950330c2623eb43debf323b60654/yazi-config/preset/keymap-default.toml), section `[mgr]` | v26.9.1 | `8dd895c695a5950330c2623eb43debf323b60654` |
| ranger | [`ranger/config/rc.conf`](https://github.com/ranger/ranger/blob/55fc2839f693aed9486d211694d7317d78161341/ranger/config/rc.conf), the `map` and `copymap` lines | v1.9.4 | `55fc2839f693aed9486d211694d7317d78161341` |
| lf | [`opts.go`](https://github.com/gokcehan/lf/blob/5b6c393d547970a264bd4f0a78fd6513227f8e10/opts.go) (`init()`, the Normal mode `nkeys`), [`os.go`](https://github.com/gokcehan/lf/blob/5b6c393d547970a264bd4f0a78fd6513227f8e10/os.go) and `os_windows.go` (`setDefaults()`: `e`, `i`, `w`, F1), checked against the command list in [`doc.md`](https://github.com/gokcehan/lf/blob/5b6c393d547970a264bd4f0a78fd6513227f8e10/doc.md) | r42 | `5b6c393d547970a264bd4f0a78fd6513227f8e10` |

Only the main browsing view is drawn. The other views have their own key maps
and no window title of their own, so the host cannot tell them apart: yazi's
task list, input box and help (`[tasks]`, `[input]`, `[help]`); ranger's pager,
task view and console (`pmap`, `tmap`, `cmap`); lf's Visual mode (`vkeys`, which
differs from Normal mode only in Esc, `V` and `o`) and command line (`cmap`).

The programs write a key as typed, so an upper-case letter is Shift + that
letter, and a shifted character is drawn on its key's Shift variant on a US
layout (`?` = Shift+/, `:` = Shift+;, `~` = Shift+`, `"` = Shift+', `$` =
Shift+4, `{` = Shift+[).

### Single keys and sequences

All three use sequences of two keys (`gg`, `yy`, `dd`, `cw`, `zh`). A keycap
can show only one key, so:

- A **single key** is drawn with its action.
- The **first key of a sequence** is drawn only when every default sequence
  that starts with it does one kind of thing; its label ends in "...". Where
  the sequences that start with a key do different kinds of things, the key
  is left blank.
- A key that is both a single key and the first key of a sequence does not
  occur in the defaults of these three programs.

| program | key drawn as a group | sequences |
|---|---|---|
| yazi | `g` Go to... | `gg` top, `gh` home, `gc` ~/.config, `gd` ~/Downloads, `gt` trash, `g Space` jump, `gf` follow symlink |
| yazi | `m` Linemode... | `ms` `mp` `mb` `mm` `mo` `mn` |
| yazi | `c` Copy path... | `cc` path, `cC` URL, `cd` directory, `cD` directory URL, `cf` file name, `cn` name without extension |
| yazi | `,` Sort... | `,m` `,M` `,b` `,B` `,e` `,E` `,a` `,A` `,n` `,N` `,s` `,S` `,r` |
| yazi | `t` Tab... | `tt` new tab, `tr` rename tab |
| ranger | `y` Copy... | `yy` copy, `ya` `yr` `yt` copy modes, `yp` `yd` `yn` `y.` copy the path or name, `ygg` `yG` `yj` `yk` copy a range |
| ranger | `p` Paste... | `pp` `po` `pP` `pO` paste, `pl` `pL` paste a symlink, `phl` `pht` paste a hardlink, `pd` paste to |
| ranger | `u` Undo... | `ud` `uy` uncut, `uv` unmark all, `uV` visual reverse, `ut` remove tag, `uq` restore tab, `um` remove bookmark |
| ranger | `o` Sort... | `os` `ob` `on` `om` `oc` `oa` `ot` `oe` and the upper-case reverse forms, `or` reverse, `oz` random |
| ranger | `M` Linemode... | `Mf` `Mi` `Mm` `Mh` `Mp` `Ms` `MH` `Mt` |
| ranger | `.` Filter stack... | `.d` `.f` `.l` `.m` `.n` `.#` `."` `.'` `.\|` `.&` `.!` `.r` `.c` `.*` `.p` `..` |
| lf | `g` Go to... | `gg` top, `gh` home |
| lf | `s` Sort... | `sn` `ss` `st` `sa` `sb` `sc` `se` |
| lf | `z` View option... | `zh` hidden files, `zr` reverse order, `zn` `zs` `zt` `za` info columns |

Left blank because the sequences that start with the key do different things:

- ranger `d`: `dd` cut, `dD` delete, `dT` trash, `du` `dU` disk usage, `dc`
  directory size.
- ranger `g`: go to a directory (`gh`, `ge`, `gu` ...), but also `gt` `gT` next
  and previous tab, `gn` new tab, `gc` close tab.
- ranger `c`: `cw` rename, `cd` change directory, `ct` `cs` `ci` `cc` `cm` `ca`
  search order.
- ranger `z`: settings toggles, but also `zf` filter.

ranger keys that take a following character are drawn with the action:
`` ` `` and `'` go to a bookmark, `m` sets one, `"` (Shift+') tags with a
character. lf's `m`, `'` and `"` work the same way with marks.

### Left out

- Esc: the program mark (yazi: cancel; ranger: back to normal mode; lf: no
  action in Normal mode).
- The plain arrow keys, Home, End, Page Up and Page Down in ranger and lf: they
  do what their legends say. yazi's arrows are left out for the same reason.
- ranger `@` and `#`: the shell console with preset flags (`shell %s`, `shell
  -p`); `!` and `s` are drawn.
- ranger `zh` etc.: see above. Toggle hidden files is drawn on Ctrl+H and
  Backspace, its single-key bindings.
- ranger `<A-j>`/`<A-k>` and the `<a-N>` tab keys are drawn. On macOS they reach
  ranger only when the terminal sends Option as Meta.
- lf has no default key for delete, tabs or toggle hidden as a single key; they
  are not drawn.

## How the host knows the program is running

The three run in a terminal and have no plugin, so the host sees them only in
the terminal's **window title**. Each has a route in the shared
`&editor_titles` list (`overlay-mapping.poly.yaml`) that every terminal entry
uses, as GNU nano does (`../nano/SOURCES.md` has the title formats of each
terminal and shell, and the tmux setting). The route's key selects it; its
`title` regex then requires the program at the command position: at the start
of the title (not followed by ` — `, ` : ` or ` - `, which there mean the word
was a directory name), or after ` - `, ` — `, ` : `, `(`, `] ` or `> ` (also
`> ^`), each optionally with `sudo ` before it. So `vim lf`, `man ranger` and a
prompt in `~/yazi` keep the terminal's own overlay. The title is split into
words on whitespace before the keys are compared, so a key never matches part
of a word: `golf`, `self-test` and `lfs` do not select the lf route.

| program | title it writes | key words |
|---|---|---|
| yazi | `Yazi: <directory name>`, written on every directory change and tab change, cleared on exit (`yazi-actor/src/app/title.rs`, v26.9.1). Earlier releases had a `title_format` option whose default `Yazi: {cwd}` wrote the full path (removed in favour of the `ind-app-title` event, CHANGELOG #3684). Before its first write, the shell's title shows `yazi`. | `Yazi:`, `yazi`, `(yazi)`, `(yazi`, `^yazi` |
| ranger | Nothing by default (`set update_title false` in rc.conf). With `set update_title true` it writes `ranger:<path>` (`ranger/gui/ui.py`, `draw()`), shortened to the last 3 parts by `shorten_title`. The shell's title shows `ranger` otherwise. `update_tmux_title` renames the tmux window only. | `ranger`, `(ranger)`, `(ranger`, `^ranger`; `ranger:<path>` is one word, so it is matched by a `titles-match` regex on the terminal entry, `(?:^\|\s[-—:]\s\|\(\|\]\s)ranger:\S` |
| lf | Nothing (no title escape in the source; doc.md shows an `on-cd` example that writes `$PWD`, which does not name lf). Only the shell's title shows `lf`. | `lf`, `(lf)`, `(lf`, `^lf` |

ranger has no Windows set: its route and its `titles-match` entry have no
overlay of their own and only `macos` and `linux` branches, and each branch
repeats the title regex, because an `os:` branch is tried before the entry's
own `title`. yazi and lf use the same set on all three platforms.

As for nano, the terminal's own shortcuts stay on the keycaps, dimmed, under
the file manager's set, and a vim or emacs mode report takes priority over a
title. None of the title formats was checked on an install; the program titles
were read from the source above.

`tests/handler/tui_file_manager_routing_test.py` checks the positive titles,
the negative ones on all three platforms, the missing Windows set for ranger
and the priority of a mode report.

## Icons

| icons | source | licence |
|---|---|---|
| the plain glyphs listed in `FLUENT` in `fetch_icons.py` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons), `main` branch, through `icon_fetch.fluent` | MIT |
| the `ms:` entries of `FLUENT` | [Google Material Symbols](https://github.com/google/material-design-icons), weight 300, through `icon_fetch` | Apache-2.0 |
| the composites in `COMPOSITES` (half page, page, scroll, last file, tabs, jumps, find by letters, preview, shell variants, command history) | drawn with `composite()` of `../emacs/fetch_icons.py`; the shell and history composites draw the Fluent `Window Console` and `History` glyphs (`_shell.png`, `_history.png`) small above the word | MIT (Fluent) and this project |
| `tab1.png` .. `tab9.png` (yazi 1..9, ranger Alt+1..9) | Fluent `Tab` with the digit drawn inside by `number_badge.numbered`, as in the WezTerm set | MIT (Fluent) and this project |
| `search_fwd.png`, `search_back.png`, `find_next.png`, `find_prev.png` | copied byte for byte from `../nano/icons/` (drawn there with the same `composite()`) | this project |
| `yazi.png` | yazi mark, see below | MIT |
| `ranger.png` | ranger mark, see below | no licence stated |
| `lf.png` | drawn in `fetch_icons.py` (`_lf_mark`) | this project |

Where an action is the same as in the Total Commander set (`../totalcmd/`),
the same Fluent glyph is used: parent folder, back, forward, view, rename,
new file, new folder, delete permanently, close tab, new tab, reload, filter,
sort, shell, find. Labels that name a shared concept (Copy, Cut, Paste, Quit,
Help, Delete, Undo, Reload, Select all, Open, Go to...) are drawn by the shared
renderer instead, byte-identical with every other set that names them.

### ESC marks

All three are 32x32, drawn at the keycap size so the generator copies them
1:1 (`program_icon_region: [37, 32]`, anchor right, margin 0, mode alpha).

- **yazi**: the duck of `assets/logo.png` in the yazi repository
  (<https://github.com/sxyazi/yazi/blob/8dd895c695a5950330c2623eb43debf323b60654/assets/logo.png>,
  MIT, the repository's licence), composited over black, contain-fit into
  32x32 with LANCZOS, pixels lighter than luma 190 lit, lit groups smaller than
  3 pixels removed (`_logo_mark`). At luma 128 the orange disc behind the duck
  is lit as well and the mark is one round blob, in both the light-lit and the
  dark-lit form; 190 separates the white and yellow duck from the orange.
- **ranger**: the "r" of `ranger_logo.png` from the ranger website repository
  (<https://github.com/ranger/ranger.github.io/blob/eae5f11bbb247e221468b466da2d2214442dfa06/ranger_logo.png>;
  the site has moved to codeberg.org/ranger/pages, which has the same file).
  Same steps as yazi. At 190 only the light grey "r" is lit; the orange star
  and the small "anger" lettering drop out, which at 32 px were noise. Neither
  website repository states a licence for the logo, and the program repository
  (GPL-3.0) does not contain it. It is used only to name the program on its own
  key, as the other program marks are.
- **lf**: lf has no logo (its `lf.desktop` names the generic
  `utilities-terminal` icon, and the repository has no image file), so the mark
  is drawn: a filled folder with the letters "lf" cut out, pixel by pixel.

PolyKybdHost is GPL-3.0-or-later; MIT and Apache-2.0 are GPL-3.0-compatible.
