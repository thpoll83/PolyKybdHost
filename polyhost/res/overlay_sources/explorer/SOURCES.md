# Windows File Explorer overlay — sources & provenance

Reproducible record. Re-run `fetch_icons.py` then `scripts/generate_app_overlays.py`
on `bindings.yaml` to rebuild.

## Shortcuts

Windows 10/11 File Explorer default keyboard shortcuts. Reference:
- https://support.microsoft.com/windows/keyboard-shortcuts-in-windows-dcc61a57-8ff0-cffe-9796-cb9706c75eec
  (File Explorer section)

21 high-value, **representable** shortcuts. Excluded by the overlay format:
Win-key combos (e.g. Win+E to launch) and any Ctrl+Alt+Shift — both unsupported.
`Delete` appears twice: plain (recycle bin) and `Shift+Delete` (permanent) — same
key cell, different modifier channel. Back is on both `Backspace` and `Alt+Left`.

| key | action | key | action |
|---|---|---|---|
| Ctrl+C | Copy | F2 | Rename |
| Ctrl+X | Cut | Delete | Delete (recycle) |
| Ctrl+V | Paste | Shift+Delete | Delete (permanent) |
| Ctrl+Z | Undo | F5 | Refresh |
| Ctrl+Y | Redo | Backspace | Back |
| Ctrl+A | Select all | F11 | Full screen |
| Ctrl+F | Search | Alt+Enter | Properties |
| Ctrl+N | New window | Alt+Up | Up one level |
| Ctrl+W | Close | Alt+Left | Back |
| Ctrl+L | Address bar | Alt+Right | Forward |
| Ctrl+Shift+N | New folder | | |

## Icons — all MIT

All 39 glyphs + the program icon are **Microsoft Fluent UI System Icons (MIT)**
(`microsoft/fluentui-system-icons`, `main`,
`assets/<Name>/SVG/ic_fluent_*_24_regular.svg`) — the native style for a Microsoft
app and license-clean vs the GPL-3.0-or-later host. Mapping in `fetch_icons.py`
(`MS_ICONS`); each binding's `source:` notes the glyph.

## Program icon (ESC, all layers)

`program_icon: explorer.png` is drawn into the ESC cell across all channels
(every layer). It is a **committed, project-owned 32×32 white-on-black line-art
Explorer icon** (provided by the owner), rendered **1:1** — `mode: bright` (lights
the white pixels), `region: [32, 32]` (native, no scaling), bottom-right. The
fetch script leaves the committed `explorer.png` untouched. (Earlier default was a
generic Fluent "Folder"; the real Windows Explorer logo is proprietary, so this
hand-made b/w version is used instead.)

## Transformations

`bindings.yaml`: `mode: luma`, `threshold: 150`, `region: [36, 32]`,
`anchor: bottom-right`; program icon right-aligned, `[42, 34]`, `threshold: 170`.
Fluent `.svg` → cairosvg 96px in `fetch_icons.py`. To pin exact bytes against
upstream updates, replace `main` with a commit SHA; committed `icons/` freeze the
render regardless.

## Win-key (GUI) combos — protocol 12

Protocol 12 made all sixteen modifier variants addressable, so this set also
carries the Windows **shell** shortcuts that a user reaches for while a file
window has focus. They fill the tiers the Explorer commands alone would leave
empty, which is what makes this overlay the visual check that the GUI variants
render on hardware:

| Variant | File · channel | Shortcuts |
|---|---|---|
| `GUI` | `combo` · A | Win+E/D/L/R/I/V/X/S/P/Tab |
| `GUI+Shift` | `extra` · G | Win+Shift+S · +M · +←/→ |
| `GUI+Alt` | `extra` · B | Win+Alt+R · +PrtScn |
| `GUI+Ctrl` | `extra` · A | Win+Ctrl+D · +F4 · +←/→ |
| `GUI+Ctrl+Shift` | `gui` · R | Win+Ctrl+Shift+B |

`Ctrl+Alt+Shift` (extra · R) and the other three `gui` channels are **left
empty on purpose** — Windows defines no standard shortcut for them, and putting
an invented one on a keycap would be worse than a blank.

Two caveats worth knowing:

- **Win+Alt+R / Win+Alt+PrtScn are Xbox Game Bar**, so they do nothing if Game
  Bar is disabled or uninstalled. They are the only genuine `GUI+Alt` shell
  bindings Microsoft documents.
- **Win+Ctrl+Shift+B resets the graphics driver.** Real and documented, but it
  blanks the screen for a second — expected behaviour, not a fault.

Shortcut reference: Microsoft's Windows 11 keyboard-shortcut documentation
(cross-checked against the Windows 11 shortcut listings, 2026-08).
