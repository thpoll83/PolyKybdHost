# FigCraft overlay: sources and provenance

FigCraft is the interface design and prototyping app in the ArtCraft "Crafting Apps"
suite (<https://getartcraft.com/apps>): open-source Rust/egui, modelled on Figma,
<https://github.com/storytold/figcraft>, licence **MIT OR Apache-2.0**. This host is
GPL-3.0-or-later, which may ship either.

Rebuild: `PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/figcraft/fetch_icons.py`,
then `scripts/generate_app_overlays.py` on `bindings.yaml`. Both are deterministic
(generator run twice: identical sha256 for all seven PNGs; a re-fetch reproduced every icon).

## Shortcuts

Source commit: `e56856f4016c76fbc862ac2fb4fd3fb43a68f396`.

FigCraft defines every default key once, in **`crates/engine/src/keymap.rs`, `KEYS`
(lines 160-331)**. Its menus, Keyboard shortcuts panel, canvas and control channel
all look keys up there (`crates/ui-egui/src/shortcuts.rs`, `lookup()` at line 56 and
`key_event()` at line 156). So this overlay is that table, not Figma's keymap.

Notation in the table: `Cmd` is the command key (⌘ on macOS, Ctrl elsewhere), so it is
written `CMDCTRL` here. `Ctrl` is literal Control on macOS, so it stays `CTRL`. On
Windows/Linux, `Cmd` and `Ctrl` are one key (`same_mods`, line 453). A binding with
`.win([...])` has different Windows/Linux keys. Those eleven commands are written twice
with `only:`. Only the canvas context is bound (`Context::Canvas`/`Both`). Text-only
bindings are left out: `text.link` Cmd+K, list indent/outdent Cmd+]/[.

| Group (keymap.rs line) | Bound |
|---|---|
| Essential (161) | Actions Cmd+K / Cmd+/, Keyboard shortcuts Ctrl+Shift+/ (literal Ctrl on Mac too), Toggle UI Cmd+\, Pick color I (+ Ctrl+C Mac only), Preferences Cmd+,, New/Open/Save/Save as/Save version/Close (Cmd+N/O/S, Shift+Cmd+S, Alt+Cmd+S, Cmd+W), Find/replace Cmd+F, Cursor chat /, Run last plugin (Mac Alt+Cmd+P; Win/Linux Ctrl+Alt+Shift+P) |
| Tools (178) | V K H F A S R L O P T C, Shift+S/L/P/M, Place image Shift+Cmd+K |
| View (195) | Pixel grid Shift+' / Cmd+', Layout grids Shift+G (+ Mac Ctrl+G, Win/Linux Ctrl+Shift+4), Rulers Shift+R, Outlines Shift+Cmd+O, Pixel preview (Mac Ctrl+P; Win/Linux Ctrl+Alt+P), Comments Shift+C, Multiplayer cursors Alt+Cmd+\, Snap to pixel Shift+Cmd+', panels Alt+1/2/3/8/9, Shift+E, Shift+D, Left sidebar Shift+Cmd+\, regions F6 / Shift+F6 (+ Win/Linux Ctrl+F6), Context menu Shift+F10, Collapse layers Alt+L, pages PgUp/PgDn |
| Zoom (221) | Zoom in Cmd+= / Shift+= / Shift+Cmd+=, Zoom out Cmd+- / - / Shift+-, 100% Shift+0 / Cmd+0, fit Shift+1, selection Shift+2, prev frame Shift+N / Home, next frame N / End |
| Text (229) | Cmd+B/I/U, Shift+Cmd+X, lists Shift+Cmd+8/7, align Alt+Cmd+L/T/R/J, size Shift+Cmd+./,, weight Alt+Cmd+./,, line height Alt+Shift+./,, tracking Alt+./, |
| Shape (251) | Flatten Alt+Shift+F / Cmd+E, Outline stroke Alt+Cmd+O, booleans Alt+Shift+U/S/I/E, Remove fill Alt+/, Remove stroke Shift+/, Swap Shift+X, Join Cmd+J, Smooth join Shift+Cmd+J, Delete and heal Shift+Delete |
| Selection (264) | Cmd+A, Shift+Cmd+A, Alt+Cmd+A, Select parent \, Cmd+G, Shift+Cmd+G / Cmd+Delete, Alt+Cmd+G, Shift+Cmd+H, Shift+Cmd+L, Rename Cmd+R / F2, Select area F8 |
| Edit (283) | Undo/Redo, copy/cut/paste, Paste over Shift+Cmd+V, Paste to replace Shift+Cmd+R, Cmd+D, Delete, Alt+Cmd+C/V, Copy as PNG Shift+Cmd+C, Export Shift+Cmd+E, Import Shift+Cmd+I |
| Transform (298) | Flip Shift+H/V, Mask (Mac Ctrl+Cmd+M; Win/Linux Ctrl+Alt+M), Resize to fit Alt+Shift+Cmd+R, Rotation origin Alt+R |
| Arrange (304) | Front/back (Mac Alt+Cmd+]/[; Win/Linux Shift+Ctrl+]/[), forward/backward Cmd+]/[, align Alt+A/H/D/W/V/S, distribute (Mac Ctrl+Alt+H/V; Win/Linux Alt+Shift+H/V), Tidy (Mac Ctrl+Alt+T; Win/Linux Ctrl+Alt+Shift+T), auto layout Shift+A / Alt+Shift+A, suggest (Mac Ctrl+Shift+A; Win/Linux Ctrl+Alt+Shift+A) |
| Components (321) | Create Alt+Cmd+K, Detach Alt+Cmd+B, Go to main (Mac Ctrl+Alt+Cmd+K; Win/Linux Ctrl+Alt+Shift+K). Shift+I = Assets, as in View |
| Gestures (`GESTURES`, line 333) | Hold Z zoom tool, hold Alt+Z zoom out (`crates/ui-egui/src/canvas.rs:321`). Digits 1-9, 0 set opacity 10-90%, 100% (`shortcuts.rs:290`, `opacity_digit`; pref `number_keys_opacity`, default on, `crates/engine/src/lib.rs:604`). |

The overlay binds 166 shortcuts per platform (the generator reports 167 placements,
which includes the ESC program mark): 36 no-mod, 25 Shift, 17 Alt, 8 Alt+Shift,
29 Cmd/Ctrl, 23 Cmd/Ctrl+Shift (including the literal-Ctrl help key), 15 Cmd/Ctrl+Alt,
1 Cmd/Ctrl+Alt+Shift, and 12 per platform from the 24 `only:` rows.

**Skipped (no keycap cell, or not a plain key):** Escape (deselect; the ESC cell is the
program icon), Enter / Shift+Enter (select children/parent, place shape), Alt+Cmd+Enter
(Present), Tab / Shift+Tab (next/prev layer), Ctrl+Tab / Ctrl+Shift+Tab (document tabs),
Space / Shift+Space (pan, preview), Alt+Space or Ctrl+Space (select area; F8 is bound),
Backspace (same command as Delete; the Delete key is bound), arrow-key nudge, resize and
pan (the keycap legend is already an arrow), presentation-mode keys (only while
presenting), and vector-edit / shape-builder keys (`tool_key`, mode-only).

**Context notes.** `/` is cursor chat only in a live session. Otherwise it does nothing.
Digit opacity applies only with a selection. Neither shadows another binding.

## Window matching

`match: [figcraft, ai.storyteller.figcraft]`:

- **Windows:** `figcraft.exe` (`packaging/windows/figcraft.wxs:87`), giving `figcraft`.
- **macOS:** bundle `FigCraft.app`, `CFBundleName` `FigCraft`
  (`packaging/macos/Info.plist.in`). Lowercased, this is `figcraft`.
- **Linux:** `StartupWMClass=figcraft` (`packaging/linux/ai.storyteller.figcraft.desktop`).
  eframe gets the app name `FigCraft` (`apps/figcraft/src/main.rs:189`), which it also
  uses as the Wayland app id (lowercased `figcraft`). The Flatpak app id is
  `ai.storyteller.figcraft` (`packaging/linux/flatpak/ai.storyteller.figcraft.yml`), and
  is listed as the reverse-DNS key the way `org.gimp.GIMP` is.

## Icons

- **Borrowed from `../figma/icons` (byte-identical, `icon_fetch.borrow`)** for the 49
  actions FigCraft shares with Figma: tools, edit, text format, group/ungroup, arrange,
  component, mask, export, and so on. Provenance is in `../figma/SOURCES.md`. Fluent
  is MIT. `slice.png` and `frameselection.png` are drawn there, white-on-transparent,
  and keep `mode: alpha`.
- **Microsoft Fluent UI System Icons (MIT)**,
  <https://github.com/microsoft/fluentui-system-icons> `main`, `assets/<Name>/SVG/`. The
  per-file names are in `fetch_icons.py` `FLUENT`. All were probed before use.
- **Google Material Symbols (Apache-2.0)**, weight 300, for: `select`, `opacity`,
  `grid_guides`, `menu_open`, `format_color_reset`, `unfold_more`/`unfold_less`,
  `fullscreen`, `line_curve`, `background_grid_small`, `format_list_numbered`,
  `find_replace`.
- **Composites built in `fetch_icons.py` (guarded):**
  - `weightup`/`weightdown`: Fluent Text Bold + Arrow Up/Down.
  - `removelayout`: Fluent Auto Fit Width with a strike.
  - `trackingup`/`trackingdown`: Material unfold_more/less turned 90°, as the
    horizontal twin of the line-height pair.
- **Shared concepts:** the generator draws these through the shared renderer, so the
  committed PNG is unused for them: Comment, Zoom in/out, Delete, Open, Save, Save as,
  Bold, Italic, Underline, Select all, Undo, Redo, Copy, Cut, Paste.
- **Changed after the first preview:**
  - F6/Shift+F6 used Keyboard Tab, which read the same as Import (→|). They now use
    Arrow Circle Right/Left.
  - The two Material letter-spacing glyphs looked identical at 36×32. Tracking now
    uses the turned chevrons above.

Weaker matches worth knowing:

| Action | Icon |
|---|---|
| Section | Board |
| Design/Prototype toggle | Arrow Bidirectional Left Right |
| Snap to pixel | grid_guides |
| Pixel preview | background_grid_small |
| Select matching | Target Arrow |
| Go to main component | Arrow Square Up Right |
| Delete and heal | Pen Prohibited |
| Tidy up | Layout Cell Four |

## Program mark (ESC)

`icons/figcraft.png` is FigCraft's **own** app icon: `assets/app-icon/figcraft-small.svg`
at the pinned sha, a chameleon engraving on a green tile. Its licence is
`assets/app-icon/LICENSE.txt`: the owner's original artwork, no third-party material,
**MIT OR Apache-2.0**.

At 46×40 1-bit, plain renders of the engraving are hatch noise. This was swept: the
ICO frames 256/128/64/48 and the SVG, luma at t90/120/150 and bright at t160-215. So
`_program_mark` derives a mark:

1. Render the SVG at 256 px and LANCZOS it to 92 px.
2. The figure is every pixel more than 80 (RGB distance) from the field green `#02da96`.
3. Keep the figure's outline (figure minus a 5-px MinFilter erosion), plus ink with
   luma < 60 inside the figure.
4. Save white-on-transparent.

This was picked over res 184 and k3 and ink cut-offs 0 and 90 by rendering at keycap
size. Binding: `program_icon_mode: alpha`, region `[46, 40]`, bottom-right, margin 0.
The file is guarded, so a re-run of `fetch_icons.py` never overwrites it.

## Mapping stanza

```yaml
figcraft,ai.storyteller.figcraft:
  overlay: [figcraft_template.mods.png, figcraft_template.combo.mods.png, figcraft_template.extra.mods.png]
  os:
    macos:
      overlay: [figcraft_template_mac.mods.png, figcraft_template_mac.combo.mods.png, figcraft_template_mac.extra.mods.png, figcraft_template_mac.gui.mods.png]
```
