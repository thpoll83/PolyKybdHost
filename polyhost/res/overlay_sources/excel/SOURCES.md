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

Excluded: Win-key combos and Ctrl+Alt+Shift. ⚠️ Since protocol 12 BOTH are representable (Ctrl+Alt+Shift on the extra tier, GUI on combo A) — this line said otherwise and was stale. They are not drawn here because nobody has revisited the set, not because they cannot be.

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

## macOS

This spec also renders a macOS set (`excel_template_mac.*`, 2026-09-28). Most bindings
are `CMDCTRL` (Ctrl on Windows/Linux, Cmd on macOS); the rest are listed below.

**Sources.** The official page is "Keyboard shortcuts in Excel" (Mac tab / "Keyboard shortcuts in Excel for Mac", <https://support.microsoft.com/office/keyboard-shortcuts-in-excel-1798d9d5-842a-42b8-9c99-9b7213f0040f>). `support.microsoft.com` (and
`support.office.com`, `web.archive.org`, every third-party mirror tried) is
**blocked by this environment's egress proxy**, so both WebFetch and curl fail;
WebSearch snippets were too thin to quote. The chords were therefore read from
verbatim scrapes of the official Mac article kept on GitHub (raw.githubusercontent.com):
- `amiechen/pretzel` `shortcuts/Microsoft Excel.yml` (the MS Excel-for-Mac article's tables)
- `mutdmour/alfred-workflow-cheatsheet` `src/apps/microsoftExcel.py`
Where two scrapes disagreed or neither listed a chord, the binding is dropped on
macOS rather than guessed (marked *uncertain*). Re-check those against the live
Microsoft page when it is reachable.

⚠️ `match:` lists the Windows process name. Whether the macOS active-window
name (`Microsoft Excel`) resolves to this stanza is decided by
`overlay-mapping.poly.yaml`, which this change does not touch.

| Action | Windows | macOS | Why |
|---|---|---|---|
| Replace | Ctrl+H | ⌃H (literal CTRL, unchanged) | both scrapes list Control+H (pretzel also ⌘⇧H) |
| Go to | Ctrl+G | ⌃G (unchanged) | both scrapes; also F5 |
| New table | Ctrl+T | ⌃T (unchanged) | both scrapes list Control+T; ⌘T toggles absolute refs while editing |
| Delete cells | Ctrl+- | ⌃- (unchanged) | both scrapes list Control+Hyphen |
| Dependents / Precedents | Ctrl+] / Ctrl+[ | ⌃] / ⌃[ (unchanged) | alfred lists ⌃[ and ⌃]; pretzel lists ⌃] |
| Fill down / Fill right | Ctrl+D / Ctrl+R | ⌃D / ⌃R (unchanged) | both scrapes list Control (pretzel also ⌘) |
| Filter | Ctrl+Shift+L | ⌃⇧L (unchanged) | pretzel: "Cmd+Shift+F or Ctrl+Shift+L"; ⌘⇧L is Modify Cell Style, so CMDCTRL would be WRONG |
| Currency / % | Ctrl+Shift+4 / 5 | ⌃⇧$ / ⌃⇧% (unchanged) | pretzel lists Control; note ⌘⇧4 would be the system screenshot |
| Strikethrough | Ctrl+5 | ⌘⇧X | remapped |
| AutoSum | Alt+= | ⌘⇧T | remapped |
| Flash fill | Ctrl+E | — | dropped, *uncertain*: not in either scrape; ⌘E is Align center |
| Table | Ctrl+L | — | dropped: on Mac Control+L is Define Name (pretzel); Mac's create-table chord is ⌃T/⌘T, already drawn |
| F2 / F4 / F9 / F12 | same | same | unchanged (all listed in the Mac function-key table) |

## Standard editing chords (shared Fluent concepts, 2026-10)

Added in the `# --- standard editing (shared Fluent concepts) ---` block:

| Chord | Platform | Confirmed by |
|---|---|---|
| Ctrl+Alt+= — Zoom in | Windows (+Linux set) | https://support.microsoft.com/en-us/office/keyboard-shortcuts-in-excel-1798d9d5-842a-42b8-9c99-9b7213f0040f ("Zoom in: Ctrl+Alt+Equal sign (=)") |
| Ctrl+Alt+- — Zoom out | Windows (+Linux set) | same ("Zoom out: Ctrl+Alt+Minus sign (-)") |

Deliberately NOT added:

- **Find next (Shift+F4)**: documented only for Excel for the web, not desktop Windows.
- **Zoom on macOS**: not documented on the Mac table.
- Close (Ctrl+W), Replace (Ctrl+H, which also covers Mac's Ctrl+H) were already drawn.
