# WordCraft overlay: sources and provenance

Reproducible record. To rebuild, run `fetch_icons.py`, then run
`scripts/generate_app_overlays.py` on `bindings.yaml`. Two generator runs give
byte-identical PNGs (sha256 checked, 2026-10-13).

WordCraft is a Word-like word processor (Rust/egui) from the ArtCraft "Crafting
Apps" suite: <https://github.com/storytold/wordcraft>, licence **MIT OR
Apache-2.0**. Everything below was read at commit
**`159b84f54c74e9e82fb3109b758ae7dd6f4e3ab0`**.

## Shortcuts: WordCraft's own keymap, not Microsoft Word's

The app has one command registry. Each `CommandSpec` declares its default keys
with `.key("…")`. The canvas (`crates/ui-egui/src/keys.rs` `dispatch`, lines
119-139) builds a string like `Mod+Shift+K` from the egui modifiers and looks
it up in that registry. `Mod` is egui `command`: Ctrl on Windows/Linux, Cmd on
macOS, which is written here as `CMDCTRL`. A literal `Ctrl+` string can match
only on macOS, where Ctrl does not set `command` (`keys.rs` `combo`, lines
86-105). Two helpers decide the platform differences, and they only ever
branch on macOS (`crates/engine/src/cmd/mod.rs:105-114`):

- `mac_or(mac, other)` gives the macOS chord and the Windows/Linux chord.
- `non_mac(k)` means the chord does not exist on macOS, because Option+letter
  types a character there. These bindings carry `except: [macos]`.

Windows and Linux therefore share one keymap, and the generator emits no Linux
set. The table was pulled mechanically from every `.key(` in
`crates/engine/src/cmd/*.rs` and then checked by hand.

| Group | Source (file:line) |
|---|---|
| New / Open / Save / Save As / Print / Close (`Mod+N`, `Mod+O`/`Mod+F12`, `Mod+S`/`Shift+F12`, `F12`, `Mod+P`/`Mod+Shift+F12`/`Mod+F2`, `Mod+W`/`Mod+F4`) | `cmd/file.rs:31-80` |
| Undo, Redo (`Mod+Y`/`Mod+Shift+Z`), Cut/Copy/Paste, Paste Text Only `Mod+Shift+Alt+V`, Find `Mod+F`, Find Next `Mod+G`/`F3`/`Mod+PageDown`, Find Previous `Mod+PageUp` (macOS also `Mod+Shift+G`), Replace `Mod+H`, Go To `Mod+Alt+G`/`F5`, Go Back `Shift+F5`, Copy/Paste Formatting `Mod+Shift+C`/`V` | `cmd/edit.rs:43-152` |
| Paste Special `Mod+Alt+V` | `cmd/paste.rs:39` |
| Select All, word/paragraph/document caret moves (`Mod`/`Alt`+arrows, `Mod+Home`/`End`) | `cmd/caret.rs:19-46` |
| Character formatting (B/I/U, `Mod+Shift+D`/`W`/`A`/`K`/`H`/`F`/`P`, `Mod+=`, `Mod+Shift+=`, `Mod+Shift+.`/`,`, `Mod+]`/`[`, `Mod+D`), Highlight `Mod+Alt+H` (non_mac), Change Case `Shift+F3` | `cmd/format.rs:29-142` |
| Paragraph alignment, indents, spacing `Mod+1/2/5/0`, Reset Paragraph (`mac_or("Ctrl+Q","Mod+Q")`), styles `Mod+Shift+N`, `Mod+Alt+1-3`, `Mod+Shift+L`, move/promote/demote (`Alt+Shift+arrows`; macOS `Ctrl+Shift+arrows`), Styles pane `Mod+Alt+Shift+S`, Apply Styles `Mod+Shift+S` | `cmd/para.rs:15-227` |
| Link `Mod+K`, Bookmark `Mod+Shift+F5`, Field `Mod+F9`, Date/Time/Page fields (`Alt+Shift+D/T/P`; macOS `Ctrl+Shift+D/T/P`) | `cmd/insert.rs:39-82` |
| Field Codes `Alt+F9`, field toggle/unlink/lock/unlock/next/prev | `cmd/fields.rs:27-36` |
| Update Field `F9`, Footnote `Mod+Alt+F`, Endnote `Mod+Alt+D` | `cmd/references.rs:35-78` |
| Mark Citation `Alt+Shift+I`, Mark Entry `Alt+Shift+X` (both non_mac) | `cmd/citations.rs:335`, `cmd/index.rs:25` |
| Mailings `Alt+Shift+E/F/K/N` (non_mac) | `cmd/mailings.rs:59-137` |
| Outline `Alt+Shift+=`/`-`/`1-9`/`A` | `cmd/outline.rs:73-146` |
| Comment `Mod+Alt+M`, Track Changes `Mod+Shift+E`, Word Count `Mod+Shift+G` (non_mac), Spelling `F7`/`Alt+F7`, Thesaurus `Shift+F7` | `cmd/review.rs:12-110` |
| View: marks `Mod+8`/`Mod+Shift+8`, Print Layout / Draft / Outline / Split `Mod+Alt+P/N/O/S` | `cmd/view.rs:22-91` |
| Equation `Alt+=` | `cmd/equation.rs:26` |
| Typing: hyphens `Mod+-`/`Mod+Shift+-`, Em Dash `Mod+Alt+-`, (c)/(R)/TM/ellipsis `Mod+Alt+C/R/T/.` (non_mac), Toggle Unicode `Alt+X` (not macOS), Delete Next Word `Mod+Delete`/`Alt+Delete` | `cmd/text.rs:16-38` |
| Repeat `F4`, Tell me / Search `Alt+Q` (non_mac), Extend Selection `F8` | `cmd/tools.rs:347,383,652` |
| Column selection `Mod+Shift+F8` | `cmd/column.rs:25` |
| UI keys outside the registry: `Alt+Q` (`keys.rs:110-116`), `Shift+F10` context menu (`keys.rs:153-157`), `F10` key tips (`keytips.rs:686`) | `crates/ui-egui/src/` |

Bound: **149** cells on Windows/Linux and **136** on macOS, plus the ESC mark
on every layer.

- Windows/Linux by tier: Ctrl 49, Alt 10, Shift 7, no-mod 9, Ctrl+Shift 28,
  Ctrl+Alt 18, Alt+Shift 25, Ctrl+Alt+Shift 2.
- macOS by tier: Cmd 48, Cmd+Shift 28, Cmd+Alt 13, Cmd+Alt+Shift 2, Ctrl 1,
  Ctrl+Shift 7, Alt 8, Alt+Shift 12, Shift 7, no-mod 9.

**Skipped, because the key has no cell:** Space (`Mod+Space` reset character,
`Mod+Shift+Space` NBSP, `Mod+Alt+Space` Read Aloud, macOS `Ctrl+Space`), Enter
(page/column/line break), Tab, Backspace (`Mod`/`Alt+Backspace`), and Escape
(the program-icon cell).

**Skipped, because the key has no shortcut of its own:** the unmodified caret
keys (arrows, Home, End, PageUp, PageDown, Delete, Insert overtype). They do
what the key's own legend says. Shift+arrow selection extension is also
skipped. It is a fallback in `keys.rs` `shift_variant_params`, not a bound
chord.

### Choices and caveats

- `Mod+Shift+G` depends on the platform. It is Word Count off macOS and Find
  Previous on macOS. Both are bound, with disjoint `only:`/`except:`.
- `Mod+Shift+Alt+V` is Paste Text Only. The keymap normalizes the order of the
  modifiers (`keymap.rs` normalize), so the chord resolves.
- On macOS, `Cmd+H` (Replace) and `Cmd+M` (Indent) are what the registry binds.
  winit's default app menu may intercept `Cmd+H` (Hide) before the app sees it.
  This was not verified on hardware.
- No `Modifiers::CTRL`-literal chords exist off macOS. No GUI/Win chords exist.

## Window matching

| OS | What the handler sees | Source |
|---|---|---|
| Windows | `wordcraft.exe`, matched as `wordcraft` | `apps/wordcraft/Cargo.toml` (bin `wordcraft`), `packaging/windows/wordcraft.wxs:70` |
| macOS | `WordCraft`, matched as `wordcraft` | `packaging/macos/Info.plist.in` (CFBundleName / CFBundleExecutable / CFBundleDisplayName) |
| Linux X11 / Wayland | WM_CLASS / app id `ai.storyteller.wordcraft`; the process is `wordcraft` | `apps/wordcraft/src/main.rs:271` `with_app_id`, `packaging/linux/ai.storyteller.wordcraft.desktop` (`StartupWMClass`) |

## Icons

- **Microsoft Fluent UI System Icons (MIT).** Source:
  `microsoft/fluentui-system-icons`, `assets/<Name>/SVG/…_regular.svg`, fetched
  through the shared `icon_fetch.fluent`. The folder name for each icon is in
  `fetch_icons.py` `FLUENT`.
- **Material Symbols (Apache-2.0).** These are the `ms:` entries:
  `text_increase`/`text_decrease` (grow/shrink 1 pt), `move_up`/`move_down`,
  `format_indent_decrease`/`increase` (promote/demote), `unfold_more`/`less`,
  `skip_next`/`skip_previous` (next/previous field), `keyboard_double_arrow_*`
  (word/paragraph moves), `vertical_align_top`/`bottom` (document start/end),
  and `backspace`. The last one is mirrored into `delwordfwd.png`, the
  forward-delete glyph.
- **Copied byte-for-byte from `../word/icons/`** with the same placement keys,
  so they draw the same cell: `hangindent.png`, `linespacing1/15/2.png`, and
  `hyphen.png`.
- **Drawn in `fetch_icons.py`** (original, same licence as this repo):
  - text glyphs in DejaVu Sans Bold: em dash, (c), (R), TM, ellipsis, `a-b`
    non-breaking hyphen, `U+`, and the pilcrow;
  - `wordunderline.png` (two words, each underlined);
  - `reducehang.png` (hanging indent with a left arrow);
  - `level1-9.png` (`number_badge` digits over Fluent `Square`).

Many labels are concept names, such as Copy, Save, Go to and Find next. The
generator draws those cells with the shared renderer
(`concept:fluent:…`), so the committed PNG for them is unused.

## Program icon (ESC)

`wordcraft.png` is WordCraft's own app icon, `assets/app-icon/wordcraft.svg`,
fetched from the pinned commit. Licence: **MIT OR Apache-2.0**, per the repo's
`ATTRIBUTION.md` ("original artwork … Placeholder app icon until the WordCraft
mascot drawing lands"). It is rendered by cairosvg at 256 px with the blue
rounded-square `<rect>` removed.

A sweep at keycap size compared two versions. The full tile, in luma or alpha,
is one large lit blob. With the tile removed, the page, its lines and the
pencil read clearly. The chosen settings are `program_icon_mode: luma`,
threshold 150, region `[46, 40]`, bottom-right. Upstream calls this icon a
placeholder. When the mascot lands, delete `icons/wordcraft.png` and re-run
`fetch_icons.py` with the new SHA. The script never overwrites an existing
`wordcraft.png`.
