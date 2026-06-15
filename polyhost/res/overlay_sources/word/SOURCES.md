# Microsoft Word overlay — sources & provenance

Reproducible record. Re-run `fetch_icons.py` then `scripts/generate_app_overlays.py`
on `bindings.yaml` to rebuild.

## Shortcuts

Microsoft Word default keyboard shortcuts. Reference:
- https://support.microsoft.com/office/keyboard-shortcuts-in-word-95ef89dd-7142-4b50-afb2-f762f663ceb2

26 high-value shortcuts spread across channels:
- **Ctrl** (R): New, Open, Save, Print, Copy, Cut, Paste, Undo, Redo, Select all,
  Bold, Italic, Underline, Ctrl+D Font dialog, Hyperlink, Align L/Center/R/Justify,
  Find, Replace, Go to
- **Shift** (B): Shift+F3 Change case
- **Ctrl+Shift** (combo R): Ctrl+Shift+C Copy format, Ctrl+Shift+L Bullet list
- **plain** (A): F7 Spelling, F12 Save as

Excluded: Win-key combos and Ctrl+Alt+Shift (not representable). The ribbon
Alt-keytips are not single shortcuts and are omitted.

## Icons — all MIT

All 25 glyphs + the program-icon placeholder are **Microsoft Fluent UI System
Icons (MIT)** (`microsoft/fluentui-system-icons`, `main`,
`assets/<Name>/SVG/ic_fluent_*_24_regular.svg`). Mapping in `fetch_icons.py`;
each binding's `source:` notes the glyph.

Weaker matches worth knowing: **Replace** → "Arrow Swap" (no dedicated
find-replace glyph), **Go to** → "Arrow Down", **Copy format** → "Paint Brush"
(format painter).

## Program icon (ESC, all layers)

`program_icon: word.png` is a **generic, license-clean mark drawn in code** (no
Microsoft logo): a 90°-rotated trapezoid on the left with a **W** stamped out
(negative space) + text lines on the right. Drawn by `_draw_word_logo()` in
`fetch_icons.py` (white-on-transparent → `program_icon_mode: alpha`), so it is
fully reproducible and carries no trademark/licence risk.

## Transformations

`bindings.yaml`: `mode: luma`, `threshold: 150`, `region: [32, 28]`,
`anchor: bottom-right`; program icon bottom-right `[40, 36]`, `threshold: 160`.
Fluent `.svg` → cairosvg 96px in `fetch_icons.py`. Pin branch→SHA for byte-exact
reproducibility; committed `icons/` freeze the render.
