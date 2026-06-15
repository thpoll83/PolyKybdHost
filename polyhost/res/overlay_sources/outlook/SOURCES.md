# Microsoft Outlook overlay — sources & provenance

Reproducible record. Re-run `fetch_icons.py` then `scripts/generate_app_overlays.py`
on `bindings.yaml` to rebuild.

## Shortcuts

Microsoft Outlook default keyboard shortcuts. Reference:
- https://support.microsoft.com/office/keyboard-shortcuts-for-outlook-3cdeb221-7ae5-4c1d-8c1d-9e63216c1efd

23 shortcuts spread across channels. **Outlook quirks captured**: `Ctrl+F` =
Forward (not Find) and `Ctrl+E` = Search.
- **Ctrl** (R): New mail, Reply, Forward, Ctrl+Enter Send, Print, Save, Search,
  Mark read (Q), Mark unread (U), Hyperlink, Bold, Italic, and module switch
  Ctrl+1-4 (Mail / Calendar / People / Tasks)
- **Ctrl+Shift** (combo R): Reply all, New appointment, New contact, New task, Flag
- **plain** (A): Delete, F9 Send/Receive

Excluded: Win-key combos and Ctrl+Alt+Shift (not representable).

## Icons

All glyphs are **Microsoft Fluent UI System Icons (MIT)**
(`microsoft/fluentui-system-icons`, `main`,
`assets/<Name>/SVG/ic_fluent_*_24_regular.svg`); mapping in `fetch_icons.py`.

## Program icon (ESC, all layers)

`program_icon: outlook.png` is a **generic, license-clean mark drawn in code**
(no Microsoft logo): the Word-style trapezoid + knocked-out **O** + rounded rect
with text lines. Drawn by `_draw_outlook_logo()` in `fetch_icons.py`
(white-on-transparent → `program_icon_mode: alpha`). Intended to be hand-tuned.

## Transformations

`bindings.yaml`: `mode: luma`, `threshold: 150`, `region: [32, 28]`,
`anchor: bottom-right`; program icon bottom-right `[40, 36]`, `mode: alpha`.
Fluent `.svg` → cairosvg 96px in `fetch_icons.py`. Pin branch→SHA for byte-exact
reproducibility; committed `icons/` freeze the render.
