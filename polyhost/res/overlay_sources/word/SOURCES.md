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

Excluded: Win-key combos and Ctrl+Alt+Shift. ⚠️ Since protocol 12 BOTH are representable (Ctrl+Alt+Shift on the extra tier, GUI on combo A) — this line said otherwise and was stale. They are not drawn here because nobody has revisited the set, not because they cannot be. The ribbon
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

## macOS

This spec also renders a macOS set (`word_template_mac.*`, 2026-09-28). Most bindings
are `CMDCTRL` (Ctrl on Windows/Linux, Cmd on macOS); the rest are listed below.

**Sources.** The official page is "Keyboard shortcuts in Word" (Mac tab / "Keyboard shortcuts in Word for Mac", <https://support.microsoft.com/office/keyboard-shortcuts-in-word-95ef89dd-7142-4b50-afb2-f762f663ceb2>, Mac article id `3256d48a-7967-475d-be81-a6e3e1284b25`). `support.microsoft.com` (and
`support.office.com`, `web.archive.org`, every third-party mirror tried) is
**blocked by this environment's egress proxy**, so both WebFetch and curl fail;
WebSearch snippets were too thin to quote. The chords were therefore read from
verbatim scrapes of the official Mac article kept on GitHub (raw.githubusercontent.com):
- `amiechen/pretzel` `shortcuts/Microsoft Word.yml` (the MS article's tables, incl. its Mission Control notes)
- `mutdmour/alfred-workflow-cheatsheet` `src/apps/microsoftWord.py`
- ⌘N/⌘O/⌘S/⌘W/⌘K/⌘A (not in either scrape) follow the standard Mac/Office-for-Mac file chords ("Common Office for Mac keyboard shortcuts")
Where two scrapes disagreed or neither listed a chord, the binding is dropped on
macOS rather than guessed (marked *uncertain*). Re-check those against the live
Microsoft page when it is reachable.

⚠️ `match:` lists the Windows process name. Whether the macOS active-window
name (`Microsoft Word`) resolves to this stanza is decided by
`overlay-mapping.poly.yaml`, which this change does not touch.

| Action | Windows | macOS | Why |
|---|---|---|---|
| Find | Ctrl+F | ⌃F (literal CTRL, unchanged) | both scrapes list Control+F ("places the focus in the Search box") |
| Replace | Ctrl+H | ⌃H (literal CTRL, unchanged) | both scrapes: Control+H; ⌘H is the system Hide |
| Indent | Ctrl+M | ⌃⇧M | remapped; ⌘M is the system Minimize (⌘⇧M *removes* the indent) |
| Go to | Ctrl+G | ⌘⌥G | remapped (also F5) |
| Save as | F12 | ⌘⇧S | remapped; F12 is not a Word-for-Mac chord |
| Opt hyphen | Ctrl+- | — | dropped, *uncertain*: neither scrape lists an optional-hyphen chord (⌘⇧- is the NON-breaking hyphen) |
| Clear fmt | Ctrl+Q | — | dropped, *uncertain*: not in either scrape; ⌘Q quits Word |
| Change case | Shift+F3 | ⇧F3 | unchanged (listed on Mac) |
| Spelling | F7 | F7 | unchanged (listed in the Mac function-key table; also ⌘⌥L) |

## Standard editing chords (shared Fluent concepts, 2026-10)

Added in the `# --- standard editing (shared Fluent concepts) ---` block:

| Chord | Platform | Confirmed by |
|---|---|---|
| Shift+F4 — Find next ("repeats the last Find or Go To action") | Windows (+Linux set) | https://support.microsoft.com/en-us/office/keyboard-shortcuts-in-word-95ef89dd-7142-4b50-afb2-f762f663ceb2 |
| Cmd+F — Find | macOS | same page, Mac table ("Command+F: Find text") — the existing `CTRL+F` Find is literal Ctrl on macOS |

Deliberately NOT added:

- **Zoom (Ctrl+Plus / Ctrl+Minus)**: Ctrl+= is Subscript and Ctrl+- the optional hyphen
  (both already drawn), so the "Plus sign" chord cannot be placed on a cell without
  contradicting them.
- **Find next on macOS**: the Mac table's Shift+F4 row is not clearly a Mac chord.
- Close and Replace (Ctrl+H, also Mac's Control+H) were already drawn.
