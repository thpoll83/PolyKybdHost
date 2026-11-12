# qutebrowser overlay: sources

One spec, `bindings.yaml`, one artwork set, `qutebrowser_template.*`, for
Windows, macOS and Linux. Rebuild with `fetch_icons.py`, then
`scripts/generate_app_overlays.py` on the spec.

## Shortcuts

- **Defaults:** `bindings.default` → `normal:` in
  `qutebrowser/config/configdata.yml` at tag v3.7.0
  (commit `b0a7967f11c1c616d3914f3227113e121efb0fe8`),
  `https://github.com/qutebrowser/qutebrowser/blob/v3.7.0/qutebrowser/config/configdata.yml`
  (read 2026-11-06).
- **Cross-check:** the same table in `doc/help/settings.asciidoc`
  (section `bindings.default`) and the key cheatsheet `misc/cheatsheet.svg`
  at the same tag.
- **macOS:** `qutebrowser/keyinput/keyutils.py` swaps Qt's macOS Ctrl/Meta
  mapping back, so `<Ctrl-…>` in a binding is the Control key on macOS and
  `<Meta-…>` is Cmd. No default normal-mode binding uses Meta, so the one set
  is correct on every OS. Alt is Option on macOS.

### Modes

qutebrowser is modal. Only **normal mode** is drawn, because it is the mode the
browser is in while the user is not typing into a page. Insert mode binds 4
keys, hint mode 5, passthrough 1, command mode 8 (history and completion
navigation); none is drawn, because the host cannot tell which mode is active.

### Key sequences

Many bindings are sequences of two or three keys (`gg`, `yy`, `ZZ`, `;f`,
`wIh`). A keycap can show only one key, so the rule is:

- A sequence is drawn on its **first key** only when that key is not a binding
  of its own and every default sequence that starts with it does the same kind
  of thing. The label lists the sequences.

  | Key | Sequences | Drawn as |
  |---|---|---|
  | `x` | `xo`, `xO` | Open URL in background tab |
  | `p` | `pp`, `pP` | Open URL from clipboard |
  | `P` (Shift+P) | `Pp`, `PP` | Open clipboard URL in new tab |
  | `Z` (Shift+Z) | `ZQ`, `ZZ` | Quit (`ZZ` saves the session) |
  | `;` | `;b` `;f` `;h` `;i` `;I` `;o` `;O` `;y` `;Y` `;r` `;R` `;d` `;t` | More hint modes |
  | `y` | `yy` `yY` `yt` `yT` `yd` `yD` `yp` `yP` `ym` `yM` | Yank URL or title |
  | `a` | `ad` | Cancel download |
  | `[`, `]` | `[[`, `]]` | Previous / next page of site |
  | `{`, `}` (Shift+[ / ]) | `{{`, `}}` | Previous / next page in new tab |

- **Left blank** because their sequences do different things: `g` (`gg` scroll
  to top, `go`, `gO`, `ga`, `gm`, `gK`, `gJ`, `gC`, `gi`, `gu`, `gU`, `gd`,
  `gf`, `gt`, `gb`, `gB`, `gD`, `g0`, `g^`, `g$`), `w` (`wo`, `wO`, `wh`, `wl`,
  `wf`, `wp`, `wP`, `wb`, `wB`, `wi`, `wI…`), `t` (`th`, `tl` and the
  `ts…`/`tp…`/`ti…`/`tc…` per-site toggles), `s` (`sf` save config, `ss`,
  `sl`, `sk`), `S` (`Ss`, `Sb`, `Sq`, `Sh`) and `c` (`co` tab only, `cd`
  clear downloads). So `gg` (scroll to top) is not drawn; `G` (scroll to
  bottom) is a single key and is.

### Other keys not drawn

- `<Escape>` (clear key chain, leave search and full screen): ESC carries the
  program mark.
- `<Ctrl-^>` (last used tab): the key depends on the keyboard layout
  (Ctrl+Shift+6 on US). `Ctrl+Tab` does the same and is drawn.
- `<Ctrl-Shift-Tab>`: bound to `nop`.
- `<back>`, `<forward>`: mouse and media buttons, which have no keycap cell.
- `g0`, `g^`, `g$`: covered by `Alt+1` and `Alt+9`.

### Drawn keys

| Key | Command | Label |
|---|---|---|
| o, O | `cmd-set-text -s :open`, `… -t` | Open URL, Open URL in new tab |
| d, D | `tab-close`, `tab-close -o` | Close tab, Close tab, select other side |
| u, U | `undo`, `undo -w` | Reopen closed tab / window |
| J, K | `tab-next`, `tab-prev` | Next / previous tab |
| T | `cmd-set-text -sr :tab-focus` | Go to tab |
| H, L | `back`, `forward` | Back, Forward |
| r, R, F5, Ctrl+F5 | `reload`, `reload -f` | Reload, Reload (skip cache) |
| F11 | `fullscreen` | Full screen |
| h j k l | `scroll left/down/up/right` | Scroll |
| G | `scroll-to-perc` | Scroll to bottom |
| f, F | `hint`, `hint all tab` | Hint links, Hint links, open in new tab |
| /, ?, n, N | search | Search page, Search page backward, Next / previous match |
| Enter, Ctrl+Enter | `selection-follow`, `… -t` | Follow selected link (in new tab) |
| : | `cmd-set-text :` | Command line |
| i, v, V | `mode-enter insert/caret`, line selection | Insert mode, Caret mode, Caret mode, select line |
| `` ` ``, ' | `mode-enter set_mark/jump_mark` | Set mark, Jump to mark |
| . | `cmd-repeat-last` | Repeat last command |
| q, @ | `macro-record`, `macro-run` | Record macro, Run macro |
| m, b, B | quickmarks | Save quickmark, Open quickmark (in new tab) |
| M | `bookmark-add` | Bookmark page |
| -, +, = | `zoom-out`, `zoom-in`, `zoom` | Zoom out, Zoom in, Reset zoom |
| Ctrl+T, Ctrl+N, Ctrl+Shift+N | `open -t/-w/-p` | New tab, New window, Private window |
| Ctrl+W, Ctrl+Shift+W | `tab-close`, `close` | Close tab, Close window |
| Ctrl+Shift+T | `undo` | Reopen closed tab |
| Ctrl+PgDn, Ctrl+PgUp | `tab-next`, `tab-prev` | Next / previous tab |
| Ctrl+Tab | `tab-focus last` | Last used tab |
| Ctrl+P | `tab-pin` | Pin tab |
| Ctrl+Q | `quit` | Quit |
| Ctrl+H, Ctrl+S | `home`, `stop` | Home page, Stop loading |
| Ctrl+V | `mode-enter passthrough` | Passthrough mode |
| Ctrl+F, Ctrl+B, Ctrl+D, Ctrl+U | `scroll-page` | Page down / up, Half page down / up |
| Ctrl+A, Ctrl+X | `navigate increment/decrement` | Increment / decrement number in URL |
| Ctrl+Alt+P | `print` | Print |
| Alt+M | `tab-mute` | Mute tab |
| Alt+1 … Alt+8, Alt+9 | `tab-focus 1…8`, `tab-focus -1` | Tab 1 … 8, Last tab |

Symbol keys are placed for a US layout: `?` = Shift+/, `:` = Shift+;,
`+` = Shift+=, `@` = Shift+2, `{`/`}` = Shift+[ / ].

## Process names and matching

Read from the v3.7.0 source and packaging; not checked on an install.

- **Windows:** `qutebrowser.exe`, the PyInstaller build (`misc/qutebrowser.spec`,
  `name='qutebrowser'`).
- **macOS:** `qutebrowser.app` (same spec, `BUNDLE(name='qutebrowser.app')`);
  the host reads the display name, `qutebrowser`.
- **Linux:** the installed launcher is a script named `qutebrowser`, so the
  process name is `qutebrowser`. `app.py` sets the application name
  `qutebrowser` and the desktop file declares `StartupWMClass=qutebrowser`.
  `--desktop-file-name` defaults to `org.qutebrowser.qutebrowser`, which is
  the Wayland app id and the Flathub id. Both names are in the mapping.
- A source checkout started as `python3 -m qutebrowser` reports `python3`.
  That name is not mapped: it would match every Python program.

The entry has no web-app routing (`urls-contains`, `titles-contains`): the
browser extension that reports the tab URL does not run in qutebrowser, and
in normal mode qutebrowser takes the single keys that the web-app sets draw.

## Icons

- **Borrowed byte for byte** (same placement as in those sets):
  from `chrome/icons/`: addressbar, back, bookmark, closetab, find, findnext,
  forward, fullscreen, incognito, lasttab, newtab, newwindow, nexttab,
  prevtab, reload, reload_f5, reopentab, tab1–tab8, zoomin, zoomout,
  zoomreset; from `firefox/icons/`: caret, closewindow, findprev, hardreload,
  home, mute, quit, reopenwindow, stop. Their sources are in those sets'
  `SOURCES.md`.
- **Microsoft Fluent UI System Icons** (MIT,
  `https://github.com/microsoft/fluentui-system-icons`): Tab Add, Arrow Swap,
  Pin, Link, Arrow Enter, Open, Arrow Left/Down/Up/Right, Location Add,
  Record, Play Circle, Clipboard Link, Print. The names are in the `FLUENT`
  table of `fetch_icons.py`.
- **Material Symbols** (Apache-2.0, `https://fonts.google.com/icons`), the
  `ms:` entries of the same table: tab_unselected, content_paste_go, tab,
  ads_click, open_in_new, vertical_align_bottom, keyboard_double_arrow_*,
  keyboard_arrow_*, navigate_before/next, exposure_plus_1/neg_1, terminal,
  manage_search, edit, keyboard, subject, my_location, repeat, bookmark_add,
  bookmarks, collections_bookmark, content_copy, file_download_off.
- Ctrl+Q and Shift+Z (Quit) and Ctrl+Alt+P (Print) are drawn by the shared
  concept renderer (`concept:fluent:sign_out`, `concept:fluent:print`), not
  from `icons/`.

## ESC program mark

`icons/qutebrowser.png` is the qutebrowser logo,
`https://raw.githubusercontent.com/qutebrowser/qutebrowser/v3.7.0/qutebrowser/icons/qutebrowser-256x256.png`.
Licence: GPL-3.0-or-later, the licence of the qutebrowser repository
(`LICENSE`); the README credits the icon to Jad / yelo. PolyKybdHost is
GPL-3.0-or-later, so the logo can be shipped.

`fetch_icons.py` composites it over black, contain-fits it into 32x32 with
LANCZOS and lights the pixels brighter than luma 128. The light blue globe is
lit and the dark blue "qb" stays dark, so the mark reads as a disc with "qb"
cut out. The other polarity (dark pixels lit) keeps only the "qb" and loses
the globe. The file is guarded: a committed `qutebrowser.png` is not redrawn;
delete it to redraw. Placement: `program_icon_mode: alpha`, anchor right,
region [37, 32], margin 0, so the 32x32 mark is copied 1:1.
