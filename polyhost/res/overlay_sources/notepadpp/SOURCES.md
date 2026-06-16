# Notepad++ overlay — sources & provenance

Reproducible record for the Notepad++ keycap overlays. Re-run `fetch_icons.py`
then `scripts/generate_app_overlays.py` on `bindings.yaml` to rebuild.

## Shortcuts

Notepad++ default keymap (out-of-the-box accelerators). Reference:
- https://npp-user-manual.org/docs/preferences/#shortcut-mapper
- A user's `%AppData%\Notepad++\shortcuts.xml` overrides these — edit
  `bindings.yaml` to match a customised keymap.

21 high-frequency file/edit/search/run actions. Win-key and Ctrl+Alt+Shift
combos are excluded (not representable — see `../../overlay_specification.md`).

## Icons — all-MIT (license-clean)

PolyKybdHost is **GPL-3.0-or-later**; **all 20 shortcut
glyphs come from Microsoft Fluent UI System Icons (MIT)** in one consistent flat
style. One glyph is custom-drawn. (An earlier revision used Notepad++'s own
GPL-3.0 toolbar icons — switched to all-MIT deliberately.)

### 20 from Microsoft Fluent UI System Icons (MIT)
`microsoft/fluentui-system-icons`, branch `main`,
`assets/<Name>/SVG/ic_fluent_*_24_regular.svg`:

| action | Fluent glyph | action | Fluent glyph |
|---|---|---|---|
| new | Document Add | selectall | Select All On |
| open | Folder Open | duplicate (Dup line) | Row Triple |
| save | Save | comment | Comment |
| saveall | Save Multiple | find | Search |
| print | Print | replace | Arrow Swap |
| close | Document Dismiss | goto (Go to line) | Arrow Down |
| copy | Copy | findnext | Chevron Right |
| cut | Cut | findfiles | Document Search |
| paste | Clipboard Paste | run (F5) | Play |
| undo | Arrow Undo | redo | Arrow Redo |

Line/row-specific glyphs are chosen where a generic one would mislead
(duplicate → Row Triple, not "Document Copy").

### 1 custom-drawn (CC0 / project-owned)
- deleteline (Del line) — text rows with a strike-through, drawn by
  `_draw_deleteline()` in `fetch_icons.py` (white-on-transparent, `mode: alpha`).
  A generic trash glyph reads as delete-*file*.

## Program icon (ESC, all layers)

`bindings.yaml`'s `program_icon: npp.png` is drawn into the **ESC cell across all
channels of both PNGs** (every modifier layer), marking which overlay set is
loaded. Source: the **Notepad++ chameleon mascot** — a black-on-white line-art
asset committed directly as `icons/npp.png` (provided by the project owner;
Notepad++ logo / trademark, used for identification). It is a **committed asset**,
not fetched: `fetch_icons.py` leaves it untouched so a re-run never clobbers it.

## Transformations

- `fetch_icons.py`: Fluent `.svg` → cairosvg 96px; program icon `.ico` → 256px;
  custom strike drawn at 96px.
- `bindings.yaml`: `mode: luma`, `threshold: 150`, `region: [36, 32]`,
  `anchor: bottom-right`; deleteline overrides `mode: alpha`. Program icon:
  full-cell (`[72, 40]`), centred, `mode: luma`, `threshold: 170`.
- The generator places shortcut icons bottom-right of each cell, the program icon
  full-cell on ESC, and thresholds to 1-bit.

To pin exact bytes against upstream updates, replace the branch names in
`fetch_icons.py` with commit SHAs. The committed `icons/` freeze the render.
