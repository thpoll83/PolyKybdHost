# Windows Notepad overlay — sources & provenance

Reproducible record for the Windows Notepad keycap overlays. Re-run
`fetch_icons.py` then `scripts/generate_app_overlays.py` on `bindings.yaml`
to rebuild.

## Shortcuts

⚠️ **Notepad is closed source**, so there is no equivalent of Windows Terminal's
`defaults.json` to read. The rule applied here: **wire only what two independent
references agree on**, and record the rest as unverified. A wrong icon is worse
than a missing one, because the user believes it.

References used:
- https://scottsekinger.com/2026/02/02/windows-notepad-keyboard-shortcuts-complete-guide/
- https://qwerty.school/hotkeys/windows-notepad

Microsoft's own *Keyboard shortcuts in Windows* support page was checked and has
**no Notepad section** at all, so there is no first-party list to cite.

29 bindings are wired: file, edit, search, zoom, tabs and word/document
navigation.

### Claimed by only ONE reference — deliberately NOT wired

Confirm these on a real Windows 11 Notepad before adding them; each would be an
invented meaning on this evidence.

| binding | claimed action | note |
|---|---|---|
| `F12` | Save as | the other reference gives `Ctrl+Shift+S`, which IS wired |
| `Ctrl+Up` / `Ctrl+Down` | scroll without moving the cursor | standard rich-edit behaviour, but unconfirmed for Notepad |
| `Ctrl+Shift+C` | copy full file path | reads like the Explorer shortcut of the same name |
| `Alt+Shift+Left/Right` | move tab | one reference only |
| `F1` | help | Windows 11 Notepad has no help window |

### Excluded as unrepresentable or not app-specific

`Alt+F4` (close app), `Alt+Space` (window system menu), `Alt+F/E/O/V` (menu
access keys — every Win32 app has these), `Ctrl+mouse wheel` (not a key), and
plain `Home`/`End`/`Delete`/`Backspace`/arrow keys (OS-level text editing, not
Notepad features). Win-key and Ctrl+Alt+Shift combos are not representable at
all — see `../../overlay_specification.md`.

## Icons — all-MIT plus one drawn asset (license-clean)

PolyKybdHost is **GPL-3.0-or-later**. 29 glyphs come from **Microsoft Fluent UI
System Icons (MIT)**: `microsoft/fluentui-system-icons`, branch `main`,
`assets/<Name>/SVG/ic_fluent_<snake>_24_regular.svg`. The exact folder per action
is the `MS_ICONS` table in `fetch_icons.py`; every name there was probed against
raw.githubusercontent.com before use (there is no *Save As* folder, no *Calendar
Ltr*, no *Text Bullet List Ltr*).

**Where an action also exists in Notepad++, the SAME glyph is used** (new, open,
save, print, close, undo, redo, cut, copy, paste, select all, find, replace) so
the two editors' overlays read alike rather than looking like different products.

Choices that are not the obvious one, and why:

| action | glyph | why |
|---|---|---|
| go to line | Text Position Line | a cursor between two rules; a bare down-arrow would read as "scroll down" |
| reset zoom | Zoom Fit | the only Fluent zoom glyph that is neither in nor out |
| reopen closed tab | Arrow Hook Up Left | sits in the Ctrl+Shift layer, so it never appears beside Ctrl+Z undo |
| top / end of document | Arrow Upload / Download | an arrow into a line = "to the end" (same pairing as the Windows Terminal overlay) |
| word left / right | Arrow Previous / Next | an arrow against a bar = "jump to the next boundary" |

### Drawn here, not downloaded

**`notepad.png` — the ESC program mark.** Notepad's real product icon is
Microsoft **trademark art**, so it is not redistributed. Drawn instead: a lined
page with a folded corner. White on transparent, rendered with
`program_icon_mode: alpha`. ⚠️ Guarded in `fetch_icons.py`: once committed, the
PNG is the source of truth and a re-run leaves it alone, so a hand-tune survives.

## Rebuild

```bash
python polyhost/res/overlay_sources/notepad/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/notepad/bindings.yaml --preview /tmp/notepad_preview
```
