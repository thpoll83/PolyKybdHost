# Obsidian overlay — sources & licenses

## Shortcuts

Obsidian **Windows/Linux** defaults. Obsidian's own help site does not publish a
single default-hotkey table any more — `help.obsidian.md/keyboard-shortcuts`
redirects to `obsidian.md/help/keyboard-shortcuts`, which 404s, and the
`Hotkeys` page it points to only explains how to *rebind* them. So the set was
taken from two independent references that agree on every binding shipped here:

- <https://linuru.com/obsidian/> — the full Windows/Linux table.
- The core navigation four (`Ctrl+O` quick switcher, `Ctrl+P` command palette,
  `Ctrl+G` graph view, `Ctrl+E` toggle edit/reading) were separately confirmed.
- <https://obsidian.md/help/hotkeys> — confirms these are defaults and that
  everything is rebindable in Settings → Hotkeys.

Only bindings both references agree on shipped. Notably **omitted**: `Ctrl+T`
(new tab) and the daily-note / template commands, which vary by enabled core
plugin and are not defaults in a clean vault — an overlay must not claim a key
does something that depends on the user's plugin set.

⚠️ Obsidian is unusually rebindable, so this overlay reflects a **default**
install. A user who has customised Settings → Hotkeys will see legends that
don't match; that is inherent to the app, not a bug in the overlay.

## Icons

| File(s) | Source | License |
|---|---|---|
| all 19 shortcut icons | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `obsidian.png` (ESC program mark) | Custom-drawn, `../geo_marks.py` | GPL-3.0-or-later (this repo) |

**The program mark is NOT the Obsidian gem logo**, which is a trademark we may
not redistribute. It is a **generic irregular faceted stone**, roughly
drop-shaped: facets drawn filled, then each polygon's own outline stroked in
black so shared edges erase themselves and every face reads as a separate lit
panel. It replaced a drawn "O" letter tile.

**The seed is the whole design.** Every stone in the family comes from the same
generator and differs only by `geo_marks.OBSIDIAN_SEED` (currently **97**,
picked from a rendered contact sheet), so there is nothing hand-placed to
preserve — changing the number picks a different stone and regenerating
reproduces it byte-for-byte.

Three things were established the hard way and are enforced by the defaults:

- **Symmetry has to be broken in the silhouette, not just the facet lines.** An
  earlier round jittered only the internal edges and kept a mirrored outline; it
  still read as symmetrical. Now the apex is off-centre, every boundary point
  carries its own radial jitter, and the boundary ring is cut into arcs of
  unequal length.
- **The seam must be 1px.** At 2px the seams eat the facets and the stone reads
  as a blob (or a brain) rather than a cut surface.
- **Scale to ~250–300 lit pixels**, matching the rest of the program-icon set.
  The first irregular version ran 526–621 and would have shone as a bright blob
  next to its peers. Check with an ink count, not by eye.

PolyKybdHost is GPL-3.0-or-later; MIT is GPL-3.0-compatible.

## Regenerate

```bash
python polyhost/res/overlay_sources/obsidian/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/obsidian/bindings.yaml --preview /tmp/obsidian_preview
```

## macOS

The spec serves Windows and macOS from one file: `obsidian_template.*`
(Windows/Linux) and `obsidian_template_mac.*` (macOS). Obsidian registers every
default hotkey as `Mod` (Ctrl on Windows/Linux, Cmd on macOS), which is exactly
`CMDCTRL`; 13 bindings use it.

Sources:

- Official help, <https://help.obsidian.md> — read from its source repo
  <https://github.com/obsidianmd/obsidian-help> (`en/`): "Editing shortcuts"
  (separate Windows/Linux and macOS tables: bold, italic, paste without
  formatting), "Quick switcher", "Command palette", "Search"
  (`Command+Shift+F`), "Views and editing mode" (`Cmd+E`), "Manage notes" (`Cmd+N`).
- The app's own default-hotkey table, for everything the help does not list:
  the `hotkeys:` arrays in Obsidian 1.13.7's `obsidian.asar`
  (<https://github.com/obsidianmd/obsidian-releases/releases/tag/v1.13.7>).
  That is what Settings → Hotkeys shows as the defaults. It has **no literal
  `Ctrl` hotkeys** among these bindings; the one platform branch is Find & replace.

| Action | Windows / Linux | macOS | Why |
|---|---|---|---|
| Find and replace | `Ctrl+H` | `Cmd+Option+F` | Obsidian's source: `isMac ? Mod+Alt+F : Mod+H` (⌘H is macOS "Hide"). Written twice with `only:`. |
| Navigate back | `Ctrl+Alt+Left` | `Cmd+Option+Left` | App default is `Mod+Alt+ArrowLeft`. Written twice with `only:`. |
| Navigate forward | `Ctrl+Alt+Right` | `Cmd+Option+Right` | App default is `Mod+Alt+ArrowRight`. |
| Toggle left sidebar | — (dropped) | — (dropped) | No default hotkey in Obsidian at all. |
| Toggle right sidebar | — (dropped) | — (dropped) | No default hotkey in Obsidian at all. |
| Strikethrough | — (dropped) | — (dropped) | No default hotkey in Obsidian at all. |

No macOS chord drawn here is system-reserved; the ⌘H clash is exactly why
Obsidian moves Find & replace off `H`.

Windows/Linux fixed against the app's default table (2026-09-30): Navigate
back/forward moved from `Alt+Left/Right` to `Ctrl+Alt+Left/Right`, and the
`Ctrl+Shift+L/R/X` cells (Toggle left/right sidebar, Strikethrough) are gone,
because Obsidian binds none of them in a clean install.

## Standard editing shortcuts (shared Fluent concepts, 2026-10-08)

Label = lexicon concept, no icon. Source: Obsidian help, "Editing shortcuts"
(`obsidianmd/obsidian-help`, `en/Editing and formatting/Editing shortcuts.md`,
https://help.obsidian.md/editing-shortcuts), separate Windows/Linux and macOS
tables:

| Concept | Windows / Linux | macOS |
|---|---|---|
| Cut / Copy / Paste | Ctrl+X/C/V | ⌘X/C/V |
| Undo | Ctrl+Z | ⌘Z |
| Redo | Ctrl+Shift+Z or Ctrl+Y (`only: [windows, linux]`) | ⌘⇧Z |
| Select all | Ctrl+A | ⌘A |

Not added / why:
- Find (Ctrl/⌘F), Replace (Ctrl+H / ⌘⌥F), Close (Ctrl/⌘W), New (Ctrl/⌘N):
  already bound above.
- Open: Ctrl/⌘O is the Quick switcher.
- Save / Print / Zoom / Reload: not documented as default hotkeys (Obsidian
  autosaves; "Save current file" and "Reload app" are commands with no help-
  documented default).

## Per-view sets (2026-11-13)

The Obsidian plugin (`obsidian-plugin/`) reports the active view as
`obsidian://<view>[/vim-<mode>]`, and the mapping entry routes it. The sets
are generated: `gen_obsidian_modes.py` writes `bindings_<set>.yaml` (do not
edit those) from `bindings.yaml` and renders them. `bindings.yaml` stays the
editor set and the only place Obsidian's own hotkeys are written.

| Set | Report | Keys |
|---|---|---|
| `obsidian_template` | `source`, `live`, Vim Insert/Replace, no report | unchanged |
| `obsidian_reading_template` | `reading` | the app commands, Find in file, Toggle edit/reading view, Copy, Select all |
| `obsidian_canvas_template` | `canvas` | the app commands and the Canvas keys below |
| `obsidian_graph_template` | `graph` (also local graph) | the app commands and the Graph view keys below |
| `obsidian_global_template` | `other` | the app commands: New note, Quick switcher, Command palette, Graph view, Close tab, Settings, Search all files, Navigate back/forward |
| `obsidian_vim_normal_template` | `.../vim-normal` | a layer drawn over the editor set |
| `obsidian_vim_visual_template` | `.../vim-visual` | a layer drawn over the editor set |

Live Preview and Source mode have the same hotkeys, so they share the editor
set.

Sources:

- Canvas: Obsidian help "Canvas" (`obsidianmd/obsidian-help`,
  `en/Plugins/Canvas.md`, read 2026-11-13): `Backspace` removes the selection
  (macOS "Delete", the same key), `Ctrl/Cmd+A` select all, `Shift+1` zoom to
  fit, `Shift+2` zoom to selection, `Ctrl/Cmd+Z` undo, `Ctrl/Cmd+Y` and
  `Ctrl/Cmd+Shift+Z` redo. Icons: Fluent Delete, Zoom Fit, Select Object (MIT).
- Graph view: Obsidian help "Graph view" (`en/Plugins/Graph view.md`): `+` and
  `-` zoom, the arrow keys move the graph, Shift moves it faster. `+` is drawn
  on Shift+=, where a US keyboard types it; which key code Obsidian reads for
  `+` was not checked. Icons: Fluent Zoom In, Zoom Out, Arrow Up/Down (MIT),
  and the existing arrow icons.
- Reading view: the app commands, plus the keys that do not edit text. Copy and
  Select all are the framework's ("Editing shortcuts" help page); Bold, Paste
  and the other editing keys do nothing in Reading view and are left out.
- Vim layers: Obsidian's *Vim key bindings* option runs CodeMirror's Vim
  emulation (`@replit/codemirror-vim`). Its default key map is frozen in
  `codemirror_vim_keys.yaml` (`@replit/codemirror-vim-core` 0.1.0, MIT). A layer
  is Vim's own Normal / Visual set (`../vim/keys.yaml`, the same art from
  `../vim/icons/`) without the keys the emulation does not implement
  (for example `K`, `!`, `&`, `U` in Normal mode) and without any Ctrl chord:
  the Ctrl keys stay Obsidian's hotkeys from the set underneath. Which one acts
  when both bind a Ctrl key (Ctrl+O, Ctrl+R) was not checked in Obsidian. The
  layers have no ESC mark, so the Obsidian mark stays on ESC. One file serves
  every OS: Vim's keys do not change with the platform.

Largest set: 85 images (`.../vim-normal` adds 85 Vim keys to the editor set,
under 120 together), far below the 600-image limit.

Regenerate:

```bash
python polyhost/res/overlay_sources/obsidian/fetch_icons.py
python polyhost/res/overlay_sources/obsidian/gen_obsidian_modes.py --render --preview /tmp/obsidian_modes
```
