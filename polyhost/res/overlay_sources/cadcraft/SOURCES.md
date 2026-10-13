# CADCraft overlay: sources and provenance

Reproducible record. Re-run `fetch_icons.py`, then `scripts/generate_app_overlays.py`
on `bindings.yaml`, to rebuild. Both are deterministic (checked: icons and all five
PNGs sha256-identical across re-runs).

## The app

CADCraft, https://github.com/storytold/cadcraft (ArtCraft "Crafting Apps"),
an open-source AutoCAD-style drafting app in Rust/egui. Licence **MIT OR Apache-2.0**
(`LICENSE-MIT`, `LICENSE-APACHE`); this GPL-3.0-or-later host may ship both.

Shortcuts read from commit **`e707ab4d7cc10102e550ad4c5bcecef1084a9baa`**.

## Shortcuts (authority: the app's source, not AutoCAD's keymap)

CADCraft is driven by a command line (`crates/ui-egui/src/cmdline.rs`): most commands
are typed aliases (`L`, `C`, `CO`, `TR`, ...) followed by Enter/Space. Those are **not**
keyboard shortcuts and are not bound. Only chords and F-keys the code handles:

| Group | Source |
|---|---|
| The egui shortcut table: every Cmd/Ctrl chord, F1-F3, F5, F7-F12 | `crates/ui-egui/src/menus.rs:594-629` (`fn shortcuts`) |
| Cmd/Ctrl+C, X, V (+Shift = copy with base point / paste as block): arrive as egui clipboard events | `crates/ui-egui/src/clipboard.rs:45-66` (`shortcut_commands`) |
| Delete erases the selection (empty command line, no command running) | `crates/ui-egui/src/cmdline.rs:348`; `crates/engine/src/cmd/edit.rs:58` (`.key("Delete")`) |
| macOS native menu: every menu `.key("Cmd+...")` label becomes a real accelerator | `apps/cadcraft/src/native_menu.rs:25-30,50,146`; labels in `crates/engine/src/cmd/*.rs` `.key(...)` and `crates/ui-egui/src/menus.rs:17-73` (`UI_COMMANDS`) |

egui `Modifiers::COMMAND` is Ctrl on Windows/Linux and Cmd on macOS, so every chord
is written `CMDCTRL` and the generator emits a `_mac` set. Nothing is remapped.

Bound: **34 cells** (Win/Linux 31, macOS 34):

- **CMDCTRL** (11): N New, O Open, S Save (QSAVE), P Plot (opens the Print/Plot
  dialog), Z Undo (U), Y Redo, A Select all, C Copy (COPYCLIP), X Cut (CUTCLIP),
  V Paste (PASTECLIP), E Isoplane (cycle Left/Top/Right).
- **CMDCTRL panels** (3): 1 Properties Inspector, 3 Tool Sets, 9 Command Line.
- **CMDCTRL, macOS only** (3, `only: [macos]`): W Close, 8 QuickCalc, `,` Settings
  (Options). These exist only as native-menu accelerators; the egui table that serves
  Windows/Linux has no entry for them, so Ctrl+W/8/, do nothing there.
- **CMDCTRL+Shift** (5): S Save as, Z Redo, A Group selection (PICKSTYLE toggle),
  C Copy with base point (COPYBASE), V Paste as block (PASTEBLOCK).
- **F-keys** (10): F1 Command Reference, F2 Command History, F3 Object Snap,
  F5 Isoplane, F7 Grid, F8 Ortho, F9 Snap, F10 Polar, F11 Object Snap Tracking,
  F12 Dynamic Input.
- **Nav** (1): Delete = Erase selection (Edit > Clear).
- **ESC**: program mark.

### Not bound, and why

- **Typed command aliases** (L, C, M, CO, TR, ...): command-line input, not chords.
- **F4, F6**: no handler (`docs/ui-parity.md:188` lists them as missing).
- **Up / Down**: command-line history recall (`cmdline.rs:325-345`); text-entry
  navigation in the command line, not a drawing shortcut. Left out on purpose.
- **Escape** (cancel) is the program-mark cell; **Enter, Space, Tab, Backspace**
  have no cell. (macOS Backspace also erases a selection, `cmdline.rs:237`.)
- **Cmd+Q, Cmd+H, Cmd+Opt+H** (macOS): standard predefined app-menu items, not
  CADCraft commands.
- **Cmd/Ctrl+Enter** in the MTEXT editor (`mtext_editor.rs:115`): only inside a
  modal text editor, and Enter has no cell anyway.
- **Ctrl+Y and Ctrl+Shift+Z** both mean Redo; both are drawn.
- No Alt, Ctrl+Alt, Ctrl+Alt+Shift or GUI (Win-key) chords exist in the source.

## Icons

| icon | source | licence |
|---|---|---|
| commandref, history, osnap (Target), grid (Grid Dots), ortho (Arrow Move), otrack (Target Arrow), dynmode (Cursor Hover), properties (Panel Right), toolsets (Toolbox), cmdline (Window Console), pickstyle (Group), copybase (Copy Select), quickcalc (Calculator) | Microsoft Fluent UI System Icons, `microsoft/fluentui-system-icons` `main`, via `icon_fetch.fluent` | MIT |
| isoplane (`deployed_code`, an isometric cube), polar (`radar`), pasteblock (`content_paste_go`) | Google Material Symbols, weight 300, via `icon_fetch` `ms:` | Apache-2.0 |
| new, open, save, saveas, print, undo, copy, cut, paste, selectall, prefs | byte-identical copies of `../illustrator/icons/` (Fluent, MIT) | MIT |
| snap | copy of `../resolve/icons/snap.png`, the drawn horseshoe magnet (`nle_glyphs.snap`; neither Fluent nor Material has a magnet) | project's own (GPL-3.0-or-later) |

Labels that name a shared concept (New, Open, Save, Save as, Undo, Redo, Select all,
Copy, Cut, Paste, Close, Settings, Delete) are drawn by the shared concept renderer,
so their committed PNGs are unused in those cells (see the skill). The three
Shift variants of A/C/V set `shared: false` so they never fold onto their sibling's
concept.

## Program mark (ESC)

CADCraft's own app icon: `assets/app-icon/cadcraft.ico`, **64 px frame**, fetched at the
pinned commit by `program_marks.own_icon` (guarded: a committed `icons/cadcraft.png` is
never overwritten). The app-icon directory has no LICENSE file of its own; the repo's
`ATTRIBUTION.md` lists every `assets/app-icon/*` file as "CADCraft contributors,
MIT OR Apache-2.0", and the README says CADCraft's icons are original work under the
project licence. The ArtCraft brand in `docs/brand/` is a separate trademark and is
**not** used.

Sweep (frames 64/128/256 x `luma` t60-180 x `bright` t150-230, regions 37x32 and
40x40): the frames render identically, so the smallest converged one (64) is used.
`luma` t120 keeps the set-square, its inner triangle, the compass arc and the dot;
t150 and up light the blue tile into a solid block, `bright` loses the arc, t60-90
breaks the outline. Chosen: `program_icon_mode: luma`, `threshold: 120`,
`region: [40, 40]`, bottom-right, margin 0.

## Window matching

- Windows: `cadcraft.exe` (`packaging/windows/cadcraft.wxs:69`) -> `cadcraft`.
- macOS: bundle name `CADCraft` (`packaging/macos/Info.plist.in:9-14`) -> `cadcraft`.
- Linux: binary `cadcraft` (`apps/cadcraft/Cargo.toml`), app id / WM_CLASS
  `ai.storyteller.cadcraft` (`apps/cadcraft/src/main.rs:185,274`,
  `packaging/linux/ai.storyteller.cadcraft.desktop`).

Mapping key: `cadcraft,ai.storyteller.cadcraft`.
