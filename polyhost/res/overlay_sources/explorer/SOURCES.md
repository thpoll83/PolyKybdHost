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

All 20 glyphs + the program icon are **Microsoft Fluent UI System Icons (MIT)**
(`microsoft/fluentui-system-icons`, `main`,
`assets/<Name>/SVG/ic_fluent_*_24_regular.svg`) — the native style for a Microsoft
app and license-clean vs the GPL-2.0 host. Mapping in `fetch_icons.py`
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
