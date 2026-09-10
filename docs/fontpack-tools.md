# Font-pack inspect & extend tools

The standalone window that shows every bundle glyph as the keycap draws it, and
builds new glyphs from a TTF/OTF with pure-Python `fontconvert` parity. Moved out
of `CLAUDE.md` on 2026-09-10: ~13 KB describing two developer dialogs that are
reached from the tray's **Debugging** submenu and are irrelevant to every other
session.

`polyhost/gui/fontpack_inspector_dialog.py` + `fontpack_extend_dialog.py`, with the
Qt-free logic in `polyhost/services/fontpack_*` and `fontgen*`. Both work offline
and in either operating mode — no device needed.

**The division of labour is the thing to hold on to**: the *extend* dialog builds
ONE glyph and previews it (OK / Cancel, nothing accumulated, nothing saved); the
*inspector* owns the per-bundle working copies, the pending-edit list and Save
as… . Look for an accumulate-and-save feature in the editor and you will not find
it.

---

- **Font-pack inspect/extend tools** (`polyhost/gui/fontpack_inspector_dialog.py` +
  `fontpack_extend_dialog.py`, Qt-free logic in `polyhost/services/fontpack_*` +
  `fontgen*`): a standalone window to view every bundle glyph as
  the keycap draws it and to build/splice new glyphs from a TTF/OTF (pure-Python
  `fontconvert` parity). Launched from the tray's **Debugging** submenu (the
  "Inspect Font Packs…" entry), so it is **only shown when the app runs with
  developer mode** (`developer` in `host.py`) — it's a developer/power-user
  tool, hidden from the default menu. Unlike the other Debugging entries it works
  in both in-process and client mode (offline, no device needed). It loads the shipped bundles by default; **"Open .plyf…"**
  adds any saved/exported `.plyf` as a new tab (folded into the merged ALL_FONTS view
  + the Extend sources) so a file saved elsewhere can be re-inspected. ⚠️ **A `.plyf`
  carries no bundle name** — the PlyF header has only abi/`content_version`/font_count
  + per-font global ALL_FONTS index; the bundle id lives in `bundles.json`/the
  filename, so an opened tab is named after the file (`decode_pack` synthesises font
  names as `<filename_stem>#<gidx>`). The **View** selector offers four modes
  (`_BundleTab._mode`): **Glyph** (native size), **Keycap** (plain 72×40 white-on-
  black), and — matching the extend dialog — **Keycap OLED** (raw pixels) and
  **Keycap through cover** (diffused), both routed through `fontpack_render.glyph_cell`
  → `simulate_oled` (which returns an **RGB** cell; `_BundleTab._pm` keeps RGB via
  `_pil_to_pixmap` and only applies the semantic tints below to the plain 'L' modes).
  The grid shows **one cell per codepoint** (a
  deduped, continuous range) honouring **front-to-back precedence** (the firmware
  draws each cp from the lowest-global-index font with a glyph, `_BundleTab._stacks`):
  each cell renders the **winner** — **white** if this bundle draws it, **cyan** if
  it's borrowed from another bundle. When more than one font has the glyph, the
  losers are **overdrawn**: a "**stack**" marker (solid right+bottom border whose
  **depth = number of overdrawn glyphs**, `_stack_pixmap(depth=)`) flags it; hovering
  the bottom-right stack corner shows the overdrawn glyph **in the slot** (dim),
  **cycling** through them when there's more than one (`_hover`/`_cycle_advance`), and
  **double-click there edits the first overdrawn** while a double-click elsewhere edits
  the winner (`_edit_at`; `_on_edit`/`_bundle_of` target the clicked font's *own*
  bundle, which may be a different tab). Overlapping `fonts.yaml` ranges from the same
  source (e.g. a dedicated `_Light_` entry + broad `_EmjEffects_`/`_Emojis1_` all
  covering U+1F4A1) are why a cp can have 2+ overdraws. **Selecting a glyph highlights
  the whole range its font wins** (`_on_selection`, subtle tint), since the pack is
  organised in ranges. A glyph **edited
  this session** (the editor's OK committed it into the working copy) is re-rendered
  in-place from that working copy and bordered **green** (`MODIFIED_RGB`,
  `_BundleTab.apply_working`); "Save as… → Discard" reverts the tab to the loaded
  bundle. Edits **propagate across tabs**: `_commit_edit` rebuilds the merged
  ALL_FONTS view (`_rebuild_all_fonts`) and `_propagate` pushes it to every tab
  (`set_all_fonts`), so a cell in bundle B whose winner or overdrawn (stack) glyph
  lives in the edited bundle A re-renders from the new glyph — the visible
  tab rebuilds immediately, the rest lazily on next show. The inspector's
  **"Peek empty (from source)"** toggle
  renders the *empty* slots from their source font (via `fontpack_extend.peek_source_glyph`
  + the shipped render settings, needs the source font downloaded) as **amber
  previews** — candidates you can then double-click to edit/take; they are not in
  the pack. Peek **prefers a non-emoji (symbol/text) source over an emoji source**
  when the slot's own font isn't itself emoji (`_peek_candidates` style key), so a
  symbol codepoint that also exists in NotoEmoji/NotoColorEmoji previews from the
  clean symbol font (NotoSansSymbols) rather than the emoji glyph — even if the
  emoji font is lower-gidx / in-range / in-bundle. For an emoji slot the deferral is
  a no-op (the emoji source order stands). Peek also offers, as a **last-resort
  fallback, any downloaded catalog font that no bundle uses** (default render
  options, `_BundleTab._catalog` from `noto-fonts.yaml`) — so adding a font to the
  catalog (e.g. NotoSansMath) makes it usable in peek with **no code change**, even
  though it's in no pack. The extend dialog's **Source fonts** browser (always under the
  preview; click a font to use it, downloading first if needed) downloads/assigns
  the Noto source fonts via `polyhost/services/font_downloader.py`, which reads the
  catalog from **`polyhost/res/fonts/noto-fonts.yaml`**. ⚠️ That YAML is the **single
  source of truth shared byte-identically** with the firmware's
  `qmk_firmware/keyboards/polykybd/fonts/noto-fonts.yaml` (which `dl-fonts.sh` reads)
  — keep both in sync (`cmp`). The host stores a *flat* cache keyed on
  `basename(dest)`; the firmware honours the nested `dest` path.
  The extend dialog is a focused **glyph editor** (`FontPackExtendDialog`): it builds
  **one** glyph/font from a source + options and previews it, with just **OK / Cancel**
  — OK exposes the built glyph via `result_font`/`result_label`/`result_edit` (Cancel
  discards); it neither accumulates nor saves. Its preview shows each built keycap
  **next to the smooth, undithered glyph straight from the source font**
  (`fontpack_render.preview_sheet` → `reference_glyph_image`, always antialiased/colour
  regardless of the grayscale toggle), so you can compare the dithered keycap output
  against what the font actually draws while tuning. **Sequence-mode glyphs** (flags,
  matras) have a synthetic PUA pack codepoint the source font has no glyph for, so the
  reference is **HarfBuzz-shaped from the sequence** (`reference_sequence_image`,
  composites the shaped group) rather than looked up by codepoint — otherwise no
  reference showed beside a flag. **Scroll-wheel over the preview
  zooms** it (0.5×–7.0× in 0.5 steps; the render functions take a fractional `scale`,
  `fontpack_render._px` rounds to pixels). A **Preview** radio group (Normal · OLED ·
  Keycap, `_preview_style`) shows the keycap the way the physical per-key OLED renders
  it via `fontpack_render.simulate_oled` (Qt-free, NumPy/PIL) + `preview_sheet(style=)`
  (only the keycap is post-processed; the source reference + chrome stay natural):
  lit pixels are a **cool white** (`OLED_TINT` — a hint of blue; the strong cyan in
  photos is a camera artifact, not what the eye sees) on true black with a slightly
  bluer **bloom**. The two OLED styles are presets over `simulate_oled`'s knobs —
  **OLED** = the raw pixels (crisp square grid, jitter/diffusion off) and **Keycap** =
  as seen through the clear keycap cover (adds **per-pixel brightness jitter** — seeded
  so the lit area shimmers without flicker — a **staggered grid** and a **diffusion**
  blur that lets pixels bleed, modelling the cover's light-guide, not the panel; the
  blur amount is **spatially varied** by a smooth seeded mask — a lighter/heavier blur
  mixed per region so it isn't one uniform smear). A
  post-blur **brightness** gain lifts both styles (higher for Keycap, since the
  diffusion spreads/dims thin strokes);
  `preview_sheet(oled=)` runs **only the keycap** through it (the source-font reference
  + chrome stay natural for comparison) and returns RGB, so the preview pixmap path
  preserves colour (`_pil_to_pixmap`). **Flag keycaps** (the PUA 0xE000 band) are
  drawn on hardware through a **single-font array** (baseline adjustment 0), so the
  keycap render uses the **flag's own yAdvance** as the baseline reference
  (`fontpack_render.base_yadv_for`), NOT the `(yAdvance − IconsFont 40)` shift the
  in-pack g_all_fonts glyphs get — without this a tall flag (yAdvance 54) was shifted
  +14 px down and its bottom rows clipped off the 40 px keycap (the "flag preview cut
  off at the bottom" bug). Emoji (yAdvance 48, drawn via g_all_fonts) keep the shift,
  so the fix is gated to the flag band only. **Reset** restores the render options to
  the values the dialog opened with (`_snapshot` taken after prefill). **Auto update**
  (default on) re-renders on any control change (debounced). Layout niceties: each
  float control (gamma / contrast / exposure / sharpen / saturation) is a **fixed-width
  spin (0.1 step) with a slider beside it** (`_with_slider`, one notch = 0.1); range
  **first–last share one row**; the four flag checkboxes (grayscale/normalize/invert/
  edge) are a **2×2 grid**; the source-font browser's **"Download all" sits on top** of
  the list (clear of OK/Cancel).
  The **accumulate + save** side lives in the **inspector**, not the editor: the
  inspector owns per-bundle in-memory **working copies** (`_work`/`_pending` keyed by
  source index). Each editor OK calls `FontPackInspectorDialog._commit_edit` →
  `replace_glyph` (edit mode) or `splice_font` (whole-font add) into that bundle's
  working copy, appends a pending-edit description, and marks the tab with a "● "
  prefix. The toolbar's **"Save as…"** opens `FontPackSaveDialog` for the current
  bundle: metadata (abi / current content version / working fonts·glyphs·size), the
  **pending-edits list**, an editable **content_version** spin (default current+1 —
  **one bump for all accumulated edits**), and **Save .plyf… / Flash / Discard /
  Close** (`encode_pack(working_fonts, version)` is what's written/flashed; Discard
  drops that bundle's working copy). Flash is only offered when the inspector was
  given a `flash_cb`.
  When you **edit** a glyph, the editor pre-fills the render controls (size,
  dither, normalize/invert/edge/outline, render size, yAdvance, …) from
  **`polyhost/res/fontpack/fontpack_render_settings.json`** — a `global ALL_FONTS
  index → fonts.yaml options` map emitted by the firmware's `generate_fonts.py`
  (`RENDER_SETTINGS`) and shipped here. The `.plyf` carries only rendered bitmaps,
  not the fontconvert options, so this manifest is the only way to recover "the
  settings this glyph was built with". Each record also carries `source_file` (the
  basename of the source TTF, matching `noto-fonts.yaml`), so the edit dialog
  **auto-fills the source font from the download cache** when it's present (else it
  names the file and points at "Download Noto…"/Browse) — the TTF itself isn't
  bundled. Keep it in sync with the firmware copy
  (`base/fonts/generated/fontpack_render_settings.json`).
  **Sequence-mode glyphs** (the language-layer flags): a record with a `sequence`
  field is a HarfBuzz-shaped font (`-S`), so the editor switches to **sequence mode**
  and pre-fills the single group for the edited codepoint (group = `cp − font.first`,
  seq base set to `cp` so Build emits exactly that one glyph). The **flag font is NOT
  in fonts.yaml** (it's `pack_extra` from `gen-lang-fonts.sh`), so it has no record in
  `fontpack_render_settings.json`; its options + `seq_first` + the per-flag
  regional-indicator `sequence` live in **`polyhost/res/fontpack/lang_flags.json`**,
  which the editor uses as the record when the edited cp is in the flag range. ⚠️
  `lang_flags.json` is mirrored **byte-identically** with the firmware's
  `base/fonts/generated/lang_flags.json` (emitted by `gen-lang-fonts.sh`) — keep both
  in sync (`cmp`). Editing a flag needs **NotoColorEmoji** downloaded; if its cached
  file is truncated (a bad download) FreeType fails to open it — re-download. A CBDT
  **colour-bitmap font (NotoColorEmoji) renders whether or not grayscale is checked**:
  it has no outlines, so `fontgen._open_color_font` decodes it via fontTools for any
  source with bitmap strikes (`num_fixed_sizes>0`), not only in `-g` mode — otherwise
  a mono build hit FreeType's "unimplemented feature" on the PNG-based glyph.
  **Matra/combining-mark fonts** (Devanagari/Bengali/Telugu/Tamil/Thai/Vietnamese,
  PUA 0xE100+) are sequence-mode **and** use fontconvert `-C` composite (each group
  composites a mark onto the dotted circle U+25CC). The editor has a **Composite -C**
  checkbox (enabled in sequence mode); `_setup_sequence_edit` ticks it from the
  record's `composite` field (the `fontpack_render_settings.json` matra records now
  carry `composite: true` + `seq_first`, emitted by `generate_fonts.py` from the
  `-C`/`-F` extra_args), falling back to **inferring** it (every group starts with
  `25CC` → composite; regional-indicator flag groups don't) for older manifests.
  Host builds matras via fontgen's mono composite path.

---

- **Source-font download validation** (`font_downloader.py`): a download is rejected
  (`DownloadError`, no file cached) when it's short (Content-Length mismatch) or not a
  complete sfnt (`_validate_sfnt` checks the table directory fits the file) — this is
  the fix for a proxy-truncated NotoColorEmoji that FreeType then refused to open.
  `is_downloaded()` re-validates, so an already-cached corrupt file reads as missing
  and is re-fetched (overwritten); `download_font(force=True)` always re-downloads.
