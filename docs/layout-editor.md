# The layout editor (`polyhost/gui/layout_dialog/`)

How the keymap editor draws a PolyKybd — the key geometry, the case plate under it,
the three ways a key can be pictured, and where the picture DATA comes from. Moved
out of `CLAUDE.md` on 2026-09-10: it is ~52 KB that matters when you touch the
editor and never otherwise.

Notes are kept WHOLE with their measurements attached. Almost everything here was
settled by RENDERING and counting pixels rather than by reading the code, so a rule
separated from its numbers is a rule nobody can re-derive — the bezel is 0.33U
because 149 outline points measured 1.65 mm outside `Edge.Cuts`, and REAL is drawn
at 3x because at 1x there is literally nothing to see.

**Start here when a preview looks wrong**: `python tools/preview_doctor.py` prints
the host and firmware commits, the layer-enum diff, every layer key's resolved token
and the brightness legend expressions. Three separate field reports — a blank L5,
missing emoji/Intl keys, and old brightness icons — were ONE stale firmware clone,
and two rounds were spent inferring that from the symptoms instead of asking.

---

## What the editor is

- **Layout dialog** (`polyhost/gui/layout_dialog/`): fully implemented — layer switching re-renders all key labels from the cached buffer; clicking a key then selecting from the browser writes immediately to the device via `set_dynamic_keycode()` and keeps the local buffer in sync. `RenderableKey` carries `matrix_index` for row/col derivation.

---

## Where the key GEOMETRY comes from

- ⚠️ **The editor's key GEOMETRY comes from `polyhost/res/polykybd-split72.json`
  (KLE), and the firmware's `keyboard.json` is NOT a second opinion on it.** When
  the board looks misaligned, that is the first thing to get straight, because the
  obvious cross-check is worthless: QMK's `layouts.*.layout` is a **coarse grid**
  used for `qmk info -l` ASCII art — it carries no column stagger and no thumb
  rotation at all. Compared key for key (2026-08-29), **64 of the 74** disagree
  with the KLE: every non-thumb key by 0.125–0.25 in `y` (the stagger the KLE
  expresses with fractional `y` offsets), and all ten thumbs by position *and* by
  the whole `r`/`rx`/`ry` rotation the grid simply does not have. The x values do
  agree, which is exactly what makes it feel authoritative when it is not.
  - **The authority is the PCB** (`PolyKybd/poly_kybd/poly_kybd_split72_*.kicad_pcb`),
    read via the `investigate-kicad-pcb` skill: switch footprints are `SW_K_<n>`,
    and a row of them at one `y` gives the real pitch. Worked example — the
    "bottom row looks inset" question: `SW_K_30` sits at x=53.25 against the
    column above at x=48.49, i.e. **inset 0.25U (4.76 mm)**. So the inset is
    real; flushing that key to `x: 0` in the KLE would have made the editor
    disagree with the hardware.
  - ⚠️ **The KLE's outer column is a STYLISATION, and it is what makes the two
    numbers differ.** The PCB has 1U switches on a 1.25U pitch (48.49 → 72.30 is
    23.81 mm = 1.25U, while every other gap is 19.05 mm = 1U); the KLE draws them
    as 1.25U-wide keys with a 0.25U gap. That is why the bottom row reads as a
    0.5U inset there and 0.25U on the board. It applies to all five rows, so
    "fixing" it is a redraw of the whole column, not a bottom-row tweak — don't
    take it for a bottom-row bug.
  - `parse_kle` (`polyhost/kle/kle_praser.py`) is the decoder to reason through;
    note `row_defaults.clear()` after each key (so `w` does not persist) and that
    `y_cursor` only advances at end-of-row when `current_rotation == 0`, which is
    what lets the rotated thumb clusters sit outside the row flow.

---

## The board plate under the keys

- **The board the keys sit on is GENERATED from the KiCad boards —
  `polyhost/res/board_outline.json`, written by `scripts/export_board_outline.py`,
  drawn by `gui/layout_dialog/board_plate.py`.** It carries each half's
  case contour and the two optional 0.96" status panels, in the same key
  units as the KLE, so the editor shows which half a key is on and where the
  screens are instead of 74 tiles floating in space. It is decoration and fails
  soft: no file, no picture, unchanged editor.
  - ⚠️ **The outline is the CASE, not the board — `parts/case/outline_polykybd_split72_*.svg`,
    which is `Edge.Cuts` grown by `case_wall_thickness + pcb_clearance` = 1.65 mm.**
    Drawing `Edge.Cuts` itself makes the plate 1.65 mm too small on every side, and
    the visible symptom is at the thumbs: keycaps overhang the plate there (worst
    0.10U = 1.9 mm) where on the real keyboard they do not. The shipped SVG is used
    verbatim rather than re-deriving the offset — it IS the extruded contour, rounded
    corners and all — placed by a translation fitted to the board's bounding box and
    then CHECKED, by requiring every one of its 149 points to sit 1.65 mm outside
    `Edge.Cuts` (measured 1.647–1.654, the spread being the polygon approximation of
    the corners). That check is what proves the SVG belongs to this board; a swapped
    left/right pair misses by 18 mm, the spacer outline by 3.8 mm. ⚠️ **1.65 is the
    split72 left+right case specifically** — `case_polysplit72_right2` and
    `right_side` use a 0.25 clearance, i.e. 1.75.
  - ⚠️ **The outline is then FITTED to one even bezel on all four sides
    (`BEZEL_U`, 0.33U / 6.3 mm) — the real case is NOT even, and that is deliberate.**
    Measured on the left half the true margins are W 6.4 / E 3.6 / N 8.8 / S 6.2 mm,
    which reads as a crooked plate rather than as accuracy — because the KEYS are
    stylised too: the KLE draws the outer column 1.25U wide over a 1.25U pitch where
    the board has 1U switches, and it approximates the thumb clusters. So a
    photographically exact case around approximated keys is the worst of both.
    `normalise_bezel` is an axis-aligned scale + translate, so the silhouette and the
    rounded corners survive and only the margins move; measured stretch is 1.3% in x
    and 1.9% in y, and past `MAX_BEZEL_STRETCH` (15%) it refuses rather than reshapes.
    Evening it also lifted the last two overhanging thumb corners inside, so the
    overhang bound is now zero rather than a tolerance.
    - ⚠️ **This BLINDS the even-bezel test to a revert to the bare PCB edge** — that
      would be evened out too and measure the same. The case-vs-board pin therefore
      reads `fit.case_mm` (185.30 x 132.30, recorded BEFORE the fit) and not the drawn
      outline. A test that measures a fitted number cannot also police its input.
  - **The mm → key-unit transform is a pure translation at 19.05 mm/U** — the
    boards carry no rotation, so scale is the pitch and the only unknown is the
    origin. The exporter fits it by trying every (switch, key) pairing and keeping
    the one that explains all 37 switches, then refuses to write unless the fit is
    a **bijection** within bounds. Measured: 31 of 37 land exactly, the outer column
    is out by 0.125U and the outer thumbs by up to 0.24U — the KLE's stylisation
    (see the outer-column note above), not drift.
  - ⚠️ **A containment test cannot catch a wrong offset, and that is not obvious.**
    "Every key is inside the outline" passes with the whole board shifted **0.25U**
    (4.8 mm) inward, because the inner edge has that much slack — measured, after
    writing exactly that test and watching the mutation escape. What catches it is
    the opposite property: the margin at each edge is PINNED, so
    `test_the_bezel_is_the_SAME_on_all_four_sides` fails on the first edge a
    translation moves. Ten mutations are caught — translate, scale, mirror, an
    uneven bezel, a revert to the bare PCB edge, and each of the three ways the
    status panel can be misplaced (centred in its corner, left at its real width,
    pulled off the case).
  - ⚠️ **Restore the baseline before EACH mutation in a sweep, or a `+x`/`-x` pair
    CANCELS and reads as ESCAPED.** The first harness here re-read the file it had
    just mutated, so mutation 2 landed on top of mutation 1 and reported the tests
    as worthless when they were fine. Same family as the ANSI-escape and
    never-applied traps in `qmk_firmware/CLAUDE.md`: every one of them fails toward
    "your tests caught nothing", which is the reading that makes you stop trusting a
    suite that works.
  - **The status panels are ANCHORED on `J39`** — the 30-pin FPC each half carries
    for the display (the schematic's *"Optional OLED Status Display"*) — but they are
    not DRAWN at it. The connector says which corner; `free_rect_at` then measures the
    largest free rectangle containing it (case polygon minus keycaps plus a 0.06U
    clearance, on a 0.05U grid) and the panel is grown to span that corner's full
    width and hung one bezel under the case's top edge. Drawn at the connector it is
    both too small and too low: the FPC sits at the BOARD's height near the bottom of
    the corner, so the panel reads as having slipped, and at its real 26.7 mm it
    leaves a gap on both sides. ⚠️ The display hangs off a ~40 mm cable, so where it
    ends up in the CASE is in no repo file — this is a layout rule, not a measurement.
    - ⚠️ **The side bezel is simply NOT DRAWN — which changes the GLASS and nothing
      else. The screen keeps the size AND the position the uniform fit gave it, so
      the panel now stops one module bezel (3.5 mm) short of the housing rather than
      meeting it.** The MODULE is scaled to span the corner, that fit sets the
      screen's size (30.6 x 15.3 mm on the left half), and the module's side bezel is
      symmetric — so not drawing it leaves exactly half a bezel of air at each end of
      the span. Glass survives above and below in the module's own proportion, so the
      screen's 2:1 aspect is deliberately gone. There is no caption on it — a lit
      rectangle in a dark frame is already a screen.
      - ⚠️ **FOUR readings of "remove the bezel" were built and three are wrong; the
        picture cannot tell them apart and `w == aw` is true of all four.** They are
        (1) grow the whole MODULE until the bezel closes — that enlarges the bezel
        along with everything else; (2) widen the SCREEN to fill the glass — same
        envelope, 23% more lit area, i.e. it adds the bezel to the display rather
        than deleting it; (3) narrow the glass and slide it FLUSH — correct size,
        but it moves a screen that was already placed; (4) narrow the glass and
        leave it where it is, which is the one that ships.
      - **Two tests separate the four, and they pin different things.**
        `test_dropping_the_side_bezel_did_NOT_enlarge_the_screen` pins the panel's
        ASPECT — 21.74/19.26 = 1.129 narrowed against 26.70/19.26 = 1.386 filled —
        which catches (1) and (2).
        `test_a_panel_STOPS_ONE_MODULE_BEZEL_SHORT_of_the_case` pins the gap to the
        housing, which catches (3): a flush panel measures 0. Neither is redundant
        and neither alone is enough.
      - **The gap is derived, not hardcoded**: half a module bezel times the scale
        the panel itself reports (`d.h / panel_h`), because a literal would pin
        today's corner width rather than the intent.
    - **The vertical glass is therefore pinned as a RATIO, not in mm** (8.4 of the
      module's 19.26, whatever the scale). A test in millimetres would encode the
      corner's width, which is geometry rather than intent.
    - **The screen carries a PICTURE, following the same Symbol/Preview/Real control
      the keys do** — `services/status_screen.py` composes it (Qt-free, lit pixels),
      `gui/layout_dialog/status_screen_render.py` makes the QImage, and
      `board_plate.set_screen_images` paints it into the lit rectangle. What is
      decided, not incidental:
      - **It draws the WHOLE panel — it is a PORT of the firmware's own preview tool**
        (`qmk_firmware/keyboards/polykybd/tools/status_oled_preview.py`, itself a
        mirror of `split72/status_oled.c` `oled_update_buffer`), function for function
        and coordinate for coordinate, so the two files diff line for line. It shipped
        as a hand-written subset first — top row, side marker, layout name, every other
        row dark — on the reasoning that the RGB effect, WPM, brightness and language
        are live DEVICE state the editor does not have and a placeholder is a number
        true of nothing. ⚠️ **That reasoning was rejected in review**: a status panel
        showing three of its eight rows reads as broken, not as honest, and the
        firmware tool has carried representative values for exactly this purpose all
        along. So the editor uses the tool's own placeholders and the module says
        plainly that they are not measurements — **do not wire a UI readout to them.**
      - ⚠️ **A PORT DRIFTS, and nothing in this repo can see the firmware move — so it
        is pinned to a GOLDEN FIXTURE**, `tests/services/status_panel_golden.json`,
        generated from the firmware tool by `scripts/gen_status_panel_golden.py` and
        compared PIXEL FOR PIXEL. Two halves, and each covers what the other cannot:
        the fixture comparison runs with **no checkout**, so the port cannot drift from
        what was frozen; a second, checkout-gated test re-derives the fixture live, so
        `status_oled.c` moving a row is caught on the machine that moved it. A
        structural comparison would be worthless — both sides are Python read from the
        same constants and would agree by construction.
      - ✅ **The pair FIRED, and what it caught was the port — not the fixture.**
        Measured 2026-09-09 (firmware 0.21.0 → 0.23.3): the checkout-gated half went
        red with *"the firmware panel moved"*, and the cause was qmk `2bb724ce38`,
        which split the status OLED's percentage arithmetic in two — saturation is
        genuinely 0..255 and keeps `byte_to_percent`, while the VALUE is capped at
        `RGB_MATRIX_MAXIMUM_BRIGHTNESS` (100) and gained `val_to_percent`, so a
        fully-lit matrix used to report 39%. The firmware moved its own preview tool
        with the C; this port did not. ⚠️ **Regenerating the fixture ALONE is the wrong
        fix and the suite says so** — with the new fixture and the old helper,
        `test_the_port_draws_WHAT_THE_FIRMWARE_TOOL_DREW` fails on both RGB cases
        (verified by reverting just the helper). The fixture is the BRIDGE: when the
        live half goes red, read the firmware diff and port the change, then
        regenerate; a green run needs both.
      - ⚠️ **Neither half fires on a clone that is BEHIND** — the live one re-derives
        from whatever checkout is there, so it happily confirms a fixture frozen
        against the same old firmware. This drift sat unnoticed until a `git fetch`
        made the clone current. Same shape as the `--check` trap above, and the same
        remedy: fast-forward the clone before trusting either answer.
      - ⚠️ **A fixture at the firmware's DEFAULT values pins only the easy half.**
        Those defaults saturate: `brightness=50` IS `FULL_BRIGHT`, so every gauge
        segment is lit and no unlit one exists to keep its documented 1px foot, and
        `sat=255`/`val=100` round identically with and without the `+127`. Measured —
        three mutations of the port (drop the foot, drop the percent rounding, swap the
        gauge fill) **all ESCAPED** against the four default cases and are caught by
        the two non-saturating ones added beside them. Same family as the status-OLED
        layout rule in `qmk_firmware/CLAUDE.md`: check the worst case, not the default
        fixture. Nine of ten mutations are caught; the tenth (deleting
        `brightness_to_level`'s outer `min`) is **inert by construction** — `contrast`
        is clamped a line above, so no input reaches it — and is kept because the
        firmware's expression is the same and a port that tidies a redundancy stops
        diffing against what it mirrors.
      - **One honest departure**: hardware names the BASE layout on that row and this
        names the layer being edited. Identical for layers 0..4; above them it says
        `Fn` / `Numpad` / `Utility`, which is what an editor wants.
      - ⚠️ **`set_keycodes_for_layer` OWNS `current_layer`, and it did not.** That
        attribute was written only by the layer-button handler, so calling the method
        directly left the two disagreeing — and the next MODE change repaints with
        `current_layer`, silently putting the board and both panels back on the last
        *clicked* layer. Measured: show layer 5, toggle Symbol → Preview, get layer 0.
        The layer that ends up on screen is what everything else means by "the layer
        being edited" (the keycode assignment indexes the buffer with it), so the one
        method that draws it is the right writer.
        - ⚠️ **Drive that test through `set_keycodes_for_layer`, not the button** — the
          button sets `current_layer` on the way past and hides exactly this.
      - ⚠️ **A failed keymap read used to take the panels with it.** The mode switch's
        repaint sat inside `if self.key_buffer is not None`, so with the keys locked
        down the panels never followed the mode at all. They carry the LAYER, not the
        keymap; a board that cannot be edited still says which layer is selected.
      - ⚠️ **"The panels open on the keyboard's default layer" is NOT pinned by the
        test that says so, and the first draft claimed it was.** `_add_board` does draw
        them before the default layer is read, but the default mode is Symbol — so they
        are blank until the user picks Preview, and that pick repaints at
        `current_layer` regardless. Measured: deleting the startup
        `set_keycodes_for_layer` outright leaves the test green. What that actually
        breaks is the KEYS (layer 0's keycodes under a layer-3 tab), which is a keycap
        claim and belongs in a keycap test.
      - ⚠️ **A missing face SUBTRACTS, it is never a precondition** — and expecting an
        empty panel from no faces at all was wrong: the role icons, the brightness
        gauge and the speed box are bitmaps and drawn rectangles, so they survive every
        missing font. That is what the degradation test pins.
      - ⚠️ **The Real filter is the `oled` preset, NOT `keycap`.** There is no keycap
        over a status display — it is a bare panel behind a window — so the cover's
        diffusion and jitter would model a light guide that is not there. The keys and
        the screens therefore use different presets on purpose, both out of
        `fontpack_render.apply_oled_style` so neither is a second set of numbers.
      - **The faces come from `KeycapPreview.status_faces()`**, i.e. whichever source
        won the shipped-vs-checkout compare, so one board cannot draw keys from one
        firmware and screens from another. That needed `_Small_` 15px added to the
        export's `ui_fonts.plyf` — the third standalone face, which the macro-caption
        note already said was the right fix rather than another fallback path.
        ⚠️ Five faces are wanted, not three, and **two of them are found by COVERAGE
        rather than by name**: the firmware tool names `IconsFont` and
        `NotoEmoji_Medium_World_20pt16b` out of its parsed headers, and the host has no
        names for pack fonts at all — so the icon face is the first pool font covering
        `0x80` and the globe the first covering `U+1F310`. Front-to-back precedence
        makes both exact today (the World face covers that one codepoint alone), and a
        renamed header cannot quietly cost the panel a row.
      - ⚠️ **`_refresh_screens` swallows its exceptions (decoration must not take the
        editor down), so a plain `AttributeError` in the Real branch cost nothing but
        a `log.debug` and the panel just stayed flat.** That shipped for the length of
        one test run. `tests/gui/kb_layout_screens_test.py` drives the real dialog for
        exactly that reason — a renderer-level test cannot see wiring that is never
        reached, and the fail-soft `except` is what makes the wiring invisible.
  - ⚠️ **The grid search resolves the corner to 0.05U, and that millimetre is a
      millimetre of SCREEN** — the corner's width is what the module is scaled
      against — so `exact_span` re-measures the one band the panel occupies off the
      polygon rather than off the grid. The containment test still needs a tolerance:
      the outline is fitted, so a point can land on the boundary, and a ray-cast
      answers arbitrarily there.
    - ⚠️ **`_top_at` at the polygon's EXTREME x lands on a vertex and returns the
      corner rather than the top edge.** That put one half's panel 0.085U below the
      other's, on two boards that are mirror images — so `case_top_over` insets 0.4 mm
      from both ends. Consequence worth knowing: at the very corner the panel clears
      the case by less than a bezel (0.28U measured), which is why the placement test
      bounds the tightest gap across the width instead of asserting one bezel.
  - ⚠️ **The tiles are dark in BOTH themes** (`RenderableKey` hardcodes its greys),
    so the plate has to work under dark keys either way.
  - **The two themes are NOT one palette at two lightnesses.** Dark draws a graphite
    board on the view's own ground; light draws a GREY board on a blue ground
    (`LIGHT["scene"]`, painted by `add_board` via `setBackgroundBrush`) — the blue
    moved to the background so the board reads as the object rather than as the
    biggest coloured shape on screen. `DARK["scene"]` is None, which must stay a
    no-op: dark's ground is the palette's and nothing here should second-guess it.
    The light plate is deliberately the DARKER of the two (pinned as a relation, not
    a literal): a plate a shade off white reads as a differently-coloured page rather
    than as a board lying on one.
  - ⚠️ **The BOARD is neutral and every stroke is near-black — the blue survives only
    as `LIGHT["scene"]`.** The plate, the screen bezel and all three outlines carried
    the brand mark's blue → cyan sweep, which on a picture of a keyboard reads as a
    lit edge rather than as a case; the ground is the one place the colour describes
    the page instead of the object. `test_the_board_and_its_outlines_are_NEUTRAL`
    bounds the channel spread at 4 for every key but `scene`, so a re-tint fails while
    a lightness tweak does not.
    - ⚠️ **"Every outline is darker than its fill" was written first and is WRONG.**
      The bezel is the darkest thing on the board, so a stroke darker than it would be
      invisible — `glass_edge` is deliberately the *lighter* of the two, because what
      it separates the bezel from is the PLATE. The property that actually holds for
      all three is that none of them is bright (`test_every_OUTLINE_is_DARK` bounds
      lightness at 90), plus the one real relation: the plate's edge must read against
      the plate.
  - ⚠️ **The screen picture is FITTED inside the lit rectangle and inset clear of the
    frame — scaling it to the rectangle's WIDTH put it on top of the bezel, by two
    independent mechanisms.** Reported as the display extending over the bezel:
    - the panel is 2:1 and the lit rectangle no longer has to be (dropping the side
      bezel reshaped it), so a width-derived height simply overflows; and
    - a rect item's pen is **centred on the edge**, so half the stroke lies inside,
      and a picture that exactly fills the rectangle covers that half.
    So `set_screen_images` scales by `min` over both axes of the box inset by
    `ACTIVE_PEN` and centres the result, and `SCREEN_BOX` carries the HEIGHT it had
    been managing without. The pen widths are named constants for that reason — a
    stroke and the inset that clears it must not drift apart.
    - ⚠️ **The old test asserted the picture filled the rectangle EXACTLY**, i.e. it
      had the defect as its contract; that is why nothing caught this. Its replacement
      bounds the width from BOTH sides — an inset that ran away is as wrong as none.
    - ⚠️ **The containment test derives the rectangle from the DESCRIPTION, never
      from `SCREEN_BOX`.** Reading it back off the item makes the check self-consistent
      with whatever the item cached: measured, replacing the real height with `width/2`
      escaped exactly that way, because the lit aspect (2.002) is a hair off the
      panel's 2.000 and the error is a fraction of a pixel. Eight mutations are caught
      now; that one needed the box asserted against the description as well.

---

## Key pictures — Symbol / Preview / Real

- **The editor's key pictures are a THREE-way group — Symbol / Preview / Real —
  drawing every key through the FIRMWARE's own renderers** (`gui/layout_dialog/keycap_preview.py`, driving `tools/oled_preview.py`
  for the language LUT and `tools/lang_demo.py` for the `keycode_helper.c` static-text
  map; macros go through the host's own composer). Off is the default, and off means
  each key shows its keycode text.
  - ✅ **The DATA ships with the host now (2026-09-01) — `polyhost/res/preview/`,
    written by `scripts/export_preview_data.py`, loaded by
    `polyhost/services/preview_data.py`.** Until then both halves read a
    `qmk_firmware` clone beside the install and the LUT half needed `openpyxl`, so
    the feature was unavailable to anyone who is not a firmware developer **and
    silently wrong for anyone whose clone had drifted** — a blank Fn key, blank
    emoji/Intl keys and retired moon brightness icons were all ONE clone that was
    months behind the connected keyboard. 420 KB: `resident.plyf` (the fonts
    compiled into the firmware, so in no bundle) + `ui_fonts.plyf` (the standalone
    faces no codepoint can reach) + the legends **resolved to codepoints**, the raw
    LUT grid, the named glyphs and the layer enum. `openpyxl` left
    `requirements.txt` with it; it is a dev dependency (`tools/requirements.txt`).
  - ⚠️ **A firmware checkout still wins, but ONLY by being strictly newer**
    (`preview_data.choose_source`) — a developer's tree is ahead of the last release
    and previewing it is the whole point, while a clone that is merely old is the
    case above. **EQUAL versions take the shipped copy**: it is the one that was
    tested, and re-parsing the same firmware twice cannot do better. When a checkout
    loses, `source_info()` says so ("a firmware checkout is present but is not
    newer") — silence there reads as "my clone is being used" and sends the next
    round after the clone.
  - ⚠️ **A STALE export costs a KEYCODE ITS PREVIEW, and it reads as a rendered
    keycap rather than a missing one — the key falls back to its keycode TEXT.** The
    shipped copy carries a `fw_version`, so a keycode added since the last
    regeneration has no name and no legend in it: `KC_MACRO_REC` shipped at export
    0.17.2 against firmware 0.19.1 and the REC key drew its token, reported as *"the
    rec button has no preview"* (field, 2026-09-08). `scripts/export_preview_data.py
    --check` names every stale file; regenerating writes all four (they are one
    snapshot — leaving them at different `fw_version`s is worse than the staleness).
    - ⚠️ **`--check` answers against WHATEVER firmware clone sits beside the repo, so
      a clone that is BEHIND produces a false STALE list naming the wrong files.**
      Measured 2026-09-09: with the clone 33 commits behind (fw 0.21.0) it reported
      `legends.json` and `named_glyphs.json` stale and `lang_lut.json`/`layers.json`
      current. Fast-forwarding the clone to `origin/PolyKybd` (0.23.3) inverted that
      completely — all four files' CONTENT was already byte-identical to what was
      committed, and only the `fw_version` stamp lagged. So
      `git -C ../qmk_firmware fetch origin PolyKybd` and confirm the checkout is not
      behind BEFORE believing the list; the report is a COMPARISON and one of its two
      sides is whatever you happen to have checked out. ⚠️ The sizes it prints are the
      RE-DERIVED ones, not the committed file's, so a size shown there is not evidence
      about what is in the repo — `git show HEAD:<path> | wc -c` is.
    - ⚠️ **A DEVELOPER CANNOT SEE THIS**, which is why it needed a test that pins
      the source. A firmware checkout that is newer wins the compare above, so the
      editor draws the clone's legends and the stale export is invisible on the very
      machine that would regenerate it. `test_a_STATE_DEPENDENT_legend_previews_too`
      builds `KeycapPreview(source="shipped")` for exactly that reason — confirmed by
      running it against the pre-regeneration export: green through the checkout, red
      against the shipped copy.
    - **Regenerating catches up on everything else too, so expect a wide diff.** The
      0.17.2 → 0.19.1 pass moved ~200 `lang_lut` grid cells: the workbook had gained
      the `altgrhalf` settings rows (which renumber every row under them) and the
      2026-09-03 cursor-nudge tuning. That is the export doing its job; the pixel
      parity test above is what says the result is right.

  - ⚠️ **The two sources are pinned to draw IDENTICALLY, by rendering, not by
    comparing structures.** `test_the_two_sources_draw_the_SAME_keycaps` renders
    every keycode the editor can show from both and requires the pixels to match
    (measured: 211 static keycaps + 7,840 letter keycaps across 160 languages, zero
    differences, zero coverage gaps either way). The export resolves legends with
    the same code the checkout path does, so any comparison of the DATA would agree
    by construction — the pixels are the only claim worth making.
    - ⚠️ **`KeycapPreview(source=…)` forces a source and deliberately does NOT fall
      back**, because a comparison that silently substituted one source for the
      other would report them identical for the least interesting reason.
    - ⚠️ **A skip the code under test can CAUSE is not a gate.** The
      checkout-is-unused test first skipped whenever the source was not "shipped",
      so a mutation pinning the pick to `"checkout"` — i.e. reinstating the field
      bug exactly — made it SKIP rather than fail. It now DERIVES the expected
      source from the two versions and asserts it; mutation-checked in both states.
  - Six traps and a design note:
  - ⚠️ **Load the two halves INDEPENDENTLY.** Coupling them shipped once: `openpyxl`
    was undeclared in `requirements.txt`, so on the author's machine the letters *and*
    the modifiers/custom keys both went dark and **only macros previewed** — reported
    as "I can only see the M0 key with a preview render". Each half now reports its own
    `reason` and the tooltip names the missing one, because a partly-loaded preview
    (macros and modifiers drawn, every letter falling back to text) reads as "broken"
    with nothing anywhere to explain it. (Shipped data has no such split — the LUT is
    in the export — so this applies to the checkout path only.)
  - ⚠️ **The missing dependency failed SILENTLY** — `usable` read False in 0.00 s,
    indistinguishable from "no firmware checkout". A preview that cannot say *why* it
    is unavailable is a preview nobody can fix.
  - ⚠️ **`_tools_dir()` is FOUR dirnames up, not three** — three lands on `polyhost/`
    and finds no `tools/`, which presents as the same silent False.
  - ⚠️ **A `FlowLayout` inside a widget capped at `setMaximumHeight(40)` swallows
    wrapped rows with no error.** Adding the toggle with a sibling `addStretch(1)`
    squeezed the layer strip to 118 px, it wrapped, and **seven of the eight layer tabs
    vanished** — reported as "I can only see one layer". Give the widget a stretch
    FACTOR (`addWidget(self.layers, 1)`); never put an `addStretch()` beside a
    flow-laid-out widget.
  - ⚠️ **Strip a C continuation as `re.sub(r"\\\s*\n\s*", " ", ...)`, never a blanket
    backslash strip** — the legends are `U"…"` literals, so removing every backslash
    turns `U"\f\f\f"` into `U" f f f"` and the keycap renders `f f f f`.
    - ⚠️ **…and the shipped pattern asked for TWO backslashes, so it never matched
      anything.** A C continuation is ONE. Every multi-line legend macro therefore
      kept a literal `\` at the front of its body, which resolves to a real glyph —
      the five settings keycaps drew a backslash before their label. It hid behind
      the size-op refusal below (those were the only multi-line macros) and surfaced
      the moment they started rendering. Over-escaping a raw-string regex fails
      **silently**; the guard is now a unit test on the parser
      (`tests/gui/keycap_preview_macros_test.py`), not the eye.
  - ⚠️ **The glyph loader kept only the FIRST literal of a multi-token `#define`,
    and a TRUNCATED legend is worse than a missing one** (field, 2026-09-01). It
    still renders, so it reads as correct-but-incomplete rather than as absent, and
    nothing anywhere says a body was dropped. Three keycaps shipped that way:
    `ICON_CONTEXT_MENU` collapsed to `U" "` — a SPACE — so the Context-menu key drew
    a perfectly valid blank; `ICON_SCRLOCK_OFF/ON` to `U"Scr"`, so Scroll Lock drew
    its letters with the lock badge gone; and `ICON_PAUSE_TEXT` to a bare cursor op,
    which nobody had noticed. The six `HINT_POS_*` / `HINT_SZ_*` constants are
    coordinate PAIRS and lost their y.
    - **`load_named_glyphs` reads the whole body now** — continuations joined,
      nested macros substituted, function-like `HINT_*()` calls expanded. The
      expander (`parse_function_macros` / `expand_function_macros`) MOVED into
      `oled_preview` for this: it expands the macros `named_glyphs.h` defines, so it
      belongs beside the loader that reads that file, and the loader needs it to
      resolve a body that calls one.
    - ⚠️ **A `None` check cannot catch this class.** The truncated context-menu
      legend resolved, drew, and produced a valid image — of nothing. The test
      counts LIT PIXELS, and the scroll-lock one counts them to the right of the
      text specifically, because "Scr" alone already clears any blank threshold.
    - ⚠️ **`re.sub` reads a string replacement as a TEMPLATE**, so expanding an
      argument carrying a C escape (`HINT_MOVE(HINT_POS_CTXPTR)` → `U"\x42" U"\x0C"`)
      raised `bad escape \x` and took the entire glyph table down. Latent for as long
      as this only expanded the settings labels ("IDLE:", "Pulse"). Use a replacement
      FUNCTION.
  - ✅ **MOVE / BADGE / ERASE / ROT are DRAWN now**, which is what makes those
    keycaps render rather than merely be refused. Ported from
    `kdisp_draw_badge_rect` + `rr_row_inset` + `kdisp_draw_glyph_rot_half_at`
    (`base/disp_array.c`) and `kdisp_gfx_rot_half_extent` (`base/font_lookup.c`).
    Four things that are load-bearing:
    - **The badge is checked against FIRMWARE DATA, not against itself** — its
      silhouette must equal the baked `ICON_CAPSLOCK_OFF` glyph, which is the claim
      the firmware's own comment makes. That fixture is the C's, so a Bresenham arc
      (which insets 1,0 where this must inset 2,1,0) fails in the suite rather than
      as a keycap drawn slightly wrong.
    - ⚠️ **ERASE must reach the TEXT paths too.** The glyph plotting went straight to
      `setpix`, so `HINT_ERASE` covered only the composite ops and an engaged lock
      badge drew its arrow LIT — a solid blob instead of an inverted badge. Everything
      now goes through one `plot()`, mirroring `kdisp_plot_ink`; the C carries the
      same scar in its own comment.
    - ⚠️ **ROT rotates at FULL resolution and halves AFTERWARDS**, hence the 2×2 loop
      inside the pixel loop. Halving first throws away the pixels the rotation needs
      to rebuild an edge, and the arrowhead it exists for comes out visibly broken.
      Screen y runs DOWN, so a visually counter-clockwise turn is a NEGATIVE angle —
      the `(24 - step)` index. Getting that sign backwards mirrors the arrowhead,
      which reads as a plausible glyph rather than as a bug.
    - **`bbox` still skips them**, matching the firmware's own RELATIVE bbox form: a
      MOVE names an absolute buffer position and BADGE/ROT plot at the cursor, so
      none of it is knowable without the draw origin that form does not have.
  - ⚠️ **A legend whose MACRO the glyph table does not know draws the macro's own
    NAME as text, and two keycaps shipped that way** (2026-09-01): the mute key
    rendered the literal word `ICON_MUTE` and media-stop `ICON_MEDIA_STOP`. It is
    invisible from the code — `resolve_token` falls back to parsing an unknown token
    as the body of an implicit `U"..."`, which is right for a bare LUT cell and wrong
    for a macro name, so the legend resolves, every op in it is supported, and the
    picture is a line of capitals. **Two separate fixes, and both are needed:**
    - `load_named_glyphs` only matched `#define NAME U"…"`, i.e. a SINGLE literal, so
      a macro built from other macros (`#define ICON_MUTE  PRIVATE_MUTE U"\f\f"
      ICON_CANCEL_X`) was skipped entirely. It now collects those bodies and expands
      them afterwards, so header order does not decide it.
    - What still cannot be expanded (a body of function-like calls) is **refused**,
      via `Lang.unresolved_tokens()` — the sibling of `Renderer.unsupported_ops()`,
      with the same rule: refusing is honest, drawing capitals is not. ⚠️ Ask it
      about a LEGEND, never a setting cell — `HIDE` is a legitimate setting value
      and looks exactly like an unresolved macro.
  - **A legend using an op the renderer lacks is REFUSED, not drawn — and the
    RENDERER answers that question now, not a list in `keycap_preview`.**
    `oled_preview.Renderer.unsupported_ops(cps)` returns the ops it cannot follow;
    empty means the legend is safe to draw. The old module-level `UNSUPPORTED_OPS`
    named `HINT_SMALL` (`\x10`) and `HINT_MID` (`\x16`), and went stale the moment
    both were implemented — the same enumerating-guard shape recorded in the review
    conventions above.
    - **Both size ops are supported now** (2026-08-29), so `KC_EDEN`,
      `KC_GLYPH_SCRIPT`, `KC_IDLE_STYLE`, `KC_TOGMODS`/`KC_TOGTEXT` and the ten
      half-scale two-liners (`KC_STORE_EE`, `KC_SELECT`, the `KC_OS_*` keys, …) draw
      their real legends. `HINT_MID` needs the standalone 19px face, which is NOT in
      `ALL_FONTS[]` — build the renderer with **`oled_preview.load_renderer(font_dir)`**
      rather than `Renderer(load_all_fonts(d))`, or `\x16` silently renders full size.
      It degrades rather than raising when `util_font.h` is missing (a second
      prerequisite must not take the other legends down with it) and reports `\x16`
      as unsupported in that state.
    - **What is still refused** is the ops needing a primitive this model does not
      have — and the set has shrunk twice, so read it off `SUPPORTED_OPS` rather
      than off this line. MOVE (`\x0E`), BADGE (`\x13`), ERASE (`\x14`) and ROT
      (`\x15`) were implemented on 2026-09-01; **HALF (`\x0F`) and BASE (`\x17`) on
      2026-09-09** — HALF because the RGB value keycaps composite a halved droplet/sun
      beside a full-size `+` and HINT_SMALL cannot (it latches for the rest of the
      run), BASE because it is the way *out* of that latch and of `HINT_MID`, which
      the RGB preset keycaps need for a half-scale `Preset:` over a mid-face effect
      name. That leaves THIN (`\x11`, the decimating sibling of HALF) and FRAME
      (`\x12`, a rounded rect at a radius the badge drawer does not take).
      ⚠️ **BASE has to clear the latch in BOTH walkers** (`bbox` and `draw`), like
      every other op here — and note it is the firmware that owns the semantics:
      `\x10` after `\x16` half-scales the *mid* face rather than returning to base,
      so mirroring "small = mid = False" is only correct because that is what
      `disp_array.c` does.
      ⚠️ Implementing one is TWO edits — the draw dispatch and `SUPPORTED_OPS` —
      and doing only the first leaves every legend using it still falling back to
      its keycode text, which looks exactly like the op not working.
  - ⚠️ **The renderer's `\v` and `\t` steps need C TRUNCATING division — Python's
    `//` silently produced a ZERO step.** Both are `x += (x / N + 1) * N` on a cursor
    that can be **negative** relative to the origin: `MID_TWO_LINE` lifts the first
    baseline 10px before stepping down a line. C truncates toward zero
    (`-10/15 == 0`, step 15); Python floors (`-10//15 == -1`, step **0**), so the
    second line landed on top of the first. Only a legend that moves the cursor up
    before a `\v` can reach it, which is why it went unnoticed until the size ops
    made such legends renderable. `_trunc_div` names the rule.
    - **This is the "run it and look" rule earning its keep.** The 31 bbox cases
      ported from the firmware's own `font_bbox_tests.cpp` all passed with the bug
      present — the C suite has no negative-cursor `\v` case either — and one
      contact sheet of the affected keycaps showed it immediately.
  - **`tests/tools/oled_preview_bbox_test.py` ports the firmware's bbox expectations
    verbatim** (same synthetic fonts, same display lists, same boxes, out of
    `base/tests/font_bbox_tests.cpp`). A Python model of C checked only against
    itself proves nothing; these fixtures are the C's, so a divergence fails in the
    host suite rather than showing up as a keycap drawn slightly wrong. Keep the two
    in step when either side gains a case.
  - ⚠️ **REAL puts the same keycap through `fontpack_render.apply_oled_style`, and
    that preset is SHARED with the font-pack inspector on purpose.** Both surfaces
    offer "how it really looks"; the knobs (`simulate_oled`'s jitter, diffusion,
    stagger, brightness) inlined per call site would give one physical panel two
    different-looking previews with nothing to say which was right. `"normal"` returns
    the image untouched so a caller routes every mode through one call.
  - ⚠️ **REAL is rendered at `KEYCAP_REAL_SCALE` (3) output pixels per OLED pixel, not
    at 1:1 — the scale is not cosmetic.** The pixel grid, the bloom radius and the
    per-pixel jitter are all sized from it, so at 1 there is literally nothing to see.
    The tile then scales the larger image down, which is also why zooming the view in
    reveals more of the panel instead of a bigger flat bitmap.
  - ⚠️ **Both halves go through ONE `_pixmap()`**, because the macro keycaps and the
    firmware-composed legends are rendered by different code and used to become
    pixmaps separately — the shape that would leave a board half simulated. Both
    caches hold PIXMAPS, so a mode change has to DROP them; keeping them leaves the
    previous mode on screen until something else invalidates it, which reads as a
    dead button.
  - ⚠️ **SYMBOL stays enabled when the fonts are missing** — it is the fallback the
    other two degrade to, so disabling the whole group would leave nothing selectable.
    REAL additionally needs Pillow (`gui/oled_look.available()`); it is a hard
    requirement, but a broken install must cost the picture, not the editor.
  - **The tile draws a keycap with `SmoothPixmapTransform`.** It is always a
    DOWNSCALE — a 72x40 keycap lands in a tile about 50px wide — and Qt's default
    nearest-neighbour drops whole pixel rows, which was enough to break a small
    glyph's stems: the editor showed a mangled letter the keyboard draws cleanly.
    Found by rendering the two modes side by side, not by reading the paint code.
  - **Two things are deliberately never previewed**: a `KC_TRNS` slot (the keyboard
    draws the layer below, so a preview here would invent a legend the key does not
    have) and the two keys with no OLED behind them (matrix `(3,7)` and `(8,0)` — the
    inner keys documented in the firmware's non-rectangular display grid).
  - ⚠️ **A `Lang` from the SHIPPED export is built with `object.__new__` — it has
    the grid and the names and NOTHING `__init__` would have set.** Both
    `preview_data.lang_reader()` and `KeycapPreview._load_shipped` do this
    deliberately (the storage changes, the rules stay in one implementation), so any
    helper reaching for an attribute `Lang.__init__` assigns must use `getattr`. The
    Shift-preview rule read `L.xlsx` to find the firmware module beside the workbook;
    on the shipped path that raised `AttributeError` inside `render_key`, the caller's
    handler dropped that keycap, and the resolver's **module-global cache had already
    been written** — so every LATER preview silently lost its suppression too. Caught
    by Greptile on host#210, and both halves are one root cause.
    - **Cache the resolution ON the `Lang`, never in a module global.** Two `Lang`
      objects legitimately disagree here — a checkout one resolves, a shipped one
      cannot — so a shared global lets whichever loads first answer for the other. A
      global assigned *before* the lookup that can fail is worse still: it poisons
      itself into "no suppression" for the process.
    - ⚠️ **Anything the preview needs from the FIRMWARE tree has to be BAKED into the
      export, or the shipped path is silently less correct than the developer one.**
      The rule lives in `qmk_firmware/.../lang/shift_preview.py`; a host with no
      checkout cannot import it, so `export_preview_data.py` runs it and ships the
      verdict as data (`lang_lut.json` `shift_suppressed`) — the same move the
      firmware makes for the same reason, one implementation with its answer shipped.
      Without it the shipped preview drew 236 previews across 75 layouts the keyboard
      suppresses. `test_letter_keycaps_draw_the_same_pixels` is what proves the two
      sources agree, and it is why that test renders rather than compares structures.

---

## Where the preview DATA comes from, and how it goes stale

- ⚠️ **A GENERATOR whose default source path has gone dead fails SILENTLY, and its
  output then rots for months with nothing to notice.** `scripts/generate_layer_names.py`
  produces `polyhost/res/layer_names.yaml`, which is what labels each layer in the
  layout editor. Its `DEFAULT_LAYERS_H` pointed at
  `qmk_firmware/keyboards/handwired/polykybd/split72/keymaps/default/layers.h` — a path
  that died **twice over**: the enum moved out of the per-keymap directory when
  split72/split42 began sharing one keymap, and out of `keyboards/handwired/` when the
  boards were promoted. Nothing failed, because nothing ran it. The committed file still
  listed **14** layers ending in `EMJ0`/`EMJ1`, a split the firmware had not had in a
  very long time, so the editor was mislabelling the tail of every layer list (found
  2026-08-26, only because a layer merge made it *worse* and prompted a look).
  - **This is a different failure from the mirrored-file drift already documented
    here.** `noto-fonts.yaml`, `fontpack_render_settings.json`, `lang_flags.json` and
    `iso_lang_country.py` are *copies*, guarded by "keep both in sync (`cmp`)" — and a
    `cmp` genuinely catches those. `layer_names.yaml` is **generated**, so there is no
    counterpart to compare it against; the only thing that could have caught it is
    whether its **generator still resolves its input**, which nothing checks. When you
    touch any of these, run the generator (or `cmp`) rather than trusting the file.
  - **Make the provenance line machine-independent.** It recorded the absolute path of
    whoever last ran it (`/home/thomaspollak/Repos/qmk_firmware/...`), so regenerating
    anywhere else produced a one-line diff carrying no information — the same noise the
    firmware's font headers get from embedding the `fontconvert` binary path. It now
    records the `qmk_firmware`-relative path.
  - **The layer COUNT was never affected** and needed no change: the editor reads it
    live from the keyboard (`M_KEYMAP_LAYER_COUNT` → `PolyCore.keymap_layer_count()` →
    the firmware's `DYNAMIC_KEYMAP_UPDATE_MAX_LAYER_COUNT`). Only the *names* were
    stale. Worth knowing which half of an editor's layer list is live and which is a
    committed artifact before debugging either.
  - ✅ **RESOLVED for firmware v14+ (2026-08-26): the names come off the wire too.**
    `PolyKybd.get_layer_names()` (cmd 35, `FEATURE_MIN_PROTOCOL["layer_names"]`) asks
    the keyboard, and `KbLayoutDialog._layer_names()` prefers that over the fallback —
    so both halves of the editor's layer list are now live. It also gets *better*
    names: a tag map can only ever carry `L0`, `FL`, …, while the firmware answers
    with what each layer actually is (`Qwerty`, `Stag!`, `ColemkDH`, …, `Fn`,
    `Numpad`, `Utility`).
  - ⚠️ **`layer_names.yaml` and its generator are GONE (2026-09-01), and the layer
    tags come from the SAME source as the legends — `res/preview/layers.json` when the
    shipped data is in use, the checkout's own `layers.h` when it is.** That pairing
    is the whole rule, and it took three tries to see it:
    - **A generated file** — the rot above: a dead generator input, nothing notices.
    - **A hardcoded constant** (tried for exactly one commit, and it is what this
      note used to recommend): worse. The tag has to match the spelling
      `keycode_helper.c` **switches on**, and a checkout from before the Fn merge has
      no `case MO(_FL)` at all — it switches on `MO(_FL0)`/`MO(_FL1)`. So a constant
      saying `5 -> FL` builds a token that tree cannot match and the key goes blank.
      Reported within the hour as "L5 is gone again".
    - **The checkout's own `layers.h`**: correct, because tags and legends then agree
      by construction. `qmk_keycode_helper.parse_layers_h()`; `LAYER_TAGS` remains
      only as the no-checkout fallback and as the yardstick below.
  - ⚠️ **An out-of-step checkout previews WRONG, which is why it now has to WIN a
    version comparison to be read at all** (above). The keycodes come from the
    connected keyboard while every legend comes from the data source, so an old clone
    renames the device's layers under the editor (device index 6 is `_NL`; a pre-merge
    tree's is `_FL1`) *and* draws retired glyphs beside them. When the checkout IS the
    source, `_load_checkout()` diffs its enum against `LAYER_TAGS` and, on any
    disagreement, logs a warning and appends it to `source_info()` → the "Key previews"
    tooltip. ⚠️ **That warning is suppressed for a checkout that won by being NEWER** —
    a newer tree disagreeing with the host's constant is expected, so reporting it
    would fire on every firmware developer's machine and become one more banner people
    scroll past. It is for the fallback case: a checkout read because no export
    shipped. `test_the_shipped_tags_match_the_firmware_enum` keeps the yardstick
    honest; both drift tests are mutation-checked.
    - **The tell that a clone is behind, in one line: the brightness keys.** They
      became a sun family on 2026-08-25 (`9f4fa686e5`); before that
      `keycode_helper.c` returned `PRIVATE_DISP_*`, which are MOON glyphs. Moons in
      the editor mean the clone predates that commit, full stop.
    - ⚠️ **THREE separate reports — a blank L5, missing emoji/Intl keys, and the old
      brightness icons — were ONE stale clone**, and none of them points at it. Two
      rounds were spent inferring which end was stale from the symptoms, wrongly.
      **`python tools/preview_doctor.py` answers it instead**: host + firmware
      commits, the enum diff, every layer key's resolved token, and the brightness
      legend expressions. Ask for its output before theorising.
  - ⚠️ **The reply is `[total][count]` then NUL-terminated names, and the TOTAL is
    what makes it decodable.** `total` is the whole payload length, that byte
    included; the host reads it from the first report, keeps reading until it holds
    that many bytes, and only then splits on the NULs. So termination is arithmetic
    rather than a scan, and the report's zero fill is never examined. Two encodings
    were built first and both are worse:
    - **fixed-width 8-byte records** give the same arithmetic length but cost a
      second report (65 bytes vs 54);
    - **terminated with no total** forces the decoder to find the end by scanning,
      and the only way to separate a real terminator from the zero fill is "an empty
      name means padding" — which makes an **unnamed layer** (a bare terminator)
      indistinguishable from the fill and silently truncates the list.
  - ⚠️ **A robustness argument was asserted here on the strength of a BAD FIXTURE,
    and it was wrong.** The test that "proved" terminated records unsafe fed the
    decoder a **short non-final report**, which the firmware's emit loop cannot
    produce — a short report is always the last one. Measured over every reachable
    failure mode (last report lost, first lost, reordered, nothing arrives), all
    three encodings behave identically, because HID delivers whole 64-byte reports
    or nothing. **Robustness is a wash; the encoding choice is size, report count
    and whether an unnamed layer is expressible.** Before claiming a wire format is
    unsafe, check which scenarios the emitter can actually produce.
  - **Mutation-tested.** The suite catches trusting the buffer length over the
    total, dropping the implausible-total guard, slicing past the total, losing the
    2-byte header offset, and accepting a short name list. ⚠️ The slice-past-the-total
    mutation initially **escaped**, because `test_count_larger_than_the_body_is_incomplete`
    used a bare payload with no report padding — so nothing supplied the empty fields
    that a decoder ignoring the total would read. Padding the fixture to the real wire
    is what catches it: a fixture that omits the padding cannot test the thing the
    padding causes.
