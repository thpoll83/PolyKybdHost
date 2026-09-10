# Generic shortcut + program icons — plan

A **fall-back** for apps that have no hand-made overlay template. Where
`overlay-mapping.poly.yaml` already covers a key, nothing here applies; this
fills the gap for the long tail, generically, by fetching icons on demand
instead of shipping them.

Two independent halves. The program icon is much simpler and can ship first.

---

## 1. Program icon — the ESC key

The focused application's own mark, always on ESC.

| property | value |
|---|---|
| source | [Simple Icons](https://simpleicons.org) — CC0-1.0, single-path monochrome SVG on a 24×24 box |
| placement | **right-aligned**, vertically centred |
| size | fitted to a **40×40** box, aspect preserved |
| rasteriser | `cairosvg` (today a `tools/` dependency — this makes it a runtime one) |

### Why 40 and not 48

The cap is arithmetic, not taste. Measured through the shipped renderer, the
ESC glyph (U+238B) inks **x 2..27**; the firmware clears a Chebyshev-3
courtyard around the overlay, so the icon's ink must start at x ≥ 31:

```
72 - 31 = 41   ->   max width 41, i.e. 40
```

Everything wider keeps eating the glyph's right edge, measured over 36 marks:

| cap | icon left edge | courtyard clears from | ESC worst | ESC untouched |
|---|---|---|---|---|
| 48 | 24 | 21 | 71 % | 20/36 |
| 44 | 28 | 25 | 86 % | 20/36 |
| 42 | 30 | 27 | 97 % | 21/36 |
| **40** | **32** | **29** | **100 %** | **36/36** |

⚠️ **44 looks like a safe compromise and is not** — it still clears from x=25
against ink reaching 27. Only 41 or less clears.

The cost is small and confined: **19 of 36 icons do not change at all** (they
are 40 tall and already ≤ 40 wide). Of the 17 that do, the Office set goes
44×38 → 40×35, GIMP 44×38 → 40×34, KiCad 44×18 → 40×16. None reads worse.

At 40 the rule collapses to something easy to hold: **the right-hand 40×40
square belongs to the icon, the left 32 px to the legend.**

### Measured, for whoever revisits this

* Coverage: **41 of 42** probed apps present (only TeXstudio missing), Office
  included. At full height essentially all of them read; the two duds are
  Autodesk (a generic slab) and Obsidian (a blob at 1-bit).
* Lit area: median 853 px of the panel's 2880 (30 %), from OBS Studio at 322
  to Discord at 1400.
* ⚠️ **Wordmarks survive and are worth keeping** — KiCad and Zoom are text
  logos and read well *because* the panel is landscape. A square icon scheme
  would have thrown them away.
* ⚠️ **The `simple-icons-font` webfont is NOT a shortcut.** It ships a 1.4 MB
  TTF that would reuse the existing `ImageFont` path with no new dependency —
  but at the same version (16.30.0) it carries **no `microsoft*` slugs at
  all**, plus no VS Code or Slack. Verified, not assumed.
* Trademark: the SVG collection is CC0, the marks are their owners'. Using
  them to identify the focused app is ordinary identification; worth a line in
  the user-facing docs, and a reason not to advertise a bundled logo cache.

### The alternative not taken (yet)

The OS already has the real icon — exe resources on Windows, `.desktop` + icon
theme on Linux, `.icns` on macOS. No licensing question, and it covers in-house
apps no catalog will ever have. It costs platform-specific code, and `PolyCore`
is Qt-free so it cannot lean on `QFileIconProvider`. Worth doing as the primary
with Simple Icons as the fallback, once the simple path is proven.

---

## 2. Shortcut icons — the other keys

For a key the app's overlay template does **not** already cover:

1. read the OS (`OverlayHandler._active_os()`, already there);
2. harvest the app's shortcut labels (`tools/shortcut_probe.py` backends);
3. `label -> concept -> icon` via `polyhost/services/shortcut_icons.py`;
4. fetch/cache/render via `polyhost/services/icon_catalog.py` (shipped);
5. anything unmatched goes to a JSON for later curation, which feeds
   `polyhost/res/shortcut_hints.yaml`.

Geometry is settled and shipped: lower-left, 32 px, five placements, the
courtyard trade documented in `icon_catalog.py`.

### ⚠️ The structural snag to settle first

The existing overlay path is **whole-keyboard template PNGs**, channel-packed
per modifier: `send_overlay_data()` takes filenames, `ImageConverter.open()`
decodes one template covering many keys, `send_overlays_mru()` ships the lot.

There is no "send one key" entry point, and **nothing can answer "does the
current template already cover this key?"** — which is exactly the condition
this fall-back turns on. So it needs one of:

* compose a synthetic template in memory and feed the existing path (an array
  entry point beside `ImageConverter.open(filename)`), or
* a per-key send path alongside the MRU template path.

Neither is large. It is invisible from the design as stated, which is why it is
written down here.

### Other gaps

* **macOS has no probe backend.** Linux (AT-SPI) and Windows (UIA) exist;
  "win/linux/mac" is two of three today.
* **The harvest is only as good as the app.** Measured: a classic menubar app
  yields ~26 shortcuts, GTK4 apps yield zero. This helps where it helps.

---

## Later: compare and replace

The repo already ships 84 hand-made overlay PNGs in `polyhost/res/overlays/`
with their generators in `polyhost/res/overlay_sources/`. Several of the
catalog marks look better than the current equivalents, so a side-by-side is
worth rendering — per app, not wholesale.
