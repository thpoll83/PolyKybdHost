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

Excluded: Win-key combos and Ctrl+Alt+Shift. ⚠️ Since protocol 12 BOTH are representable (Ctrl+Alt+Shift on the extra tier, GUI on combo A) — this line said otherwise and was stale. They are not drawn here because nobody has revisited the set, not because they cannot be.

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

## macOS

This spec also renders a macOS set (`powerpoint_template_mac.*`, 2026-09-28). Most bindings
are `CMDCTRL` (Ctrl on Windows/Linux, Cmd on macOS); the rest are listed below.

**Sources.** The official page is "Use keyboard shortcuts to create PowerPoint presentations" (Mac tab, <https://support.microsoft.com/office/use-keyboard-shortcuts-to-create-powerpoint-presentations-ebb3d20e-dcd4-444f-a38e-bb5c5ed180f4>). `support.microsoft.com` (and
`support.office.com`, `web.archive.org`, every third-party mirror tried) is
**blocked by this environment's egress proxy**, so both WebFetch and curl fail;
WebSearch snippets were too thin to quote. The chords were therefore read from
verbatim scrapes of the official Mac article kept on GitHub (raw.githubusercontent.com):
- `amiechen/pretzel` `shortcuts/Microsoft PowerPoint.yml` (the MS PowerPoint-for-Mac article's tables)
- Copy format ⌘⇧C: WebSearch snippet (indezine.com "Keyboard Shortcuts for PowerPoint 2016 for Mac": "Command+Shift+C copies object attributes")
Where two scrapes disagreed or neither listed a chord, the binding is dropped on
macOS rather than guessed (marked *uncertain*). Re-check those against the live
Microsoft page when it is reachable.

⚠️ `match:` lists the Windows process name. Whether the macOS active-window
name (`Microsoft PowerPoint`) resolves to this stanza is decided by
`overlay-mapping.poly.yaml`, which this change does not touch.

| Action | Windows | macOS | Why |
|---|---|---|---|
| New slide | Ctrl+M | ⌘⇧N | remapped; ⌘M is the system Minimize |
| Group | Ctrl+G | ⌘⌥G | remapped |
| Ungroup | Ctrl+Shift+G | ⌘⌥⇧G | remapped |
| Font + | Ctrl+] | ⌘⇧> (on the `.` key) | remapped |
| Font - | Ctrl+[ | ⌘⇧< (on the `,` key) | remapped |
| From current | Shift+F5 | ⌘Return | remapped |
| Slideshow | F5 | ⌘⇧Return | remapped |
| Save as | F12 | ⌘⇧S | remapped |
| Replace | Ctrl+H | — | dropped, *uncertain*: not in the scrape; ⌘H is the system Hide |
| Subscript | Ctrl+= | — | dropped, *uncertain*: not in the scrape |
| Spelling | F7 | — | dropped, *uncertain*: F7 not listed for PowerPoint for Mac |

## Standard editing chords (shared Fluent concepts, 2026-10)

Added in the `# --- standard editing (shared Fluent concepts) ---` block:

| Chord | Platform | Confirmed by |
|---|---|---|
| Shift+F4 — Find next ("Repeat the last Find action") | Windows (+Linux set) | https://support.microsoft.com/en-us/office/use-keyboard-shortcuts-to-create-powerpoint-presentations-ebb3d20e-dcd4-444f-a38e-bb5c5ed180f4 |
| Cmd+Shift+H — Replace ("Open the Find and Replace pane") | macOS | same page, Mac table |

Deliberately NOT added:

- **Zoom (Ctrl+Plus / Ctrl+Minus)**: Ctrl+= is Subscript (already drawn); the Plus-sign
  chord would contradict it, so left off on both platforms.
- Close (Cmd+W / Ctrl+W) and Find were already drawn.
