# Microsoft Excel overlay — sources & provenance

Reproducible record. Re-run `fetch_icons.py` then `scripts/generate_app_overlays.py`
on `bindings.yaml` to rebuild.

## Shortcuts

Microsoft Excel default keyboard shortcuts. Reference:
- https://support.microsoft.com/office/keyboard-shortcuts-in-excel-1798d9d5-842a-42b8-9c99-9b7213f0040f

24 shortcuts spread across channels:
- **Ctrl** (R): New, Open, Save, Print, Copy, Cut, Paste, Undo, Redo, Select all,
  Bold, Italic, Underline, Hyperlink, Ctrl+1 Format cells, Find, Replace
- **Alt** (G): Alt+= AutoSum
- **Ctrl+Shift** (combo R): Ctrl+Shift+L Filter, Ctrl+Shift+4 Currency,
  Ctrl+Shift+5 Percent
- **plain** (A): F2 Edit cell, F4 Absolute ref, F9 Calculate, F12 Save as

Excluded: Win-key combos and Ctrl+Alt+Shift (not representable).

## Icons

All glyphs are **Microsoft Fluent UI System Icons (MIT)**
(`microsoft/fluentui-system-icons`, `main`,
`assets/<Name>/SVG/ic_fluent_*_24_regular.svg`); mapping in `fetch_icons.py`.

Number-format shortcuts render as **text symbols** for clarity: Percent =
`%` (text label, no icon), Currency = "Money" glyph. Other notable picks:
Format cells → "Table Settings", Abs ref (F4) → "Lock Closed", AutoSum →
"Math Formula", Replace → "Arrow Swap".

## Program icon (ESC, all layers)

`program_icon: excel.png` is a **generic, license-clean mark drawn in code** (no
Microsoft logo): identical to the Word mark (trapezoid + knocked-out letter +
rounded rect) but with an **X** and **dashed** lines on the right (spreadsheet
feel). Drawn by `_draw_excel_logo()` in `fetch_icons.py` (white-on-transparent →
`program_icon_mode: alpha`).

## Transformations

`bindings.yaml`: `mode: luma`, `threshold: 150`, `region: [32, 28]`,
`anchor: bottom-right`; program icon bottom-right `[40, 36]`, `mode: alpha`.
Fluent `.svg` → cairosvg 96px in `fetch_icons.py`. Pin branch→SHA for byte-exact
reproducibility; committed `icons/` freeze the render.
