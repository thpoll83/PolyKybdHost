# The brand mark and the menu icons

Two icon sets and the traps in each: the generated PolyKybd mark (window, tray,
`.ico`/`.icns`, the size ladder) and the Material Symbols used on menu rows. Moved
out of `CLAUDE.md` on 2026-09-10: ~10 KB read when you regenerate or add an icon.

**The two rules worth knowing before you open the file**: the mark is GENERATED, so
edit `tools/gen_brand_icons.py` and never the PNGs; and a wrong icon NAME fails
silently, because `QIcon()` on a nonexistent path returns an empty icon that
nothing raises about — `tests/gui/icon_assets_test.py` is the only thing standing
between a typo and a menu row with no picture.

Almost every decision here was settled by RASTERISING and measuring, not by reading
the SVG — ink coverage, glyph height, contrast against both theme grounds, ICONDIR
entry counts. A rule separated from those numbers cannot be re-derived.

---

## The brand mark

- **The brand mark (`p{color,gray,think,warn}.*`) is GENERATED — edit
  `tools/gen_brand_icons.py`, never the PNGs.** It draws a 6x6 keycap grid whose
  UNLIT keys spell a "P" in negative space, on a 1024-unit viewBox (the 64px
  original's proportions scaled up), and writes the whole set per variant: an SVG
  master, `p<v>.png` (256, the canonical file `add_to_startup` and the About dialog
  use), `p<v>@1024.png` for docs/store, the `p<v>_<n>.png` size ladder, `.ico` and
  `.icns`. Redesigned 2026-09-05 from a six-hue rainbow to one blue -> cyan sweep,
  with "HOST" stamped out of the bottom row's four rightmost keys.
  - **`get_icon()` feeds QIcon the LADDER, not the 256 master.** The mark is hard-
    edged squares, so Qt smoothly downscaling 256 -> 16 for a tray blurs exactly the
    thing that carries the shape. `BrandMarkTest` (tests/gui/icon_assets_test.py)
    asserts the set is complete AND that each ladder PNG's pixels match its name —
    a ladder built by copying one file is as blurry as no ladder, and looks fine
    until it is on somebody else's taskbar.
  - ⚠️ **cairosvg does NOT honour `<mask>`** — the stamp is punched by redrawing the
    body fill over the key instead, which is why the body gradient is
    `gradientUnits="userSpaceOnUse"`: the punched pixels then match the body around
    them exactly. A mask renders as a silent no-op (the key just draws whole), so
    check the render, not the SVG source.
  - **The busy and warning states draw the RING ONLY** (`RING`, and the engraved
    ghosts are skipped there too), so the hourglass / warning triangle sits in
    cleared space instead of over a dimmed grid — which is also why neither
    carries a dimming overlay any more. The P goes with the inner keys; a
    transient state reads by its glyph, and the ring plus the HOST stamp still
    names the app. ⚠️ The triangle is STROKED, so its nominal width understates
    it by half the stroke on each side — an unshrunk one overlaps the ring keys.
  - ⚠️ **Whether the inner keys are cleared is counted in the SVG master, not in
    pixels** — the engraved ghosts are white at 5% opacity over the body, a
    couple of levels of difference, so a pixel threshold for them would be
    fragile in exactly the direction that matters.
    `test_the_state_variants_draw_the_RING_ONLY` counts `url(#keys)` and the
    ghost rects instead (25/11 for the full mark, 20/0 for the ring). The pixel
    test beside it answers a DIFFERENT question — that the glyph stays inside
    the cleared middle — and does NOT catch a variant that kept its inner keys;
    that gap was found by mutation-testing, not by reading the tests.
  - **The hourglass is a plain silhouette: two caps and ONE body path**, with a
    straight-sided `base` run (0.36 of the bulb height) under each cap before
    the taper starts — without it the shape reads as a bare bowtie. `wall`
    places the taper's control point between the axis and the bulb edge: ~0.53
    is a straight wall, below it bows inward (concave) and above it outward
    (convex); 0.32 ships. Drawing the bulbs as separate shapes leaves a gap at
    the neck that reads as broken glass, and it is filled shapes throughout,
    never strokes, because an outline fills in at 16 px and becomes a blob.
  - **The stamp is rendered only at 128 px and up** (`STAMP_MIN_SIZE`); the smaller
    renders come from an unstamped master, so a tray icon stays a clean grid instead
    of carrying four keys of mush. Measured: clean at 128+, legible at 96,
    unreadable at 64.
  - ⚠️ **Pillow's ICO writer SKIPS every requested size LARGER than the base image,
    silently.** Handing it the 16 px render first (natural, when the entries are
    rendered per size and iterated small-to-large) writes a **single-entry 16x16
    `.ico`** that Windows then upscales into a blur — no error, no warning, and the
    file opens fine. The base must be the LARGEST; the rest go in `append_images`.
    `test_every_ico_carries_the_whole_size_set` reads the ICONDIR count with
    `struct` so it needs no image library.
  - ⚠️ **Abutting rects leave a hairline seam once antialiased.** The stamp's pixel
    cells are inflated 6% so neighbours overlap; without it every letter shows faint
    grid lines through it at 1024.
  - The brand `.svg` files are excluded from the Material-Symbols format tests
    (`BRAND_SVG`): they are multi-layer generated artwork with many fills, not
    single-fill menu glyphs, and no `get_icon()` call names them.
  - **Downstream generators re-run from `pgray.png`** — `browser-extension/generate_icons.py`
    and `browser-extension/store/make_promo.py`. Run both after regenerating.

---

## Menu and tray icons

- **Tray/menu icons (`polyhost/res/icons/`) are Material Symbols at optical size
  48 — fetch the `_48px` cut, never `_24px`.** The optical-size axis changes the
  **geometry**, not just the header: the same symbol at opsz24 is drawn with
  heavier strokes for a smaller render target. Measured on a 48px canvas, an
  opsz24 file carries **~25% more ink on average (max +43%)** than its opsz48
  twin, so a mixed-opsz set renders visibly uneven — the new icons look bolder
  than the untouched ones sitting next to them in the same menu. This cost a
  full re-fetch of 28 files (2026-07).
  - Source: `https://raw.githubusercontent.com/google/material-design-icons/master/symbols/web/<name>/materialsymbolsoutlined/<name>_48px.svg`
    (filled variant: `<name>_fill1_48px.svg` — that's how brightness 100% differs
    from 50%). Emit as a single `<path>` under
    `<svg height="48px" viewBox="0 -960 960 960" width="48px" fill="#RRGGBB">`,
    one fill on the `<svg>` element, tinted from the palette documented in
    `gui/get_icon.py`.
  - ⚠️ **A wrong/missing filename fails SILENTLY**: `QIcon()` on a nonexistent
    path returns an **empty** icon — nothing raises at import or at runtime, the
    menu entry just renders without one. Icon names are plain string literals at
    ~50 `get_icon()` call sites, so **`tests/gui/icon_assets_test.py`** asserts
    every name resolves, that no shipped `.svg` is unreferenced (11 orphans had
    accumulated), and that the opsz48/single-fill format holds. It is Qt-free, so
    it runs in the normal suite rather than only under xvfb.
  - ⚠️ **A tint is drawn on BOTH theme grounds now, so a colour picked against
    one can vanish against the other — measured, the brightness family did.**
    The apps follow the OS light/dark setting (see the theme note below), and
    `#FFFF55` is 7.6:1 on the dark chrome (#505050) and **1.07:1 on the light
    one** (#F0F0F0): yellow on white, reported from the field 2026-09-07. It is
    `#B59D24` gold now (3.00 / 2.36), and the three other off-palette one-offs
    went with it — `sync_problem` was `#A96424`, 1.74:1 on DARK (the same fault
    the other way), and `delete` `#F19E39`; both adopted the palette colour
    their meaning already had. Every colour in the set now sits between 2.20:1
    and 3.22:1 on both grounds, and `IconContrastTest` holds a 2.0 floor.
    - ⚠️ **A ramp cannot be expressed in LIGHTNESS — that is what made the old
      one unfixable rather than merely wrong.** The four brightness entries were
      shades of one yellow (a paler `#F9DB78` for 1%), and a pale tint is the
      worst case of all on a light ground. The ramp is across the palette now:
      grey off, **amber** at 1%, gold at 50/100% (the Material glyphs carry the
      rest — fewer rays, outline vs filled), and **green** for "back to
      automatic", which is the palette's enabled/ok rather than a brightness
      level. So amber means caution *and* the dim end, and green means ok *and*
      automatic; the alternative was two more one-off colours, and the set only
      just stopped having those.
  - **Judge a candidate glyph by rendering and measuring it, not by its name.**
    Rasterise to a fixed canvas (`cairosvg` + PIL) and compare **ink coverage**
    and **glyph bounding height** against the set (baseline ≈19% ink, ≈34px tall
    on 48px). That is what caught both the opsz mismatch above and `abc` being
    only 12px tall — half the next smallest icon — which eyeballing the render
    had missed. The measurement also overruled three name-based picks: the
    `brightness_*` family is not a coherent ramp (the `backlight_*` family is),
    and `bedtime`/`bedtime_off` beat a sun for idle start/stop.

---

## The window icon vs the taskbar button

- ⚠️ **The WINDOW icon and the TASKBAR BUTTON icon are answered by different
  questions, and `setWindowIcon()` only answers the first.** Windows groups
  taskbar buttons by **AppUserModelID**, and a process that never sets one is
  identified by its host executable — `pythonw.exe` — so the button showed the
  **Python** icon while every title bar was correct (field, 2026-09-04: *"for
  all these dialogs the program icon is not shown in the task bar"*).
  - **It was never a missing icon**, which is why chasing `setWindowIcon` call
    sites finds nothing: `IconStateManager.__init__` runs `update()` with
    `dirty_flag` already set, so `QApplication.setWindowIcon` is called at
    startup and every dialog inherits a real `p*.png`. Four dialogs additionally
    override it with `pcolor.png`; that is cosmetic, not the fix.
  - **The Linux half had been solved all along, three lines away** —
    `QApplication.setDesktopFileName('PolyHost')` in `main_app.py`, commented
    *"important for XWayland icon matching"*, i.e. the same question with the
    same failure mode. `set_windows_app_id()` is its counterpart and sits in the
    same `if/elif`, so the two are read together.
  - ⚠️ **It must run BEFORE the first window exists** — a window keeps the
    identity it was born with — and it must never raise: this is cosmetic, and an
    exception there kills the tray before it appears. One call in `main_app`
    covers the **forwarder** too, which is the second tray app that otherwise
    gets forgotten.
  - ⚠️ **`WINDOWS_APP_ID` is STABLE, not a name to tidy.** Windows keys pinned
    buttons and jump lists off that string, so renaming it orphans a user's
    pinned icon. A test pins the literal for that reason.
  - **Not verifiable from this container** — the code path is `win32`-only, so
    the tests cover the wiring (asked for on Windows, nowhere else, a failure
    swallowed and logged) and hardware confirms the icon.
