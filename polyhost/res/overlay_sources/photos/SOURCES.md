# Windows Photos overlay — sources

## Shortcuts

⚠️ **Microsoft no longer publishes a shortcut table for Photos.** The old
*"Keyboard shortcuts in apps"* support page that carried the Photos / Maps /
Voice Recorder tables has been folded into the general Windows shortcuts page and
the per-app tables are gone (checked 2026-09-14; the URL still resolves and the
Photos section is simply absent).

So the **`notepad` rule** applies: every binding drawn here is one that **two
independent references agree on**.

* <https://winaero.com/the-list-of-keyboard-shortcuts-for-photos-app-in-windows-10/>
* <https://www.makeuseof.com/windows-photos-keyboard-shortcuts/>

✅ **One binding has a third, first-party witness.** `F5` = start slideshow was
harvested from the live app by our own UIA probe and appears in the field
`daemon_log.txt` (2026-09-14) as:

```
Shortcut icons for 'photos': 2 shortcut(s) harvested
  no icon (no icon concept matched the label): F5 'Start slideshow' Alt+Space 'System'
```

That is the app itself agreeing with both references — and it is also why that
harvest now reports **one** shortcut rather than two (`Alt+Space` is the window
manager's system menu; see `WINDOW_MANAGER_CHORDS`).

## What is NOT drawn, and why

| left off | why |
|---|---|
| Enhance | the two references **disagree** — `Ctrl+E` vs a bare `E`. No binding both support, so it is flagged rather than guessed |
| `Ctrl+N` new album | one reference only |
| `Ctrl+R` remove album | one reference only, **and it contradicts** the twice-corroborated `Ctrl+R` = rotate |
| `Win+H` share | the overlay format drops GUI-key layers entirely |
| `Esc` back / stop slideshow | the program mark owns ESC on every overlay in this repo |
| bare Spacebar / Enter / arrows | no modifier, and the keycap already shows the key |

⚠️ **`Ctrl++` / `Ctrl+-` assume a US layout**, the same assumption calc's
`@ # !` entries carry: zoom is bound to the *character*, so it lands wherever the
layout puts it. Everything else here is keyed by virtual key.

## Program mark

**None is baked, deliberately.** Photos runs as its own `Photos.exe`, so the
curated generic in `app_icons.yaml` (`photos: mdi:image-multiple`) resolves from
the process name — confirmed in the same field log (`Program icon for 'photos':
mdi:image-multiple`). A baked `program_icon:` would **win** over it and the
generic would never upload.

That is the opposite of `calc`, whose process is a host and which therefore has
to bake its own.

## Icons

All Microsoft Fluent UI System Icons (MIT), <https://github.com/microsoft/fluentui-system-icons>.

⚠️ **`zoomrst` is the bare magnifier, not "Zoom Fit".** Fit renders as four
arrows radiating from a box, which at 40x40 reads as the `Arrow Move` crop glyph
three keys away on this same overlay — two unrelated actions, one silhouette. The
plain magnifier instead completes the family its two neighbours already form
(magnifier+, magnifier−, magnifier). Decided by rendering the candidates side by
side, not from their names.

The two crop families use **one glyph per family, not per direction**: the
direction is the arrow key's own legend, which the firmware draws anyway.

## Reproducing

```bash
python polyhost/res/overlay_sources/photos/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/photos/bindings.yaml --preview /tmp/photos
```

Verified byte-identical on a re-run.
