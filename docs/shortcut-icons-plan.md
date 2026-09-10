# Generic shortcut + program icons — plan

A **fall-back** for apps with no hand-made overlay template. Where
`overlay-mapping.poly.yaml` already covers a key, nothing here applies; this
fills the long tail generically, by fetching icons on demand instead of
shipping them.

Two features, one mechanism:

* **Program icon** — the focused app's own mark, always on **ESC**.
* **Shortcut icons** — a per-key icon derived from the app's own shortcut
  labels, only where the template does not already draw something.

Status: **Phase 0 and Phase 1 are built, tested and pushed.** The keyboard draws
the focused app's mark on ESC, for an app with a template and for one without.
Phase 2 (shortcut icons on other keys) and Phase 3 (the curation file) are next.

⚠️ **Read A.3 before judging what Phase 1 delivers** — the catalog carries no
Microsoft Office, no Adobe and no VS Code, which this document previously got
wrong.

---

## Part A — settled design

### A.1 Program icon (ESC)

| property | value |
|---|---|
| source | [Simple Icons](https://simpleicons.org) **15.22.0, pinned** — CC0-1.0, single-path monochrome SVG, 24×24 box (⚠️ no Office/Adobe/VS Code — A.3) |
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

⚠️ **CORRECTED 2026-09-10 — the coverage claim here was WRONG, and the correction
is the most important fact in this document.** It read *"Simple Icons covers 41 of
42 probed apps, Office included"*. Checked against the CDN's own
`data/simple-icons.json`, by slug **and** by title, in both versions:

| probe | 15.22.0 | 16.30.0 |
|---|---|---|
| `microsoftexcel` / `microsoftoutlook` / `microsoftteams` | absent | absent |
| `adobephotoshop` / `illustrator` / `aftereffects` | absent | absent |
| `visualstudiocode` | absent | absent |
| `slack` | **present** | **absent** |
| `gimp` `inkscape` `kicad` `krita` `figma` `libreoffice` `obsstudio` `zoom` | present | present |

So the catalog carries **no Microsoft Office, no Adobe and no VS Code, in any
version** — the project's own trademark policy — and those are among the most
used apps here. Measured against this repo's shipped `overlay-mapping.poly.yaml`,
a normalised-name guess resolves **24 of 57** app names; the slug map lifts that,
and `winword` / `excel` / `powerpnt` / `outlook` / `teams` / `photoshop` /
`illustrator` / `afterfx` / `devenv` / `code` / `explorer` stay unreachable.

**The complement that closes it is the OS's OWN icon for the running process** —
the exe's resource icon on Windows, the `.desktop` + hicolor theme on Linux, the
bundle's `.icns` on macOS. Always exact, no catalog, no trademark question. It is
a per-platform lift and is **not** in this plan; the catalog is the cheap 60 %.

* ⚠️ **THE VERSION IS PINNED (15.22.0) and a newer pin is NOT a superset.** v16
  has 76 more entries and dropped Slack. `@latest` resolves to 15.22.0 today
  (`x-jsd-version`), so leaving it unpinned works right up until npm's `latest`
  tag moves, at which point every dropped mark vanishes with no error anywhere.
* ⚠️ **Wordmarks survive and matter** — KiCad and Zoom read *because* the panel
  is landscape. A square scheme would have discarded them.
* ⚠️ **The `simple-icons-font` webfont is not a shortcut.** A 1.4 MB TTF that
  would reuse the existing `ImageFont` path with no new dependency — but it is
  the same collection, so it has the same hole.
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

### Phase 0 — prerequisite (small) — ✅ DONE (`3401720`)

* `content_key` uses each converter's own filename (`zip(filenames, converters)`).
* The regression test drives two overlapping templates through the real send
  path and pins all three consequences (two slots, both filenames recorded, the
  mapping pointing at the later template's image). Confirmed to fail against the
  pre-fix loop.

### Phase 1 — program icon on ESC — ✅ DONE (`4e23c70`, `84e9223`)

**Deliverable met:** focus GIMP, ESC shows Wilber — for an app with a template
and for one without.

| shipped | what it is |
|---|---|
| `services/app_icons.py` + `res/app_icons.yaml` | slug resolution, fetch, cache, render (38 tests, 16/16 mutations caught) |
| `services/app_icon_fetcher.py` | the queue that keeps the fetch off the caller's thread (11 tests, 10/10) |
| `device/synthetic_overlay.py` | the duck-typed converter + the per-device `OverlayData` factory |
| `poly_kybd.send_overlays_mru(..., synthetic=)` | template-wins coverage rule (7 tests, 6/6) |
| `PolyCore` + `OverlayHandler.current_app` | the wiring, incl. the no-template case (10 tests, 8/8) |

Measured, not argued: ESC untouched on **12 of 12** marks (all 251 lit legend
pixels survive the courtyard clear), and end to end on the fake device
`org.gimp.GIMP` → `gimp` → 581 lit pixels → 8 HID reports → ESC mapped to the
slot filed under `@prog:gimp`.

Two rules turned out to be the whole contract, and both are pinned:

* a **real template wins** any key the synthetic source also offers, decided
  before the upload rather than by a later mapping write;
* the coverage key is **(modifier, keycode)**, not keycode — a template drawing
  ESC under Ctrl says nothing about bare ESC.

⚠️ **The pseudo-filename carries the slug because it is also the CACHE KEY.** A
fixed `@prog` would file the second app's mark under the first's key, hit the MRU
cache, skip the upload and draw GIMP's logo on an Inkscape window.

⚠️ **One bug came from running it, not reading it:** a slug is neither queued nor
cached while in flight, so the poll loop re-queued it every tick — two fetches
and two `on_ready`s, the second re-sending every overlay for nothing.

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
* ⚠️ The SAME file collects unmatched **app names** (E.3), so the slug map
  and the label hints grow from one curation pass, not two.
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

## Part E — decisions (settled)

### E.1 Default on, with a fetch setting — **settled**

Both features default **on**. The switch is over *retrieving* icons, not over
the feature:

* `shortcut_icon_auto_fetch` (default **True**) — may reach the network for an
  icon this install has not cached.
* Off ⇒ **cache-only**, never a request. Already-fetched apps keep working; a
  new app simply gets no icon.

That separation matters for anyone on a metered or air-gapped machine: turning
the switch off must not disable icons they already have.

### E.2 A log line on the miss path — **settled**

INFO, once per (app, reason), not per window switch:

```
No program icon for 'foo-editor' (no catalog match) — add a slug to app_icons.yaml
No program icon for 'gimp' (offline, not cached)
```

⚠️ Dedupe it. The window tick runs continuously, and an undeduped line would
fill the log with one entry per poll for any app that has no icon.

### E.3 Curate `app_icons.yaml` from the misses — **settled**

Start from automatic matching; write what fails into the same curation JSON the
shortcut labels use, and grow the YAML from that. Same loop as
`shortcut_hints.yaml`, same `--review` flow.

⚠️ **Auto-matching stays deliberately strict — no fuzzy fallback.** A wrong
logo is worse than none: showing Krita for KiCad is a bug the user cannot
explain, while a missing icon is self-evident and lands in the curation file.
(The shortcut lexicon needed a measured 0.85 fuzzy floor for the same reason;
here the answer is simpler because a slug is an exact identifier.)

### E.4 macOS — what the gap actually is

**The harvest needs a per-OS accessibility backend.** Three platforms, three
unrelated APIs:

| OS | API | status |
|---|---|---|
| Linux | AT-SPI2 over D-Bus, `org.a11y.atspi.Action.GetKeyBinding` | built, measured (26 shortcuts on a menubar app) |
| Windows | UI Automation, `AcceleratorKey` (30006) / `AccessKey` (30007) | built, measured (13 on Word's Home tab) |
| macOS | Accessibility API — `AXUIElement`, walking the menu bar for `AXMenuItemCmdChar` / `AXMenuItemCmdModifiers` / `AXMenuItemCmdVirtualKey` | **not built** |

So "two of three" means: on macOS **Phase 2 finds nothing and the fall-back
never fires** — E.2's log line says so, and nothing misbehaves.

Two things make this less bad than it sounds:

* ⚠️ **Phase 1 has no such gap.** The program icon needs only the app *name*,
  which the host already tracks on every platform for overlay matching. ESC
  works on macOS from day one.
* ⚠️ **macOS would likely have the BEST harvest of the three**, not the worst.
  Every Mac app has a real menu bar with real key equivalents, where GTK4 apps
  yield literally zero. It is the platform most worth doing eventually.

Cost when someone does it: `pyobjc` (`ApplicationServices`), and the user must
grant Accessibility permission in System Settings → Privacy & Security — a
consent prompt neither other platform needs.

⚠️ **I cannot test a macOS backend from this container at all**, so it is out of
scope here rather than merely deprioritised.

### E.5 Where the fetch runs — a core-owned thread

The constraint is two-sided and both sides are already documented:

* **Never the HID worker.** A 15 s HTTP timeout there stalls the reconnect probe
  (1 s) and the console read (250 ms).
* **Never the GUI main thread.** `wincompose_install.find_installer()` froze the
  tray ~10 s on an unreachable network by doing exactly this.

**`PolyCore` already owns Qt-free threads that do this kind of I/O**, so there is
a pattern to copy rather than a decision to invent:

| existing | does |
|---|---|
| `_wincompose_thread` | TASKLIST probes, 10 s → 60 s cadence, stop `Event` |
| `_tick_thread` | the headless window tick |
| telemetry reporter | HTTP POSTs, its own thread |

So: **one core-owned fetch thread**, a small queue of "resolve + fetch icon for
app X", stop `Event`, and the result handed back through the existing
`subscribe`/`emit` seam.

⚠️ **Copy the shutdown discipline too.** `_start_wincompose_settle` shares a lock
with `shutdown()` plus a one-way flag, because a reconnect landing concurrently
would otherwise clear the stop Event and start a fresh thread *after* shutdown,
holding the core and submitting to a stopped worker.

#### The sequencing wrinkle

`send_overlays_mru` needs every `OverlayData` **up front**, so on a cache miss
the icon cannot be in that switch's send. Two options:

* **(a)** the icon appears the *second* time you focus the app — simplest, and
  the cache makes it once per app ever;
* **(b)** re-send when the fetch lands, gated on the app still being focused.

**Recommend (b).** `coalesce_key="overlay"` already supersedes an in-flight
send, so the extra burst is cheap and a stale one cannot pile up. (a) is the
fallback if (b) turns out to fight the MRU batching.

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
