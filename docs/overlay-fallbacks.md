# Overlay fall-backs: the program mark and the shortcut icons

A hand-made overlay covers the apps somebody has drawn one for. These two sources
cover the rest — they draw something useful on a keycap for an app with no
template at all, and they fill keys a template leaves blank.

Both ride `send_overlays_mru`'s **`synthetic=` seam**
(`device/synthetic_overlay.py`), which needs no firmware change: a duck-typed
converter returning `{keycode: OverlayData}` gets the MRU cache, the pool
allocation, the ROI/RLE encoders and the mapping commit for free.

## The two sources, and what their pseudo-filename has to carry

The rule that separates them is **what the name identifies**.

- **`@prog:<slug>`** — the focused app's brand mark on `ESC`
  (`services/app_icons.py` + `services/app_icon_fetcher.py`). The name carries the
  APP, because a mark differs per app by definition.
- **`@sc:<concept>:<height><placement>`** — an icon for one of the app's own
  shortcuts, on a key no hand-made template covers (`services/shortcut_source/` →
  `services/shortcut_overlays.py` → `services/shortcut_fetcher.py`). The name
  deliberately carries **no app**: a `save` icon is the same pixels whoever drew
  it, so Word and Notepad both drawing Save on `Ctrl+S` share one pool slot and
  one upload, and alt-tabbing between them re-sends nothing.

⚠️ **The render settings are part of that name because
`overlay_cache.get_or_allocate` returns an exact key hit WITHOUT comparing
bytes.** `@sc:save` alone would keep serving a 32 px mask out of the pool after
the user asked for 16, until the next reconnect cleared the cache. Anything that
changes the pixels belongs in the key.

⚠️ **A synthetic name whose converter came back `None` must be dropped from the
file list before `send_overlays_mru` sees it.** It hands an unrecognised name to
`ImageConverter.open()`, which cannot find a file called `@sc:save:32lower_left`
and returns False **for the whole send** — one undrawable icon costing every
hand-made overlay on the keyboard. Reachable whenever a mask is all-black
(`OverlayData` refuses one), and far likelier for shortcuts than for the single
program mark, since every icon is its own source.

## Coverage needs no host-side computation

The plan proposed computing the union of what the templates already draw. It was
wrong to: `send_overlays_mru` **already** skips a synthetic `(modifier, keycode)`
a real template claimed, *before* the upload — so template-wins is a device-layer
property and the caller computes no union. Building one host-side would re-do the
template decode the device layer already performs, to reach the same answer.

The one thing the caller decides is **order**: the program mark is appended before
the shortcut sources, so on `ESC` — the only key both can want — the app's
identity wins.

## `Shortcut.mods` IS `Modifier`'s value

⚠️ With no mapping in between. Both are the L/R-folded QMK nibble (bit0 Ctrl,
bit1 Shift, bit2 Alt, bit3 GUI), because both were written against the firmware's
`overlay_mod_variant()` — but they were defined independently, in
`shortcut_source.model` and `device.keys`.
`tests/services/shortcut_overlays_test.py` pins the agreement, since a
renumbering would put an icon under the **wrong** modifier rather than under none.

## What the harvest can reach is a measured ceiling, not a bug

- **Linux AT-SPI** finds shortcuts for **classic-menubar apps only**. An app whose
  menu lives in a hamburger popover exposes no accelerator at all, and GTK4
  answers `<VoidSymbol>` for every keybinding it has.
- **Windows UIA** is built but has **never run against a live application**.
- **macOS** has no backend, so the fall-back never fires there.

All three degrade to drawing nothing and saying which of the three it was in the
log. Do not read a quiet keyboard as broken.

## Both fetch threads exist because the alternatives are forbidden

The shortcut one more so: the harvest alone is a tree walk over **another
process** (a D-Bus round trip per node) before any icon is downloaded.
`overlay_for()` / `overlays_for()` are dict lookups that queue, and the answer
arrives through `on_ready` → `invalidate_window_cache(resend_same_entry=True)`.

⚠️ That flag is load-bearing: the answer lands for the app that is **still**
focused, so the re-match finds the same entry and the redundant-command guard
would drop it — measured on the program mark, where a Chrome icon took four
minutes and three activations to appear.

**An EMPTY harvest is cached like a missing mark.** Most apps yield nothing, so
without the negative cache every window switch would re-walk a tree already proven
empty.

## The two settings answer different questions

`shortcut_icons_enabled` and `shortcut_icon_auto_fetch` are not a coarse and a
fine switch over one thing:

- may another process's accessibility tree be read at all?
- may the network be used for an icon this install has not cached?

Someone on a locked-down machine wants the first; someone on a metered one wants
the second.

## `icon:` — when the process is not the app

The generic mark is looked up from the **app name**, which works as long as the
process is named after the app. On Windows 11 packaged apps it is not: the window
belongs to `ApplicationFrameHost.exe`, and Sticky Notes runs inside `ONENOTE.EXE`.
Such an entry is reached by window title, so the name the matcher started from
cannot resolve a mark — `icon:` on the mapping entry names the slug to use
instead. Full rules, including why a baked `program_icon:` wins over it and why
the parent entry must keep an `overlay:` of its own, are in
[`../polyhost/res/overlay-mapping.md`](../polyhost/res/overlay-mapping.md).
