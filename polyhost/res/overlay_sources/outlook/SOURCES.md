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

## Standard editing shortcuts (shared Fluent concepts, 2026-10-08)

Label = lexicon concept, no icon. support.microsoft.com was reachable this time:
- "Keyboard shortcuts for Outlook" (new + classic Outlook for Windows) —
  https://support.microsoft.com/en-us/accessibility/outlook/keyboard-shortcuts-for-outlook
- "Keyboard shortcuts in Outlook for Mac" —
  https://support.microsoft.com/en-us/accessibility/outlook/mac/keyboard-shortcuts-in-outlook-for-mac

| Concept | Windows | macOS | MS wording |
|---|---|---|---|
| Open | Ctrl+O | ⌘O | "Open the selected item" / "Open a received message" |
| Cut / Copy / Paste | Ctrl+X/C/V | ⌘X/C/V | "Edit text" table / "Edit and format text" |
| Undo | Ctrl+Z | ⌘Z | "Reverse the most recent action" / "Undo the last action" |
| Redo | — | ⌘Y (`only: [macos]`) | Mac: "Redo the last action ⌘Y" |
| Select all | Ctrl+A | ⌘A | "Select all items" / "Select all items in the item list" |
| Find | F4 (`only: [windows, linux]`) | ⌘F (`only: [macos]`) | classic: "Find or replace text F4"; Mac: "Find text within an item" |
| Find next | Shift+F4 | ⌘G | classic: "Find the next item"; Mac: "Find the next instance…" |
| Replace | Ctrl+H (`only: [windows, linux]`) | — | classic: "Find and replace text … in an open item" |
| Close | — | ⌘W (`only: [macos]`) | Mac: "Close the active window" |

Not added / why:
- Redo on Windows: Ctrl+Y is "Go to a different folder" (classic) / "Go to the
  Folder pane" (new Outlook); new Outlook's text table also lists Ctrl+Y as
  "Repeat", so the chord is ambiguous — not drawn.
- Find on Windows as Ctrl+F: Ctrl+F is Forward (already drawn).
- Replace on macOS: the Mac article lists no chord.
- Close on Windows: the article lists Esc only.
- New / Save / Print: already bound above.
- Zoom in/out: the Mac article's ⌘+/⌘- change only the message text size, and
  Windows has no chord; not drawn.

## F2 / F5 (no modifier, 2026-10-08)

The firmware no longer draws a built-in Rename/Refresh hint on F2/F5 for every
app, so the overlay carries them only where Outlook really does that.

| Key | Platform | Drawn as | Confirmed by |
|---|---|---|---|
| F2 | Windows (`only: [windows, linux]`) | Rename (`icon: rename.png`) | <https://support.microsoft.com/en-us/office/keyboard-shortcuts-for-outlook-3cdeb221-7ae5-4c1d-8c1d-9e63216c1efd> — classic Outlook, "Use the Folder pane": "F2 — Rename a selected folder in the list of folders." |

`icons/rename.png` is a byte-identical copy of `../explorer/icons/rename.png`
(Microsoft Fluent UI System Icons "Rename", MIT). Rename is not a shared lexicon
concept, so it is drawn from the file. It is not produced by `fetch_icons.py`.

Not added:
- **F5 Reload** — the same page's only bare-F5 row is "Update a list of contact
  group members" (People), not a view refresh; F9 is Send/Receive (already drawn).
- **macOS** — the documented F2 rename is classic Outlook for Windows; it is not
  carried over to the Mac set.
