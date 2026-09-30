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

Excluded: Win-key combos and Ctrl+Alt+Shift. ⚠️ Since protocol 12 BOTH are representable (Ctrl+Alt+Shift on the extra tier, GUI on combo A) — this line said otherwise and was stale. They are not drawn here because nobody has revisited the set, not because they cannot be.

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

## macOS

This spec also renders a macOS set (`outlook_template_mac.*`, 2026-09-28). Most bindings
are `CMDCTRL` (Ctrl on Windows/Linux, Cmd on macOS); the rest are listed below.

**Sources.** The official page is "Keyboard shortcuts for Outlook for Mac" (<https://support.microsoft.com/office/keyboard-shortcuts-for-outlook-for-mac-07ae68c8-b7af-4010-b225-324c04ac7335>; also `af188485-2c8e-4fcf-a5d2-76bc24edf9d0`). `support.microsoft.com` (and
`support.office.com`, `web.archive.org`, every third-party mirror tried) is
**blocked by this environment's egress proxy**, so both WebFetch and curl fail;
WebSearch snippets were too thin to quote. The chords were therefore read from
verbatim scrapes of the official Mac article kept on GitHub (raw.githubusercontent.com):
- `mutdmour/alfred-workflow-cheatsheet` `src/apps/outlook.py` (cites the MS article `07ae68c8…` in its source)
Where two scrapes disagreed or neither listed a chord, the binding is dropped on
macOS rather than guessed (marked *uncertain*). Re-check those against the live
Microsoft page when it is reachable.

⚠️ `match:` lists the Windows process name. Whether the macOS active-window
name (`Microsoft Outlook`) resolves to this stanza is decided by
`overlay-mapping.poly.yaml`, which this change does not touch.

| Action | Windows | macOS | Why |
|---|---|---|---|
| Forward | Ctrl+F | ⌘J | remapped |
| Search | Ctrl+E | ⌘⌥F | remapped (search current folder); ⌘E adds an attachment |
| Mark read | Ctrl+Q | ⌘T | remapped; ⌘Q would quit Outlook |
| Mark unread | Ctrl+U | ⌘⇧T | remapped |
| Hyperlink | Ctrl+K | ⌃⌘K | remapped; ⌘K is Send/Receive All |
| Next msg | Ctrl+. | ⌃] | remapped (plain `]` also listed) |
| Prev msg | Ctrl+, | ⌃[ | remapped (plain `[` also listed) |
| Flag | Ctrl+Shift+G | ⌃6 | remapped: ⌃6 = flag with a custom due date, the Mac analogue of the Windows Flag-for-follow-up dialog (⌃1–⌃5 flag with fixed dates) |
| Delete | Delete | ⌫ (Backspace) | remapped: the Mac "delete" key is Backspace |
| Send/Recv | F9 | ⌘K | remapped |
| Folder list | Ctrl+6 | — | dropped: no Mac chord (⌘6 unlisted) |
| Shortcuts | Ctrl+7 | — | dropped: ⌘7 is the Sync Status window on Mac |
| Go to date | Ctrl+G | — | dropped: ⌘G is Find next |
| Hang indent | Ctrl+T | — | dropped: not listed for the Mac composer; ⌘T is Mark read |
| Opt hyphen | Ctrl+- | — | dropped: ⌘- shrinks text size on Mac |
| New appt | Ctrl+Shift+A | — | dropped: Mac uses ⌘N inside the Calendar view; no global chord |
| New contact | Ctrl+Shift+C | — | dropped: ⌘⇧C copies the item to a folder on Mac |
| New task | Ctrl+Shift+K | — | dropped: ⌘⇧K sends all Outbox messages on Mac |
