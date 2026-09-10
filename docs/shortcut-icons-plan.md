# Generic shortcut + program icons — plan

A **fall-back** for apps with no hand-made overlay template. Where
`overlay-mapping.poly.yaml` already covers a key, nothing here applies; this
fills the long tail generically, by fetching icons on demand instead of
shipping them.

Two features, one mechanism:

* **Program icon** — the focused app's own mark, always on **ESC**.
* **Shortcut icons** — a per-key icon derived from the app's own shortcut
  labels, only where the template does not already draw something.

Status: geometry settled and measured (below). `icon_catalog.py` and
`shortcut_icons.py` are shipped and tested. Nothing else is built yet.

---

## Part A — settled design

### A.1 Program icon (ESC)

| property | value |
|---|---|
| source | [Simple Icons](https://simpleicons.org) — CC0-1.0, single-path monochrome SVG, 24×24 box |
| placement | **right-aligned**, vertically centred → the right-hand **40×40** square |
| size | fitted to 40×40, aspect preserved |
| rasteriser | `cairosvg` (today a `tools/` dep — this makes it a runtime one) |

**Why 40 is arithmetic, not taste.** The ESC glyph (U+238B) inks **x 2..27**;
the firmware clears a Chebyshev-3 courtyard around an overlay, so the icon's
ink must start at x ≥ 31 → `72 − 31 = 41`, i.e. **40**.

| cap | icon left edge | clears from | ESC worst | ESC untouched |
|---|---|---|---|---|
| 48 | 24 | 21 | 71 % | 20/36 |
| 44 | 28 | 25 | 86 % | 20/36 |
| 42 | 30 | 27 | 97 % | 21/36 |
| **40** | **32** | **29** | **100 %** | **36/36** |

⚠️ **44 looks like a safe compromise and is not** — it still clears from x=25
against ink reaching 27. Only ≤41 clears.

Cost of 40 over 44 is confined: **19 of 36 icons do not change at all** (already
≤40 wide at 40 tall). Of the 17 that do, Office goes 44×38 → 40×35, GIMP → 40×34,
KiCad → 40×16. Rendered side by side, none reads worse.

At 40 the rule collapses to: **right 40×40 is the icon, left 32 px is the
legend.**

### A.2 Shortcut icons (other keys)

Shipped in `icon_catalog.py`: Material Symbols, subsetted server-side
(4.8 KB for 12 names vs a 10.6 MB variable font), lower-left, 32 px default,
five placements, clamped to the panel.

⚠️ **An overlap is not a collision** — the courtyard means the icon always lands
on cleared black. The cost of size is legend pixels eaten, not muddle: at 32 px
about 42 % of the legend survives. Full table in `icon_catalog.py`.

### A.3 Measured facts worth not re-deriving

* Simple Icons covers **41 of 42** probed apps (only TeXstudio missing), Office
  included. At full height essentially all read; duds are Autodesk (generic
  slab) and Obsidian (blob at 1-bit).
* Lit area: median 853 px of 2880 (30 %), OBS 322 → Discord 1400.
* ⚠️ **Wordmarks survive and matter** — KiCad and Zoom read *because* the panel
  is landscape. A square scheme would have discarded them.
* ⚠️ **The `simple-icons-font` webfont is not a shortcut.** A 1.4 MB TTF that
  would reuse the existing `ImageFont` path with no new dependency — but at the
  same version (16.30.0) it has **no `microsoft*` slugs**, no VS Code, no Slack.
* Trademark: the collection is CC0, the marks are their owners'. Identifying the
  focused app is ordinary use; worth a line in the user docs, and a reason not
  to advertise a bundled logo cache.

---

## Part B — how it integrates (verified against the code)

**The integration is smaller than it first looked. No new send path is needed.**

`PolyKybd.send_overlays_mru(filenames, cache, cancel)` already does everything:

```
for filename in filenames:            # 1. decode every template up front
    converter.open(filename)
prepare_for_mru_send()                # 2. reset firmware mapping + usage
for converter in converters:
    for modifier in Modifier:
        overlay_map = converter.extract_overlays(modifier)   # {keycode: OverlayData}
        for keycode, overlay_data in overlay_map.items():
            content_key = (basename(filename), modifier.value, keycode)
            pool_slot, hit = cache.get_or_allocate(content_key, filename, bytes)
            if not hit: send_smallest_overlay(...)
            display_to_pool[display_flat_idx(keycode, modifier)] = pool_slot
send_overlay_mapping(display_to_pool)
```

Two consequences that shape the whole plan:

1. **A converter is duck-typed.** Anything exposing
   `extract_overlays(modifier) -> {keycode: OverlayData}` plugs in. So a
   *synthetic* converter — built from fetched icons rather than a PNG — needs no
   changes to the device layer at all.
2. **"Does the template already cover this key?" is answerable locally.** It is
   just the union of the templates' own `extract_overlays()` results, computed
   before any device I/O. No new firmware query, no guessing.

### ⚠️ B.1 A latent bug that goes live the moment we add a converter

`content_key` uses `filename` — the **leftover loop variable from the decode
loop above**, so it holds the *last* filename for every converter.

Today this is harmless: measured, the shipped multi-template apps (chrome,
googledocs, excel, github) are **disjoint in (modifier, keycode)**, so no two
converters ever key the same tuple.

It stops being harmless here. Once a synthetic converter is appended, every
template's images get filed under the *synthetic* name. If that name is
app-specific — which it must be — then `chrome_template.*`, shared today by
chrome/edge/brave/vivaldi, would key differently per browser: **cache misses and
a full template re-upload on every browser switch.**

**Fix first, separately:** `for filename, converter in zip(filenames, converters)`.
The lists are always parallel (a failed `open()` returns early). One line, plus a
regression test with two overlapping templates.

---

## Part C — work breakdown

### Phase 0 — prerequisite (small)

* Fix `content_key` to use each converter's own filename.
* Test: two synthetic templates that DO overlap on (modifier, keycode) get
  distinct pool slots. Fails against today's code.

### Phase 1 — program icon on ESC (self-contained, ships alone)

* `polyhost/services/app_icons.py` — slug resolution + fetch + cache, mirroring
  `icon_catalog.py`'s shape (`fetch`, cache dir, `_is_svg` validation).
  * app name → Simple Icons slug. Start with an explicit map in
    `polyhost/res/app_icons.yaml` (`gimp-2.0` → `gimp`), falling back to a
    normalised-name guess. **Not** fuzzy matching — a wrong logo is worse than
    none.
  * render: rasterise at the size whose *ink* fits 40×40, aspect preserved,
    right-aligned, vertically centred → boolean mask → `OverlayData`.
* `SyntheticConverter` — duck-typed `extract_overlays(modifier)`, returning
  `{KC_ESCAPE: OverlayData}` for `Modifier.NO_MOD`.
* Hook: where the app is resolved (`OverlayHandler` → `PolyCore.send_overlay_data`),
  append the synthetic converter and a pseudo-filename (`@prog:<slug>`).
* Setting: `program_icon_enabled` (default?) — see open decisions.

**Deliverable:** focus GIMP, ESC shows Wilber. Works for an app with a template
and for one without.

### Phase 2 — shortcut fallback

* Move the probe backends out of `tools/shortcut_probe.py` into
  `polyhost/services/shortcut_source/` (`atspi.py`, `uia.py`, `__init__.py`
  picking by platform). Keep the probe as a CLI over the same code.
* Coverage: union of the templates' `extract_overlays()` per modifier.
* For each harvested shortcut whose (keycode, modifier) is uncovered:
  `label → concept → icon → OverlayData`, into the same synthetic converter.
* ⚠️ Ordering: synthesise only for uncovered keys, so template-wins needs no
  precedence rule and no wasted upload.

### Phase 3 — unmatched → curation

* `polyhost/services/shortcut_unmatched.py`: append `{app, os, label, accel,
  count, first_seen, last_seen}` to a JSON under the user config dir.
* `polyctl shortcuts unmatched [--review]` — the probe's `--review` flow,
  emitting `shortcut_hints.yaml` stanzas.
* ⚠️ Bounded: cap entries, dedupe by (app, label). This file grows unattended.

---

## Part D — testing

Offline, no network, no device — matching `icon_catalog_test.py`:

* **Geometry**: right-aligned 40×40; ESC glyph untouched for a fixture icon
  (the arithmetic in A.1 is the contract, and a regression would be silent).
* **Slug resolution**: known app → slug; unknown app → `None`, never a guess
  that could yield the wrong logo.
* **Synthetic converter**: `extract_overlays` returns the right keycode/modifier;
  the result is a real `OverlayData` (so the ROI/RLE paths accept it).
* **Coverage**: a key the template covers is not synthesised; an uncovered one is.
* **Cache**: distinct apps get distinct content keys (the Phase-0 bug, inverted).
* Mutation-check each suite, as the last three commits did.

⚠️ The device path itself stays untested offline — `send_overlays_mru` needs
hardware. The HIL rig is where a real send is proven; consider a rig test that
sends one synthetic overlay and reads back the mapping.

---

## Part E — open decisions (need your call)

1. **Default on or off?** Program icon and shortcut fallback separately. Both
   reach the network on first use for a new app.
2. **Offline behaviour.** No network / unknown app → ESC keeps its normal
   legend, silently? Or a log line?
3. **Slug map curation.** Ship `app_icons.yaml` with the ~40 apps measured, or
   start empty and grow it from the unmatched JSON like the shortcut hints?
4. **macOS.** No probe backend exists (Linux AT-SPI + Windows UIA do). Phase 2
   is two-of-three platforms unless someone writes it. The ESC program icon has
   no such gap — it only needs the app name, which the host already has.
5. **Where the fetch runs.** `PolyCore` is Qt-free and the worker thread must not
   block on HTTP. The wincompose installer's pattern (own thread, result through
   the callback) is the precedent.

---

## Part F — risks

* **`cairosvg` becomes a runtime dependency** (native cairo). The only way to
  avoid it is the webfont, which lacks the Microsoft marks (A.3).
* **Cache growth** — one SVG per app is ~1 KB, but unbounded over years. Needs a
  cap or an age-out, like the crash log's trim.
* **The harvest is only as good as the app.** Measured: a classic menubar app
  yields ~26 shortcuts, GTK4 apps yield zero. Phase 2 helps where it helps; that
  is worth saying in the docs so it does not read as broken.
* **Trademark presentation** — see A.3.

---

## Later: compare and replace

84 hand-made overlay PNGs live in `polyhost/res/overlays/` with generators in
`polyhost/res/overlay_sources/`. Several catalog marks look better than the
current equivalents, so a side-by-side is worth rendering — per app, not
wholesale.
