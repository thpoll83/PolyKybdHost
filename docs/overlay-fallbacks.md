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

## The two catalog files, and the judgements behind them

`polyhost/res/app_icons.yaml` and `polyhost/res/shortcut_hints.yaml` carry short
comments saying what goes in them. The reasoning that used to sit in those
headers lives here, so the files stay readable for someone adding an entry.

### Why the simple-icons version is pinned

Every slug in `app_icons.yaml` was verified against **simple-icons 15.22.0**;
v16 REMOVED brands (see `app_icons.py`). A slug that does not exist costs a
fetch and a curation entry on every switch to that app, and a slug that exists
for a DIFFERENT brand draws a wrong logo — the one failure the resolver cannot
detect itself. So: check, never write one from memory.

### Why some entries name `mdi:` instead

Simple Icons has **no Microsoft and no Adobe at all** (measured by substring over
the whole collection), so the Office family, Visual Studio and Edge come from
Material Design Icons, which draws them as monochrome single-path glyphs that
render cleanly at 40×40. A bare `mdi:` name is usually a generic UI symbol
rather than a brand, which is why each one is listed individually rather than
guessed — see the note in `app_icons.candidates()`.

### ⚠️ Adobe products share the company "A", because nothing finer survives 1 bit

The obvious better answer — the `logos:` collection's `adobe-photoshop`,
`adobe-illustrator`, `adobe-premiere`, `adobe-indesign`, `adobe-lightroom`,
`adobe-after-effects`, all CC0 — was rendered and looked at: the product letters
("Ps", "Ai") are SEPARATE COLOURED PATHS rather than knockouts, so flattening to
a silhouette gives six identical solid rounded squares of 1516 lit pixels. Six
apps showing the same white block is worse than one shared "A" that at least
says Adobe. Acrobat keeps its own mark.

### ⚠️ `chromium -> google-chrome` stays out, on a different rule

It names a DIFFERENT PRODUCT (a different browser), where the Adobe "A" is the
true company. `explorer -> microsoft-windows` was out for the same reason and is
still out — Explorer gets a plain folder from the generic section instead.

### ⚠️ The generic section breaks the "product mark, never a generic symbol" rule

Deliberately, and it is easy to delete if you disagree with the trade. The first
field report of this feature was *"so far nothing"* (2026-09-10), and a third of
the reason was here: Windows' own bundled apps have no brand mark in either
catalog. Measured against both — Notepad, Paint, Paint.NET, Windows Terminal,
WordPad, Snipping Tool, Task Manager, Explorer, 7-Zip, PuTTY, WinSCP: **ZERO
hits**, in Simple Icons or in mdi, under any spelling the resolver guesses.
Microsoft does not license those logos and mdi does not draw them.

So the choice is a symbol that says WHAT THE APP IS, or nothing at all. The repo
already made that call once: the hand-made `explorer_template` draws a folder on
ESC. A folder identifies Explorer, a palette identifies Paint, and `>_`
identifies a terminal — which is the whole job of the mark. What it must never
do is name the wrong BRAND, which is why every entry there is a neutral object
rather than another company's logo. Each was rendered at the real 40×40 and
looked at; a symbol that does not survive 1 bit is worse than no icon.

### ⚠️ A hosted app cannot be listed in `app_icons.yaml` at all

On Windows 11 Calculator, Clock and the other packaged apps run inside
`ApplicationFrameHost.exe`, so the app name the window tracker reports is the
HOST — and the same happens outside the packaged-app world, where the new Sticky
Notes runs inside `ONENOTE.EXE` (both measured in one field log, 2026-09-14).
Their identity is in the window TITLE, which that file cannot key on, so
`calculator: mdi:calculator` there would look like coverage and resolve for
nobody. `PURE_HOST_PROCESSES` + `app_from_host_title()` handle the generic case;
`icon:` on a mapping entry is how a specific one names its mark.

⚠️ For `onenote` that is not just a gap but a WRONG icon waiting to happen: the
entry maps it to `mdi:microsoft-onenote`, so a Sticky Notes window would draw a
OneNote logo unless its mapping entry names its own.

### `shortcut_hints.yaml` is half of a feedback loop

The lexicon in `shortcut_icons.py` holds the general rules; the YAML holds the
JUDGEMENTS — labels a real application uses that the rules miss or get wrong.
`shortcut_probe.py --unmatched <file>` logs every label that produced no icon,
with a count and the apps it came from; `--review <file>` prints them by
frequency with a stub to paste in.

Bold, Italic, Underline, Superscript, Subscript and Format Painter were once
marked `text` there, because the font pack was the only way to draw anything and
it carries none of them — no bold, italic or paintbrush glyph among its 7242
codepoints, and adding one meant fontconvert plus a bundle reship. They are
ordinary LEXICON concepts now: the catalog has all six, so the constraint that
made them `text` is gone rather than worked around.
