# lazygit overlay: sources

One overlay set for lazygit, the terminal UI for git (`bindings.yaml` →
`lazygit_template.mods.png` and `lazygit_template.combo.mods.png`), for
Windows, macOS and Linux. lazygit runs in a terminal, where Ctrl is Control on
every platform, so there is no macOS set.

Regenerate:

```bash
PYTHONPATH=. python polyhost/res/overlay_sources/lazygit/fetch_icons.py
python scripts/generate_app_overlays.py polyhost/res/overlay_sources/lazygit/bindings.yaml \
    --preview /tmp/lazygit_preview
```

## Shortcuts

Source: lazygit's default keybindings, `GetDefaultConfig()` in
[`pkg/config/user_config.go`](https://github.com/jesseduffield/lazygit/blob/v0.66.2/pkg/config/user_config.go),
tag **v0.66.2** (commit `63ab89fff478854deb4a35ef8902676b3cc5ca72`), checked
against the generated reference
[`docs/keybindings/Keybindings_en.md`](https://github.com/jesseduffield/lazygit/blob/v0.66.2/docs/keybindings/Keybindings_en.md)
at the same tag. lazygit writes an upper-case letter or a shifted symbol for a
key that needs Shift; it is drawn on the Shift variant of its key on a US
layout (`?` = Shift+/, `:` = Shift+;, `@` = Shift+2, `<` `>` = Shift+, Shift+.,
`+` `_` = Shift+= Shift+-, `{` `}` = Shift+[ Shift+]). Users can rebind every
key in `config.yml`; the set shows the defaults.

### What is drawn

- **Files panel** (the panel that has focus when lazygit starts): Space stage,
  `a` stage all, `c` commit, `w` commit without the pre-commit hook, `A` amend
  the last commit, `C` commit in the git editor, `e` edit, `o` open, `i`
  ignore, `r` refresh files, `s` stash all changes, `S` stash options, `d`
  discard, `D` reset options, `g` upstream reset options, `f` fetch, `M` merge
  conflict options, `y` copy, `` ` `` file tree, `-` collapse all, `=` expand
  all, Enter focus the file diff, Ctrl+O copy path, Ctrl+B filter by status,
  Ctrl+F find base commit for fixup, Ctrl+T external diff tool.
- **Global keys**: `q` and Ctrl+C quit, `Q` quit without changing the shell's
  directory, Ctrl+Z suspend, `p` pull, `P` push, `R` refresh, `m` merge/rebase
  options, `z` undo, `Z` redo, `?` keybindings menu, `:` shell command, `@`
  command log options, `W` and Ctrl+E diffing options, Ctrl+R recent
  repositories, Ctrl+P custom patch options, Ctrl+G jump to file in diff,
  Ctrl+S filter options, Ctrl+W toggle whitespace, `+` `_` screen mode, `{`
  `}` diff context, `0` focus the main view, `/` filter the view,
  Alt+Shift+C edit the config file (on macOS the terminal must send Option as
  Meta).
- **Navigation**: `1`..`5` jump to the Status, Files, Branches, Commits and
  Stash panels (the default `gui.sidePanels` order), `h` `l` Tab Shift+Tab
  previous and next panel, `j` `k` next and previous item, `,` `.` page, `<`
  `>` Home End top and bottom, `[` `]` previous and next tab, `v` range
  select, `K` `J` PgUp PgDn Ctrl+U Ctrl+D scroll the main view, `H` `L` scroll
  left and right.
- Esc shows the program mark (in lazygit it closes a popup or cancels).

### Left out

- The keys of the other panels. The overlay cannot know which panel has
  focus, so the set draws the Files panel's meaning of each letter. The
  letters that do something else elsewhere: in **Branches** `c` checkout by
  name, `r` rebase, `R` rename, `M` merge, `f` fast-forward, `o` create pull
  request, `u` upstream options, `i` git-flow options, `s` sort order, `T`
  create tag, `N` move commits to a new branch, `F` force checkout, `-`
  checkout the previous branch, `G` open the pull request in a browser,
  Ctrl+Y copy the pull request URL; in **Commits** `s` squash, `f` fixup, `r`
  reword, `R` reword in the editor, `d` drop, `e` edit, `p` pick, `t` revert,
  `C` copy for cherry-pick, `V` paste, `A` amend to this commit, `a` amend
  attributes, `g` reset options, `b` bisect, `i` interactive rebase, `B` base
  for rebase, `T` tag, `F` create fixup commit, `S` squash above, Ctrl+J and
  Ctrl+K move the commit, Space checkout, Ctrl+L log options, `*` select the
  branch's commits; in **Stash** Space apply, `g` pop, `d` drop, `n` new
  branch, `r` rename; in **Status** `a`/`A` the all-branches graph, `u` check
  for updates, Enter recent repositories. The main panel (staging lines and
  hunks, merge conflicts) has its own keys too (`a`, `b`, `E`, `n`, `N`).
- `|` and `\` (cycle diff renderers): they do nothing unless several diff
  renderers are configured ("No other diff renderers configured").
- `(` and `)` (rename similarity threshold): no picture explains them at
  keycap size.
- `n` and `N` (next and previous search match): they act only while a search
  is active.
- The arrow keys and Shift+Up/Down (move and range select): the keycap legend
  already says what they do.
- Ctrl+Enter, Ctrl+S, Ctrl+Backspace and the word movement keys: they act only
  in the commit message editor and the text prompts.

## Icons

| file | source | licence |
|---|---|---|
| `commit` `push` `pull` `fetch` `stash` `stashall` `branches` `history` `filter` `repolist` `shell` `openwith` `fullscreen` `compare` `merge` `rebase` `editor` | copied byte for byte from `../githubdesktop/icons` (Fluent UI System Icons / Material Symbols) | MIT / Apache-2.0 |
| `stage` `stageall` `shortcuts` `difftool` `prevtab` `nexttab` | copied byte for byte from `../gitkraken/icons` | MIT / Apache-2.0 |
| Fluent names in `FLUENT` (`edit`, `ignore`, `refreshfiles`, `discardfile`, `resetoptions`, `stashoptions`, `treeview`, `mainview`, `copypath`, `status`, `files`, `quitkeepdir`, `refresh`, `suspend`, `screenprev`, `editconfig`, `_nohook`) | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `ms:` names in `FLUENT` (`upstreamreset`, `collapseall`, `expandall`, `statusfilter`, `filteroptions`, `patch`, `jumptofile`, `whitespace`, `commandlog`, `contextmore`, `contextless`, `fixupbase`, the navigation arrows, `scrollup`..`scrollright`, `rangeselect`, `scrolltop`, `scrollbottom`) | [Material Symbols](https://github.com/google/material-design-icons) | Apache-2.0 |
| `commitnohook` `amend` `commiteditor` | drawn in `fetch_icons.py`: the commit glyph with a badge (prohibited sign, pencil, code brackets) in the lower right corner | from the sources above |
| `lazygit` (ESC mark) | drawn in `fetch_icons.py` from the lazygit logo, see below | see below |

The shared renderer draws `y` Copy, `q`/Ctrl+C Quit, `z` Undo and `Z` Redo
(their labels name a shared concept), so those keys have no file here.

Within the set, no two actions share a picture except keys that do the same
thing (Enter and `0`, the four scroll keys, `<`/Home, `>`/End, Tab/`l`).
GitHub Desktop draws "Discard" with an undo arrow; here `d` uses the trash can
because `z` Undo already shows an undo arrow.

## ESC program mark

The lazygit logo (the reclining git graph with a nightcap, above the word
"Lazygit") shown at the top of the repository's README:
`https://user-images.githubusercontent.com/8456633/174470852-339b5011-5800-4bb9-a628-ff230aa8cd4e.png`
(1072x1090 RGBA). The repository has no logo file in its tree (no `assets/`
directory on `master`; the `assets` branch holds only demo GIFs and sponsor
images), and lazygit.dev's favicon is the default Astro icon, so the README
image is the source. lazygit is MIT-licensed (Copyright (c) 2018 Jesse
Duffield); the image is part of the project's own README but is not a file in
the repository, so the licence does not name it. It is used here to identify
the program, as the other program marks are.

`_lazygit_mark()` composites the image over white and fits the figure (rows
85..800 of the logo, with the cap and the moon, without the word) into the
top 22 rows of the 32x32 mark. The dark graph (luma 128 or darker) is lit
where a pixel is at least 45% covered (**dark lit**). The green cap and the
blue moon are lit on a checkerboard where a pixel is at least 30% covered, so
they read as a second shade. The coloured end circles and the grey quotes
stay unlit, so the circles show hollow. Under the figure, after one blank row,
"lazygit" is written in a hand-drawn 6-row micro font (`_MICRO_FONT`). The 32x32 mark is placed 1:1 (`program_icon_region:
[37, 32]`, anchor right, margin 0, mode alpha). The file is guarded: a re-run
leaves a committed `lazygit.png` as it is.

## How the host knows lazygit is running

lazygit never sets the terminal's window title: there is no OSC 0 or OSC 2
write anywhere in its `pkg/` sources at v0.66.2 (its only OSC writes are 8,
hyperlinks, and 11, the background colour query), and it does not call tcell's
`SetTitle`. The host therefore sees lazygit only in the terminal's window
title, when the shell or the terminal puts the running command there, exactly
as for GNU nano (`../nano/SOURCES.md` has the title formats of each terminal
and shell, the shell scripts in `polyhost/res/shell/`, and the tmux setting).

The mapping (`overlay-mapping.poly.yaml`, `&editor_titles` on every terminal
entry) selects the route on the word `lazygit` (or `(lazygit)` / `(lazygit`
for iTerm2, `^lazygit` for Nushell) and then requires lazygit at the command
position:

```
^(?:sudo\s+)?lazygit(?:$|\s(?![—:-]\s))|(?:\s[-—:]\s|\(|\]\s|>\s\^?)(?:sudo\s+)?lazygit(?:$|\s|\))
```

Checked in `tests/handler/lazygit_routing_test.py`. None of the title formats
was checked on an install of lazygit; they are the formats nano's routing was
written for, with lazygit as the command.

Missed: lazygit started through an alias or a wrapper (`lg`, the usual alias
in lazygit's README, writes `lg` into the title), from an editor plugin
(lazygit.nvim runs it inside Neovim's terminal, where Neovim's title shows),
or from a file manager.
