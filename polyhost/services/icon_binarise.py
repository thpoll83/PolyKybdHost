"""Turn ANY raster or vector icon into the 1-bit ink a 72x40 keycap can draw.

⚠️ THE CONVERSION IS CHOSEN PER ICON, NOT CONFIGURED, and the reason is that no
single rule survives contact with real application icons. Measured over the six
LibreOffice marks plus the Debian logo at the shipping 38x38:

  * the ALPHA SILHOUETTE -- what the Simple Icons path uses, correctly, because
    a monochrome single-path SVG *is* its own silhouette -- renders all six
    LibreOffice icons as the SAME 94.5%-lit page blob. Base, Calc, Draw and
    Impress become one picture. It is nonetheless the right answer for a
    two-tone logo on transparency;
  * LUMA (dark linework lit, composited over white) ranges from 1.9% lit on
    Draw, which is effectively blank, to 56.6% on Base;
  * an ADAPTIVE Otsu split inside the silhouette recovers the content-bearing
    icons and DESTROYS the Debian spiral (1.1% lit, scattered dots), which the
    other two both draw cleanly.

So the module renders all three and scores them. 6 of 7 come out legible and,
more to the point, the six LibreOffice apps become distinguishable from each
other -- which is the property that decides whether a program mark is worth
drawing at all.

⚠️ The remaining failure is real and is not hidden: a smooth full-colour
gradient with no two-tone structure (LibreOffice Draw) has no good 1-bit
reading, and `choose()` returns its best attempt with the score attached so a
caller can decline it. `MIN_SCORE` is that floor.
"""

from __future__ import annotations

import logging

log = logging.getLogger('PolyHost')

# Reject a candidate outside this lit range before scoring it. A render past the
# upper bound is a filled blob carrying no shape; one below the lower bound has
# lost the icon. Both numbers are measured (see the module docstring), not tuned
# to taste: the LibreOffice silhouettes sit at 94.5% and Draw's luma at 1.9%.
# ⚠️ TIGHTENED 0.80 -> 0.70 (2026-09-18) and it costs nothing measured: across
# 1064 renders of 116 real icons NO winning render exceeds 0.623 lit, so the
# change moves zero winners and zero gate decisions. What the old bound admitted
# was a flat filled DISC at 0.763 -- a featureless black circle on the ESC
# keycap, and the fixture `app_icons_test` uses for "does not survive 1-bit".
# It survived because the rewritten score no longer leans on `detail`, which had
# been refusing it as a side effect of being maximised by texture.
MAX_LIT = 0.70
MIN_LIT = 0.04

# The lit fraction a legible keycap icon tends to have. Scoring peaks here and
# falls off either side, so a candidate that is merely *inside* the bounds above
# still loses to one with a healthier balance of ink to ground.
IDEAL_LIT = 0.35

# The lit-balance falls to zero this far either side of `IDEAL_LIT`. It is a
# SOFT preference, unlike the hard bounds above, and its width decides how much
# a heavy render is punished for being heavy.
#
# ⚠️ Measured, and the whole 0.50-0.70 band is within one icon of each other on
# the 22-icon judged set (16-17 of 22), so this is the middle of a plateau
# rather than a fitted peak. Below 0.50 it starts refusing sparse marks that are
# perfectly readable -- GNOME Dictionary's `a` inks 5.5% of the cell.
LIT_WIDTH = 0.55

# A render whose ink fills this much of its own bounding box is a RECTANGLE, not
# a mark, and no threshold on ink or edges can tell those apart -- see the
# `survives` note in `score()`. Measured over 1064 renders of 116 real icons: it
# rejects 10, every one an `alpha` silhouette already at or past `MAX_LIT`, and
# the highest-filling render it lets through is 0.836 (LibreOffice's Start
# Centre, which is a poor reading for other reasons). The synthetic blob fixture
# is 1.000 by construction.
MAX_FILL = 0.95

# Below this, `choose()` has found nothing worth drawing. A wrong or unreadable
# mark is worse than none -- the user cannot tell a bad render from a bug.
#
# ⚠️ The value is taken from where the DATA separates, not chosen, and it has
# been RE-DERIVED TWICE -- 0.30 -> 0.25 when the corpus grew to 130 icons, then
# 0.25 -> 0.08 when `score()` was rewritten (2026-09-18) and the scale moved
# under it. Re-derived over 116 deduplicated real icons (Yaru 256, hicolor
# 512/256/128, /usr/share/pixmaps) plus the suite's synthetic fixtures:
#
#     fixtures   checkerboard 0.000   fragments 0.037   blob REJECTED outright
#     real icons lowest 0.097, then 0.116, 0.175, 0.187 ... median 0.428
#
# So the band 0.037 -> 0.097 is EMPTY and 0.08 sits inside it, clearing the
# fragments by 2.2x and staying below every real icon measured.
#
# ⚠️ It is a WEAKER gate than the number it replaced, and deliberately so. The
# old floor refused the synthetic blob only because `detail` was maximised by
# texture -- the documented defect this rewrite removes -- so removing the defect
# removes that accident. What refuses a blob now is `MAX_FILL`, which is a
# statement about the SHAPE and cannot be defeated by re-thresholding. The floor
# is left holding the fragments and the halftone, which is all the data supports.
MIN_SCORE = 0.08

# The long edge an icon is shrunk to before it crosses the network. The
# receiver reduces to `app_icons.PROGRAM_ICON_BOX` (38) anyway, so 4x that is
# ample headroom for its own LANCZOS pass and everything above it is bytes
# nobody looks at. ⚠️ Cannot be DERIVED from that constant -- `app_icons`
# imports this module, so importing it back would be a cycle -- so
# `tests/services/icon_transport_test.py` asserts the 4x relation instead.
TRANSPORT_MAX_PX = 160



def _to_rgba(image):
    """`image` as an RGBA numpy array, or None."""
    try:
        import numpy as np
        return np.array(image.convert("RGBA"))
    except Exception as exc:
        log.debug("Could not read an icon as RGBA: %s", exc)
        return None


def alpha_coverage(image):
    """The icon's silhouette. Right for a monochrome glyph on transparency."""
    rgba = _to_rgba(image)
    return None if rgba is None else rgba[..., 3]


def luma_ink(image):
    """Dark linework lit, composited over white — the classic 1-bit reading."""
    try:
        import numpy as np
        from PIL import Image
        ground = Image.new("RGBA", image.size, (255, 255, 255, 255))
        flat = Image.alpha_composite(ground, image.convert("RGBA")).convert("L")
        return 255 - np.array(flat)
    except Exception as exc:
        log.debug("Could not take an icon's luma: %s", exc)
        return None


def _otsu(gray, mask):
    """The luminance that best splits `gray[mask]` in two.

    Written out rather than pulled from a library because the only alternative
    in this repo's dependency set is OpenCV, which is a very large dependency
    for one histogram.
    """
    import numpy as np
    values = gray[mask]
    if values.size == 0:
        return 128
    hist, _ = np.histogram(values, bins=256, range=(0, 256))
    total = values.size
    sum_total = float((np.arange(256) * hist).sum())
    weight_bg = 0
    sum_bg = 0.0
    best = (-1.0, 128)
    for level in range(256):
        weight_bg += int(hist[level])
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break
        sum_bg += level * float(hist[level])
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_total - sum_bg) / weight_fg
        variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if variance > best[0]:
            best = (variance, level)
    return best[1]


def adaptive_ink(image):
    """Split the icon's own pixels into ink and ground, and keep the minority.

    ⚠️ The MINORITY side is the ink, always — not the darker one. A modern app
    icon is as often light-on-coloured (LibreOffice) as dark-on-light, so
    choosing by brightness gets half of them inside out, while the drawn detail
    is the smaller area in both.
    """
    try:
        import numpy as np
        rgba = _to_rgba(image)
        if rgba is None:
            return None
        inside = rgba[..., 3] > 128
        if not inside.any():
            return None
        gray = np.array(image.convert("RGBA").convert("L")).astype("uint8")
        level = _otsu(gray, inside)
        dark = inside & (gray <= level)
        light = inside & (gray > level)
        ink = dark if dark.sum() <= light.sum() else light
        return (ink * 255).astype("uint8")
    except Exception as exc:
        log.debug("Could not take an icon's adaptive ink: %s", exc)
        return None


# The pre-dither adjustments the dither conversions run. ⚠️ NOT optional
# decoration -- bare Floyd-Steinberg on an app icon is unreadable noise at this
# size. Normalise + unsharp + contrast is what removes the scatter, and it is
# the stage fontconvert itself always pairs with the dither.
DITHER_ADJUST = dict(normalize=True, sharpness=2.5, contrast=2.5)

# ⚠️ GAMMA IS THE KNOB THAT DECIDES WHETHER A DITHER READS, and the right value
# is PER ICON and points in OPPOSITE directions -- which is why these are three
# scored candidates rather than one tuned default. Measured over the 235-icon
# Yaru set at 38x38: Totem, Text Editor, Weather and Camera want gamma 1.4-2.0,
# while Calculator wants 0.5 (at 2.0 its right panel turns into a texture field,
# at 0.5 Totem's triangle drowns in scatter).
#
# The set is CHOSEN BY MEASUREMENT, not spaced by taste: of every 3-tuning
# combination drawn from a 12-point grid, this one maximises the mean best-dither
# score over the 88 distinct arts (0.317, against 0.225 for the shipped tuning
# alone) and puts the best dither ahead of the best threshold read on 36 of 88
# rather than 21.
DITHER_TUNINGS = (
    ("dither-lo", 0.5, 2.5),
    ("dither", 1.0, 2.5),
    ("dither-hi", 2.0, 3.5),
)

# The block size `fidelity()` compares the render and the source at. It is the
# scale at which a keycap is READ -- at 38px, 4px blocks are roughly the feature
# size the eye resolves at arm's length. Measured over the 87 distinct Yaru arts,
# 2 is too fine (it grades the dither's texture, and a dither wins only 56 of 87)
# and 6 too coarse to separate the gammas; 3, 4 and 6 all sit at 63-65 and 4 has
# the fewest weak matches.
FIDELITY_BLOCK = 4

# A reference block counts as INKED, for the coverage check in `fidelity()`, at
# this share of the source's darkest block; a render's block counts as DRAWN at
# this share of lit pixels. Both are deliberately loose -- coverage asks whether
# a region was drawn AT ALL, not how well, because how well is what the
# correlation beside it already measures. Half the peak splits the two panels of
# every two-tone icon in the corpus, and one lit pixel in a 4x4 block is the
# least a dither can put down while still claiming the region exists.
COVERAGE_INK = 0.5
COVERAGE_MIN = 0.05

# A majority-lit render is only read as an INVERTED picture when this share of
# its unlit pixels is enclosed by ink -- a glyph knocked out of a plate rather
# than the page around a silhouette. The data separates at ZERO and leaves a wide
# empty band: measured at the shipping 38x38, all 13 silhouettes tried (a flat
# disc, a plain rounded rect, and the `alpha` reading of 11 real icons) enclose
# EXACTLY 0.000, while all 20 real plate renders enclose 0.098 to 0.555. Any
# floor inside that band is equally supported; this one sits ~5x above a
# single-pixel hole and ~5x below the smallest real case.
ENCLOSED_MIN = 0.02

def dither_ink(image, box: int, gamma: float = 1.0, contrast: float = 2.5):
    """Error-diffused ink, dithered AT the target size. Keeps midtone AREAS.

    The other three conversions all pick a threshold and throw the midtones
    away, which is right for line art and loses a modern app icon's body: a
    coloured document, a gradient sphere, a solid object. Measured over 14 icons
    this wins on firefox, vlc, telegram, draw, writer and inkscape -- vlc goes
    from four disconnected specks to a recognisable traffic cone -- and loses to
    `adaptive` on vscode, mousepad, ubuntu and math. Neither dominates, which is
    why this is a fourth candidate rather than a replacement.

    ⚠️ The dither MUST run at the final size, not at the source size followed by
    a downscale -- resampling averages the diffusion back into gray and the
    re-threshold then produces mush. Hence `box` here, where the other
    conversions leave scaling to `fit()`.

    ⚠️ Composited over WHITE, so ink is DARKNESS. Over black wins on some icons
    (math, telegram) but loses badly on others (draw, mousepad, ubuntu); one
    ground was chosen rather than adding a fifth candidate for a coin-flip.

    ⚠️ **Offering BOTH grounds as scored candidates was tried and MEASURED
    WORSE — do not re-propose it.** The reasoning is appealing (`choose()` picks
    per icon, so why decide globally?) and the result is not: FS-over-black took
    the top score on six of twelve real icons and on five of those replaced
    clean `adaptive` line art with a halftone field. It scores well for the
    reason it looks bad — `score()`'s `detail` term is `edges/lit`, which a
    dither maximises because every lit pixel in a halftone touches an unlit one.
    It also did NOT move mousepad, the regression it was proposed for. The sheet
    is `docs/images/binarise.png`; the write-up is `docs/generic-icons-plan.md`
    § E5, including the *cohesion* term that was tried next and also refuted.
    """
    try:
        import numpy as np
        from PIL import Image
        from polyhost.services import fontgen_dither as fd
    except Exception as exc:
        log.debug("Could not dither an icon: %s", exc)
        return None
    gray = luma_ink(image)
    if gray is None:
        return None
    rows = (gray > 0).any(1).nonzero()[0]
    cols = (gray > 0).any(0).nonzero()[0]
    if not len(rows) or not len(cols):
        return None
    ink = Image.fromarray(gray[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1])
    scale = min(box / ink.width, box / ink.height)
    ink = ink.resize((max(1, round(ink.width * scale)),
                      max(1, round(ink.height * scale))), Image.LANCZOS)
    small = np.asarray(ink).astype(np.float32) / 255.0
    adjust = dict(DITHER_ADJUST, gamma_val=gamma, contrast=contrast)
    fd.apply_adjustments(small, fd.DitherOpts(**adjust))
    h, w = small.shape
    # ⚠️ `_Bits` is reached for because it is the only bit buffer `dither()`
    # accepts and the module exposes no public constructor; the dither itself
    # goes through the public entry point.
    bits = fd._Bits(h * w)
    fd.dither(small, fd.DITHER_FLOYD_STEINBERG, bits)
    return np.array([bits.get(i) for i in range(h * w)],
                    dtype=bool).reshape(h, w)


def _thresholded(convert):
    """Adapt a coverage function to the (image, box) -> mask contract."""
    return lambda image, box: fit(convert(image), box)


# Each entry is (name, (image, box) -> bool mask). `dither` is last so that a
# tie goes to a thresholded reading, which has no texture to misread.
def _tuned_dither(gamma: float, contrast: float):
    def convert(image, box: int):
        return dither_ink(image, box, gamma=gamma, contrast=contrast)
    return convert


# The THRESHOLD reads -- each picks a cut and throws the midtones away.
THRESHOLD_CONVERSIONS = (
    ("alpha", _thresholded(alpha_coverage)),
    ("luma", _thresholded(luma_ink)),
    ("adaptive", _thresholded(adaptive_ink)),
)

# The DITHER reads -- each keeps the midtone AREAS, at a different gamma.
DITHER_CONVERSIONS = tuple(
    (name, _tuned_dither(gamma, contrast)) for name, gamma, contrast in DITHER_TUNINGS)

DITHER_NAMES = frozenset(name for name, _, _ in DITHER_TUNINGS)

CONVERSIONS = THRESHOLD_CONVERSIONS + DITHER_CONVERSIONS


def fit(coverage, box: int):
    """`coverage` cropped to its ink and scaled to fit `box`, as a bool array."""
    try:
        import numpy as np
        from PIL import Image
    except Exception:
        return None
    if coverage is None:
        return None
    rows = (coverage > 0).any(1).nonzero()[0]
    cols = (coverage > 0).any(0).nonzero()[0]
    if not len(rows) or not len(cols):
        return None
    ink = Image.fromarray(coverage[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1])
    scale = min(box / ink.width, box / ink.height)
    ink = ink.resize((max(1, round(ink.width * scale)),
                      max(1, round(ink.height * scale))), Image.LANCZOS)
    return np.array(ink) > 128


def reads_inverted(mask) -> bool:
    """True when `score()` will rate this mask's INVERSE rather than the mask.

    A majority-lit render is usually the same picture with the polarity
    flipped -- a white `>_` knocked out of a black terminal plate -- so the
    side carrying the shape is the minority one. `score()` has always done
    this; it is a named function so the SELECTION layer can ask the same
    question without a second copy of the condition (`app_icons.mark_rank`).

    ⚠️ Being inverted is NOT an error, and this is not a quality measure. It
    says only that the art is mostly ink and we are reading its holes -- which
    on a white-on-black keycap is exactly what "a big solid blob" looks like,
    and is why the caller prefers a candidate that did not need it.

    ⚠️ It CANNOT tell a dark plate from a filled silhouette, and no geometric
    measure can: measured 2026-09-23 over synthetic plates and silhouettes, a
    dark circular plate with a glyph knocked out (lit 0.723, enclosed 0.200)
    and a filled disc with a hole (lit 0.737, enclosed 0.158) are the SAME
    PICTURE, and si-safari sits between them at 0.727/0.188. An earlier idea --
    that a plate's inverse stays clear of the bounding-box border while a
    silhouette's does not -- was measured and REFUTED: 0.800 against 0.842 for
    that pair. Do not re-propose it.
    """
    import numpy as np                                      # noqa: F401
    if mask is None or not mask.size or not mask.any():
        return False
    return bool(float(mask.mean()) > MAX_LIT
                and _enclosed_share(mask) >= ENCLOSED_MIN)


def score(mask) -> float:
    """How legible this 1-bit render is. Higher is better; <= 0 is unusable.

    Two HARD rejections and four terms. Each arrived because a real icon defeated
    what was there before it:

    * **lit bounds** -- past `MAX_LIT` the render is a filled cell, below
      `MIN_LIT` the icon is gone;
    * **bbox fill** -- ink filling `MAX_FILL` of its own bounding box is a
      rectangle. This is what refuses a silhouette, and it replaced `detail`
      doing that job by accident (below);
    * **detail** -- the share of lit pixels touching an unlit one, at a QUARTER
      power. It is kept because it still orders two otherwise-equal readings, and
      weakened because at full strength it decided everything;
    * **survives** -- the variance of the 2x2 block means, divided by the
      variance a uniform field of the same density would have. ~1 for ink that is
      still ink after a blur, ~0 for a halftone that reads as grey;
    * **balance** -- prefers a healthy ink-to-ground ratio, zero `LIT_WIDTH`
      either side of `IDEAL_LIT`;
    * **spread** -- the share of ROWS and COLUMNS carrying any ink, which rejects
      a render made of thin fragments with an empty middle (Mousepad's).

    ⚠️ **`detail` used to be the first term at full strength and it was
    MAXIMISED BY TEXTURE** -- every lit pixel of a dither field touches an unlit
    one -- so the term meant to reward line art systematically handed the win to
    `dither`. Measured 2026-09-18 over the 235-icon Yaru set with 22 icons judged
    by eye: the old scorer picked the render a human would pick **8 times out of
    22**, and 13 of the 14 misses were "dither or luma won, adaptive was cleaner".
    This version picks it 16 times. On the 88 distinct arts in that set 23
    winners change: 17 better, 4 worse, 2 a wash.

    ⚠️ **Four repairs were measured and REFUTED before this one** -- do not
    re-propose them without new evidence:

    * a **detail ceiling** (peak at a moderate value, fall off toward 1.0). The
      highest-scoring render in the whole corpus, Power Statistics' dithered
      waveform, sits at detail 0.996; a ceiling destroys it;
    * **cohesion** (largest connected component's share). Refuted twice: it reads
      0.78-1.0 for halftone AND line art, and shipping it moved 37 winners while
      deflating the scale from 191 to 144 icons above the gate;
    * **stroke neighbourhood** (share of lit pixels with a lit 4-neighbour). Same
      wall: real dither reads 0.85-0.99, indistinguishable from line art. Only a
      perfect checkerboard reads 0, which is why testing it synthetically MISLEADS;
    * **bbox fill as a scoring TERM** rather than a rejection. It moved agreement
      DOWN (13 of 22 at best) -- it is a good yes/no and a bad dial.

    ⚠️ **The cost of `survives` is that sparse thin strokes score much lower**, a
    1px stroke and a dither field genuinely resembling each other at 2x2. GNOME
    System Monitor's clean trace went 0.34 -> 0.10 and the suite's `_line_art`
    fixture 0.32 -> 0.10. The ORDER is right in both cases -- they still win their
    icon -- but the bottom of the scale is compressed, which is why `MIN_SCORE`
    moved with it and now sits where the data separates rather than mid-range.

    ⚠️ Still a HEURISTIC fitted to judged icons, not a derived measure. Extend it
    by finding an icon it gets wrong and adding the term that separates it; do not
    tune the constants until a favourite icon passes.
    """
    if mask is None or not mask.size or not mask.any():
        return -1.0
    import numpy as np
    lit = float(mask.mean())
    if reads_inverted(mask):
        # A majority-lit render is the SAME PICTURE with the polarity flipped --
        # a white `>_` knocked out of a black terminal plate, not a filled cell.
        # Every term below reads ink as the minority, so measure the side that
        # carries the shape. `fidelity()` already takes the ABSOLUTE correlation
        # for exactly this reason; the gate was the half that still assumed a
        # light page. Measured over the 87 distinct Yaru arts: 9 winners change,
        # every one of them a dark-plate icon that had been rendering as a
        # fragment of its own lit background (bash and the root terminal drew a
        # bare `>`; Calls, Music and Snap Store drew their glyph in a noise
        # field), and the winning lit range opens from 0.055-0.623 to
        # 0.055-0.839 -- the top of which IS the plate.
        #
        # ⚠️ GATED ON AN ENCLOSED HOLE, because without it this readmits the one
        # thing `MAX_LIT` exists to refuse: a filled silhouette's inverse is the
        # page around it, which has structure of its own and scored 0.43 for a
        # FLAT DISC -- past `MIN_SCORE`, i.e. a confident offer to draw a blob on
        # the ESC keycap. See `_enclosed_share`.
        mask = ~mask
        lit = float(mask.mean())
    if lit > MAX_LIT or lit < MIN_LIT:
        return -1.0
    ink = int(mask.sum())
    rows = np.flatnonzero(mask.any(1))
    cols = np.flatnonzero(mask.any(0))
    box_area = (rows[-1] - rows[0] + 1) * (cols[-1] - cols[0] + 1)
    if ink >= MAX_FILL * box_area:
        return -1.0
    padded = np.pad(mask, 1)
    surrounded = (padded[:-2, 1:-1] & padded[2:, 1:-1]
                  & padded[1:-1, :-2] & padded[1:-1, 2:])
    detail = float((mask & ~surrounded).sum()) / ink
    height, width = mask.shape[0] // 2 * 2, mask.shape[1] // 2 * 2
    blocks = mask[:height, :width].reshape(height // 2, 2, width // 2, 2)
    survives = float(blocks.mean(axis=(1, 3)).var()) / (lit * (1.0 - lit))
    balance = max(0.0, 1.0 - abs(lit - IDEAL_LIT) / LIT_WIDTH)
    spread = min(float(mask.any(1).mean()), float(mask.any(0).mean()))
    return detail ** 0.25 * survives * balance * spread


def _source_ink(image, shape):
    """The SOURCE as an ink map at `shape` -- darkness = ink, cropped like a render."""
    import numpy as np
    from PIL import Image
    rgba = image.convert("RGBA")
    flat = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    flat.alpha_composite(rgba)
    # ⚠️ DISTANCE FROM THE PAGE, not darkness. Luma weights green x0.72 and blue
    # x0.07, so a saturated colour on white reads as almost nothing: GNOME
    # Calculator's yellow half measured 0.234 against its grey half's 0.623, i.e.
    # the reference said the right panel was very nearly blank -- so the render
    # that DROPPED that panel entirely scored 0.983 and shipped. Under this
    # reference the same panel reads 0.481. Euclidean distance in RGB is the
    # cheapest form that treats a bright colour as ink; it is not perceptual and
    # does not need to be, because only the RANKING of block means is used.
    rgb = np.asarray(flat.convert("RGB")).astype("float32") / 255.0
    ink = np.sqrt(((1.0 - rgb) ** 2).sum(axis=2)) / np.sqrt(3.0)
    ink = ink * (np.asarray(rgba.split()[-1]).astype("float32") / 255.0 > 0.35)
    rows = np.flatnonzero(ink.any(1))
    cols = np.flatnonzero(ink.any(0))
    if not len(rows) or not len(cols):
        return None
    crop = ink[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    small = Image.fromarray((crop * 255).astype("uint8")).resize(
        (shape[1], shape[0]), Image.LANCZOS)
    return np.asarray(small).astype("float32") / 255.0


def _enclosed_share(mask) -> float:
    """Share of the UNLIT pixels that are a HOLE in the ink, not the page around it.

    Floods the unlit region inward from the cell border; whatever the flood
    cannot reach is enclosed by ink. This is the one thing that separates a
    terminal plate with a `>_` knocked out of it -- which `score()` must read
    inverted -- from a filled silhouette, which it must still refuse. Both are
    majority-lit and neither lit fraction nor bounding-box fill tells them apart.
    """
    import numpy as np
    unlit = ~mask
    if not unlit.any():
        return 0.0
    reach = np.zeros_like(unlit)
    reach[0, :] |= unlit[0, :]
    reach[-1, :] |= unlit[-1, :]
    reach[:, 0] |= unlit[:, 0]
    reach[:, -1] |= unlit[:, -1]
    while True:
        grown = reach.copy()
        grown[1:, :] |= reach[:-1, :]
        grown[:-1, :] |= reach[1:, :]
        grown[:, 1:] |= reach[:, :-1]
        grown[:, :-1] |= reach[:, 1:]
        grown &= unlit
        if grown.sum() == reach.sum():
            break
        reach = grown
    return float((unlit & ~reach).sum()) / float(unlit.sum())


def _block_mean(field, size):
    height, width = field.shape
    tall, wide = height // size * size, width // size * size
    if tall < size or wide < size:
        return None
    return field[:tall, :wide].reshape(
        tall // size, size, wide // size, size).mean(axis=(1, 3))


def fidelity(mask, image, block: int = FIDELITY_BLOCK) -> float:
    """How well a render keeps the SOURCE's layout: |Pearson r| over coarse blocks.

    ⚠️ **`score()` never looks at the source.** Every one of its terms is a
    property of the mask alone, so it can say a render is crisp and cannot say it
    is the right picture -- which is why it preferred clean threshold line art
    while a human preferred the dither that kept the artwork's proportions.
    Measured over the 87 distinct Yaru arts: ranking by `score()` puts a dither
    first on 36, ranking by this puts one first on 65, with no thumb on the scale.

    ⚠️ **1 - MAE was the obvious form and is DEGENERATE -- do not go back to it.**
    Most icon sources are mostly light, so a BLANK render matches the mean and
    scores ~0.9; it picked an empty mask for baobab, empathy, engrampa and eog.
    Correlation is invariant to offset and scale, so a constant render has no
    variance and scores nothing at all. It asks only whether the ink goes WHERE
    the darkness is, which is the property being claimed.

    ⚠️ **ABSOLUTE value, because an inverted render is equally faithful in
    SHAPE.** A dark-plate icon (Terminal, Dictionary, Backups) reads correctly as
    light-on-dark or dark-on-light; both preserve the proportions, and the sign
    only records which way round the plate went. Signed correlation refuses seven
    of the 87 outright for that alone.

    ⚠️ **CORRELATION ALONE CANNOT SEE A DROPPED PANEL, which is why `coverage`
    multiplies it.** Correlation is invariant to scale, so a render that blanks a
    whole region still scores ~1 as long as what it DOES draw lines up with the
    source. GNOME Calculator is the worked example: `adaptive` renders the grey
    half perfectly and leaves the yellow half completely empty, and scored 0.983
    -- higher than every render that drew both halves. `coverage` asks the
    question correlation cannot, of the blocks the SOURCE fills, how many did the
    render put anything at all into; it takes Calculator's `adaptive` to 0.462
    against the dither's 0.648. Reported from hardware as "calc degraded as the
    right side became invisible".

    ⚠️ Coverage is measured on **whichever polarity correlated**, or it would
    refuse every dark-plate icon outright -- there the ink is deliberately where
    the source is light, so an unflipped coverage reads ~0 for a render that is
    entirely faithful.
    """
    import numpy as np
    if mask is None or not mask.size:
        return -1.0
    reference = _source_ink(image, mask.shape)
    if reference is None:
        return -1.0
    rendered = _block_mean(mask.astype("float32"), block)
    original = _block_mean(reference, block)
    if rendered is None or original is None:
        return -1.0
    centred = rendered.ravel() - rendered.mean()
    base = original.ravel() - original.mean()
    spread = float(np.sqrt((centred * centred).sum() * (base * base).sum()))
    if spread <= 1e-9:
        return -1.0
    correlation = float((centred * base).sum() / spread)
    drawn = (1.0 - rendered) if correlation < 0.0 else rendered
    inked = original >= COVERAGE_INK * float(original.max())
    if not inked.any():
        return abs(correlation)
    coverage = float((drawn[inked] > COVERAGE_MIN).mean())
    return abs(correlation) * coverage


def choose(image, box: int):
    """(mask, conversion name, score) for the best 1-bit reading of `image`.

    ⚠️ **TWO MEASURES, AND THEY ANSWER DIFFERENT QUESTIONS.** `score()` decides
    whether a render is USABLE -- a blob, a fragment field, a grey halftone are
    all refused -- and `fidelity()` decides which of the usable ones is the RIGHT
    PICTURE, by comparing it against the source. Everything clearing `MIN_SCORE`
    is ranked by fidelity; the best score is the fallback only when nothing does.

    ⚠️ **This replaced a hardcoded `DITHER_PREFERENCE` thumb (2026-09-18), and
    the thumb is the thing worth not rebuilding.** A dither was being forced to
    the front because a human kept preferring it, with a relative floor tuned
    until the count looked right. The real finding is that the dither preference
    was a SYMPTOM: `score()` was ranking crispness while the owner was ranking
    recognisability, so the fix is a measure that looks at the original rather
    than a constant that overrides the one that does not. With fidelity ranking,
    a dither wins 65 of 87 on its own merits and no constant decides it.

    Returns (None, None, -1.0) when nothing renders at all. A caller that wants
    only confident results compares the score against `MIN_SCORE`; one drawing a
    mark it has no alternative for may take whatever comes back.
    """
    candidates = []
    for name, convert in CONVERSIONS:
        mask = convert(image, box)
        value = score(mask)
        if value > -1.0:
            candidates.append((mask, name, value))
    if not candidates:
        return None, None, -1.0
    usable = [c for c in candidates if c[2] >= MIN_SCORE] or candidates
    return max(usable, key=lambda c: fidelity(c[0], image))


def looks_like_svg(data: bytes) -> bool:
    """True for SVG bytes, including a file that opens with an XML prologue.

    ⚠️ ONE definition. `app_icons.render_os_overlay` routes on it (Pillow
    cannot read SVG at all, and most of a Linux icon theme is SVG) and
    `shrink_for_transport` refuses to touch vector on the strength of it; a
    second copy that drifted would send one of them the wrong way.
    """
    head = (data or b"")[:512].lstrip()
    return head.startswith(b"<?xml") or head.startswith(b"<svg") or b"<svg" in head


def shrink_for_transport(data: bytes, max_px: int = TRANSPORT_MAX_PX) -> bytes:
    """`data`, re-encoded smaller when it is a raster icon bigger than `max_px`.

    The forwarder sends an app icon to the keyboard machine over the network,
    where it is reduced to a 38 px mark. A stock VS Code icon is 512x512 and
    measured 220 KB -- over the window-report endpoint's bounded-input cap, so
    the report was REFUSED and the mark never arrived. Shrinking at the sender
    fixes that at the source rather than by raising a cap whose whole purpose is
    to bound the one method reachable on the network.

    ⚠️ Deliberately NOT a binarisation. The receiver picks a conversion per icon
    (`choose`) and that scoring is still being tuned; converting here would
    freeze every forwarded app at the SENDER's version of it, and the two
    machines need not even run the same release. Resolution is the redundant
    part; the reading is not.

    ⚠️ SVG is returned untouched. It is text, already small, and rasterising it
    here would throw away the vector path that is the difference between the
    Linux backend working and scoring -1.00 on nearly everything.

    ⚠️ An ICO/ICNS is FLATTENED to its largest frame when it is over-size, which
    is exactly what the receiver picks anyway. Under the limit it is passed
    through, so nothing re-encodes without reason.

    Never raises: returns the original bytes if anything at all goes wrong. A
    cosmetic feature must not break window reporting.
    """
    if not data or looks_like_svg(data):
        return data
    try:
        import io as _io

        from PIL import Image

        image = Image.open(_io.BytesIO(data))
        # ⚠️ No frame selection here. Pillow already reports a multi-frame
        # .ico/.icns AT ITS LARGEST frame -- measured, a 3-frame ICO opens at
        # 256 and an 8-entry ICNS at 1024 -- so the `image.size = max(sizes)`
        # this used to copy from `app_icons` was a no-op for ICO and BROKE
        # ICNS: its `sizes` entries are 3-tuples (w, h, scale), and assigning
        # one made the decode raise, so the fallback returned the icon
        # unshrunk. A 4.1 MB .icns then crossed the wire and the endpoint
        # refused it -- the reported bug, on the other platform.
        image.load()
        if max(image.size) <= max_px:
            return data
        image = image.convert("RGBA")
        image.thumbnail((max_px, max_px), Image.LANCZOS)
        out = _io.BytesIO()
        image.save(out, format="PNG")
        # ⚠️ Returned even on the rare occasion it is BIGGER in bytes. A smooth
        # 256x256 icon can encode to 1.5 KB and re-encode to more, and keeping
        # the original there was tried -- but it leaves the PIXEL count
        # unbounded, and pixels are what the receiver has to decode. Bounding
        # the raster is the invariant worth having; at these scales both forms
        # are far under the endpoint's byte cap, so the trade costs nothing.
        return out.getvalue()
    except Exception:
        log.debug("Could not shrink a %d-byte icon for transport; sending as-is",
                  len(data), exc_info=True)
        return data
