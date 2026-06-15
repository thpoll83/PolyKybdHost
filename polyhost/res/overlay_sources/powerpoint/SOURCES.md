# Microsoft PowerPoint overlay — sources & provenance

Reproducible record. Re-run `fetch_icons.py` then `scripts/generate_app_overlays.py`
on `bindings.yaml` to rebuild.

## Shortcuts

Microsoft PowerPoint default keyboard shortcuts. Reference:
- https://support.microsoft.com/office/use-keyboard-shortcuts-to-create-powerpoint-presentations-ebb3d20e-dcd4-444f-a38e-bb5c5ed180f4

24 shortcuts spread across channels:
- **Ctrl** (R): New, Open, Save, Print, Ctrl+M New slide, Ctrl+D Duplicate, Copy,
  Cut, Paste, Undo, Redo, Select all, Bold, Italic, Underline, Hyperlink,
  Ctrl+G Group, Find
- **Shift** (B): Shift+F5 Start from current slide
- **Ctrl+Shift** (combo R): Ctrl+Shift+G Ungroup, Ctrl+Shift+C Copy format
- **plain** (A): F5 Slideshow, F7 Spelling, F12 Save as

Excluded: Win-key combos and Ctrl+Alt+Shift (not representable).

## Icons

All glyphs are **Microsoft Fluent UI System Icons (MIT)**
(`microsoft/fluentui-system-icons`, `main`,
`assets/<Name>/SVG/ic_fluent_*_24_regular.svg`); mapping in `fetch_icons.py`.
Notable PPT picks: New slide → "Slide Add", Duplicate → "Square Multiple",
Group / Ungroup → "Group" / "Group Dismiss", Slideshow → "Play", From current →
"Play Circle".

## Program icon (ESC, all layers)

`program_icon: powerpoint.png` is a **generic, license-clean mark drawn in code**
(no Microsoft logo): the Word-style trapezoid + knocked-out **P** + rounded rect
with text lines. Drawn by `_draw_powerpoint_logo()` in `fetch_icons.py`
(white-on-transparent → `program_icon_mode: alpha`). Intended to be hand-tuned.

## Transformations

`bindings.yaml`: `mode: luma`, `threshold: 150`, `region: [32, 28]`,
`anchor: bottom-right`; program icon bottom-right `[40, 36]`, `mode: alpha`.
Fluent `.svg` → cairosvg 96px in `fetch_icons.py`. Pin branch→SHA for byte-exact
reproducibility; committed `icons/` freeze the render.
