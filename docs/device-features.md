# Device features over HID

Extracted from `CLAUDE.md` 2026-09-14. The prose is unchanged; only heading levels
and relative links were adjusted to suit a standalone file.

## Device features over HID

- **Glyph-script override (protocol 9+; expanded set at v10)**: HID cmd 30
  (`GLYPH_SCRIPT`) selects a glyph-script *override* of the keycap language legends —
  `GlyphScript.STANDARD` (0, normal) or one of the fantasy/retro scripts from the
  `fantasy` font-pack bundle. The `GlyphScript` enum (`command_ids.py`) is append-only
  and byte-identical to the firmware `poly_glyph_script`: `TENGWAR=1`, then the v10
  expansion `RUNES=2, AUREBESH=3, SGA=4, CIRTH=5, IBMVGA=6, C64=7, AMIGA=8, APL=9,
  BRAILLE=10`. Wired like idle-style (cmd 28): `PolyKybd.get/set_glyph_script` +
  `GLYPH_SCRIPT_MIN_PROTOCOL=9`, `PolyCore.get/set_glyph_script`, `M_GLYPH_SCRIPT_GET/SET`,
  `RemoteCore`, and `polyctl glyph-script [standard|tengwar|runes|…|braille]` (choices
  derived from the enum). GUI: the tray **"Glyph Script"** submenu (radio, built from
  the enum via `GLYPH_SCRIPT_LABELS` in `host.py`) **plus** a **"Reset glyph script to
  Standard"** button in the settings dialog (`SettingsDialog.setup(reset_glyph_script=…)`,
  shown only when a device is present). Firmware persists the choice; the glyphs need
  the `fantasy` bundle flashed (auto on connect; regrown to `content_version 2` for the
  expansion — reshipped `polyhost/res/fontpack/fantasy.plyf` + `bundles.json`).
  **Open-ended index (v10+):** the firmware accepts ANY glyph-script byte `0..0xFE` and
  renders the normal legend for one it can't draw, so the host may offer more scripts
  than a given keyboard has (they silently degrade) and **adding a new script needs NO
  `__protocol__` bump** — just a new `GlyphScript` value + `GLYPH_SCRIPT_LABELS` entry +
  the shipped font. The `__protocol__` 9→10 bump happened once, to establish that
  open-ended contract (pre-v10 firmware NACKed unknown indices); don't bump it again for
  more scripts. `GLYPH_SCRIPT_MIN_PROTOCOL=9` is a `FEATURE_MIN_PROTOCOL` entry (see the
  range-connect note in [`protocol-gate.md`](protocol-gate.md)), so the Glyph-Script menu is disabled on a pre-v9 keyboard but
  the rest of the app still connects; within a glyph-script-capable device the script set is
  free to grow.
  - **Each menu entry PREVIEWS its script** (2026-09-07): the icon is a two-glyph
    sample and the tooltip a longer one, drawn offline from the shipped
    `fantasy.plyf` by `services/glyph_script_preview.py` (Qt-free) and turned into
    a `QIcon` by `gui/glyph_script_icon.py`. STANDARD previews the normal Latin
    face from `res/preview/resident.plyf`, so the column reads as a comparison.
    Built on the submenu's first `aboutToShow` (30 ms for all 11), never at
    startup; a missing or malformed bundle leaves the menu exactly as it was.
    Four things were decided by rendering the real menu
    (`tools/render_tray_menu.py`, which now calls `_build_glyph_script_previews()`
    for the same reason it calls `_refresh_fontpack_action()` — a `grab()` fires no
    `aboutToShow`):
    - ⚠️ **The icon is TWO glyphs because a menu icon is a ~16 px SQUARE.** `QIcon`
      scales a pixmap to *fit*, so the six-glyph sample arrives about five pixels
      tall and reads as a smudge. The tooltip carries the rest.
    - ⚠️ **A glyph is scaled against the ALPHABET's ink box, not its own.** Braille
      'a' is a single dot; measured against itself it fills the icon as a solid
      white square. `ink_extent()` over `a..z` keeps the dot a dot — and keeps
      every entry of one script at one scale whatever sample it draws.
    - **The script's font is found by BLOCK BASE, not by position in the pack.**
      `0xE800 + (value-1)*0x40`, mirroring the firmware's `glyph_script_blocks[]`
      (`tools/glyph_script_demo.py` assumes pack ORDER instead — weaker). A pack
      that reorders or lacks a block then yields no preview rather than a preview
      of the neighbouring script; the firmware table is pinned in
      `tests/services/glyph_script_preview_test.py`.
    - **The tooltip image rides in the HTML as a base64 `data:` URI** — Qt's rich
      text loads those, so there is no temp file to write or clean up. The test
      draws it through a `QTextDocument` and counts lit pixels, because a tooltip
      whose image Qt cannot load renders as an empty box and says nothing.
      ⚠️ `QMenu.setToolTipsVisible(True)` is required — action tooltips are off by
      default, so without it the whole tooltip half is a silent no-op.

- **Keycap legend size (protocol 13+)**: HID cmd 34 sets how large a key's MAIN
  legend is drawn — `GlyphSize.SMALL` (the original face), `MEDIUM`, `LARGE`. Wired
  exactly like the glyph script: `PolyKybd.get/set_glyph_size` behind a
  `"glyph_size"` `FEATURE_MIN_PROTOCOL` entry, `PolyCore`, `M_GLYPH_SIZE_GET/SET`,
  the `RemoteCore` mirror, `polyctl glyph-size`, and a **"Keycap Size"** tray
  submenu gated on `self.supports("glyph_size")`.
  - ⚠️ **`GlyphSize` is a CLOSED range and that is the ONE way it differs from
    `GlyphScript` — do not "simplify" it to match.** An unknown SCRIPT index is
    accepted by the firmware and degrades to the normal legend, which is what lets
    the host offer faces a keyboard lacks without a protocol bump. An unknown SIZE
    is NACKed, because it would otherwise persist as a setting that silently renders
    small. So never send a value outside the enum, and don't expect a newer keyboard
    to take one. `tests/device/poly_kybd_capabilities_test.py` pins the contrast.
  - The bigger faces ship in the **`latinbig`** bundle (auto-flashed on connect like
    every other). Latin only: a CJK/Arabic/Indic legend, or a keyboard without the
    bundle, keeps drawing small — so selecting a size is always safe and takes effect
    on its own once the bundle lands.
  - **`tools/glyph_size_preview.py`** renders and clip-checks the sizes straight from
    the FIRMWARE's generated headers, mirroring `plan_main_legend()` coordinate for
    coordinate. `--check` is the gate to re-run after any change to the firmware's
    `latinbig` entries; `--out` writes the contact sheet the docs page uses. Same
    caveat as `oled_preview.py`: it is a Python model of the C and can drift.

- **Macros (protocol 15+)**: HID cmds 36/37/38 behind ONE `"macros"`
  `FEATURE_MIN_PROTOCOL` entry — splitting the gate would let the editor load a list
  from a keyboard that cannot save it. `PolyKybd.get_macro_info` /
  `read_macro_buffer` / `write_macro_buffer` / `get_macro_label` / `set_macro_label`,
  then `PolyCore.macro_list/macro_set/macro_clear`, `M_MACRO_LIST/SET/CLEAR`, the
  `RemoteCore` mirror, `polyctl macro list|get|set|clear`, and a **Macros tab in the
  keycode browser** (`gui/layout_dialog/macro_tab.py`).
  - **A tab, not a window.** The browser is already a `QTabWidget` whose "Layers &&
    Mods" page BUILDS a keycode rather than listing a fixed set, so a macro page is the
    same shape — and it puts authoring and placement in one view. `KeycodeBrowser`
    takes `core=None`; without one the tab is simply absent, and the existing tabs are
    not reordered (pinned by a test, same invariant as the developer-menu one).
  - ⚠️ **`PolyCore.macro_*` is WHOLE-BUFFER on purpose.** The bodies are NUL-delimited
    in one shared buffer, so writing macro 3 means rewriting everything after it;
    read-modify-write is the only shape that cannot corrupt a neighbour. A label-only
    edit skips the body write entirely. The mock device is backed by a real `bytearray`
    rather than a dict of strings for exactly this reason — a per-macro mock could
    never show a neighbour being clobbered.
  - ⚠️ **The label meter is in PIXELS, not characters, and that is not a nicety.**
    `polyhost/services/macro_label.py` mirrors the firmware's
    `kdisp_gfx_text_bbox` for the single-font ASCII case a label always is. Measured
    against the committed `nano_font.h`: `'email'` 25 px, `'work mail'` 48,
    `'password'` 49, `'Hello World!'` 61, `'WWWWWWWW'` **exactly 72** — so the real
    budget is ~12 characters, 8 in the worst case, and a character count is wrong in
    both directions. It parses `nano_font.h` **directly** rather than through
    `load_all_fonts()`, which returns the `ALL_FONTS[]` priority list and deliberately
    excludes the three standalone UI faces (no codepoint can reach them — that is why
    the firmware draws a label through a single-font array).
  - **What a macro can type is keystrokes, not characters.** `macro_body.encode_text`
    REFUSES anything outside printable ASCII + tab/newline rather than dropping it: a
    macro that silently types less than you asked for is worse than one that refuses,
    because you find out when it matters. Accented letters and emoji belong on the
    language/emoji layers, and the docs page says so.
  - `tools/macro_label_preview.py --check` renders the keycap the way the firmware's
    `render_macro_key()` composes it and counts pixels outside the 72×40 window (320
    cells, 0 clipped) — the same "verify by rendering" rule as `glyph_size_preview.py`,
    with the same caveat that it is a Python model of the C and can drift.
  - ⚠️ **The macro ICON lookup (`macro_look.load_render_fonts`) UNIONS the firmware
    headers with the shipped `.plyf` bundles — it must not choose between them, and
    that is the OPPOSITE remedy from `preview_data.choose_source` one section below.**
    Both face the same hazard (a checkout beside this repo is a working tree at
    whatever branch it is on), but the pairs differ: there, two renderings of the SAME
    data, so the newer wins; here, the headers carry the resident half and the bundles
    are what the host actually flashes, and either can be ahead. Preferring the
    headers alone previewed the stale set — a slot's Mayan numeral drew as `M3`
    because `symbol.plyf` v9 ships that font while a clone on `PolyKybd` has no such
    header, and the keyboard drew it perfectly well (field, 2026-09-08). The union is
    safe by construction: `find_glyph` stops at the first font covering the codepoint,
    so appending can only ADD hits. **It fixes the icon PICKER for the same reason** —
    it enumerates candidates from the bundles and then looks each one up, so a glyph
    the headers lacked was dropped from the grid and could not be chosen at all.
    ⚠️ The `(no glyph)` warning still rests on the source being `"headers"`, i.e. on
    the RESIDENT faces having been visible; keep that meaning if the value is reworked.
  - ✅ **The CAPTION half of that preview used to have no such fallback — `_Small_`
    was NOT in `res/preview/ui_fonts.plyf` (it shipped `_Nano_` and `_Mid_` only), so
    `load_caption_faces()` needed a firmware checkout. FIXED by exporting the third
    face**, which is what this note already said the right answer was ("exporting the
    third face, not another fallback path"). It landed for a different consumer — the
    status-screen preview draws every row with it — which is the usual way a
    long-standing gap gets closed.

- ⚠️ **`tools/apply_tuner.py`'s export grammar CANNOT express the `caps` column** —
  its key-line regex is `base|shift|altgr`, matching what the keycap tuner emits, and
  the LUT's four sub-columns are lower/upper/**caps**/AltGr. A bulk edit that touches
  caps cells therefore cannot go through the CLI: **import the module and call its
  `set_cell()` / `str_cell()`** so the surgical `sheet2.xml` path (which preserves the
  other sheets' formula caches) is still the same tested code. ⚠️ Those two are only
  the XML edit — `set_cell()` RETURNS the modified sheet and persists nothing, so the
  caller still owns the language-column arithmetic (`base = 2 + langs.index(lang)*4`,
  `+0/1/2/3` for base/shift/caps/AltGr), rewriting the zip entry, and the `cog -r
  lang_lut.c` afterwards. The whole loop, with its verification steps, is the
  firmware repo's `tune-lang-lut-cells` skill; this note is only about which half
  the CLI cannot do. Hit on 2026-09-03,
  where 14 of the 117 cells drawing `§ £ ± µ` were caps. Widening the regex is a
  bigger change than it looks — the tuner never emits `caps`, so the grammar would
  gain an arm nothing exercises.

