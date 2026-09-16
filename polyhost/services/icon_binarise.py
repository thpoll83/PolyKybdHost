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
MAX_LIT = 0.80
MIN_LIT = 0.04

# The lit fraction a legible keycap icon tends to have. Scoring peaks here and
# falls off either side, so a candidate that is merely *inside* the bounds above
# still loses to one with a healthier balance of ink to ground.
IDEAL_LIT = 0.35

# Below this, `choose()` has found nothing worth drawing. A wrong or unreadable
# mark is worse than none -- the user cannot tell a bad render from a bug.
#
# ⚠️ The value is taken from where the DATA separates, not chosen: over the
# seven reference icons the one unreadable render (LibreOffice Draw, a smooth
# gradient with no two-tone structure) scores 0.174 while the WORST legible one
# scores 0.426. Anything in that gap rejects exactly the blob. Re-derive it from
# the histogram rather than nudging it if a new icon lands in between -- a floor
# tuned until a particular icon passes stops meaning anything.
MIN_SCORE = 0.30


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


# The pre-dither adjustments `dither_ink` runs. ⚠️ NOT optional decoration --
# bare Floyd-Steinberg on an app icon is unreadable noise at this size, AND it
# games `score()`, because every isolated pixel of a dithered midtone counts as
# an edge. Normalise + unsharp + contrast is what removes the scatter, and it is
# the stage fontconvert itself always pairs with the dither.
DITHER_ADJUST = dict(normalize=True, sharpness=2.5, contrast=2.5)


def dither_ink(image, box: int):
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
    fd.apply_adjustments(small, fd.DitherOpts(**DITHER_ADJUST))
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
CONVERSIONS = (
    ("alpha", _thresholded(alpha_coverage)),
    ("luma", _thresholded(luma_ink)),
    ("adaptive", _thresholded(adaptive_ink)),
    ("dither", dither_ink),
)


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


def score(mask) -> float:
    """How legible this 1-bit render is. Higher is better; <= 0 is unusable.

    Three terms, each added because a real icon defeated the ones before it:

    * **edge** -- the share of lit pixels touching an unlit one. A solid shape
      scores near zero however large it is, which is what rejects a silhouette
      (Yelp's help icon reduces to a ring, gedit's to a diagonal bar);
    * **balance** -- prefers a healthy ink-to-ground ratio over one extreme;
    * **spread** -- the share of ROWS and COLUMNS carrying any ink. Without it
      a render made of thin fragments scores *well*, because `edges/lit`
      approaches 1.0 for anything thin: Mousepad's icon reduced to a band of
      text at the top and a rule at the bottom, 12% lit with an empty middle,
      and scored 0.55 until this term took it to 0.14.

    ⚠️ This is a HEURISTIC fitted to roughly a dozen real icons, not a derived
    measure, and it should be read as one. It is a filter on the obvious
    failures -- blob, silhouette, fragments -- and not a judge of whether a mark
    is recognisable. Extend it by finding an icon it gets wrong and adding the
    term that separates it, the way each of these three arrived; do not tune the
    constants until a favourite icon passes.
    """
    if mask is None or not mask.size:
        return -1.0
    import numpy as np
    lit = float(mask.mean())
    if lit > MAX_LIT or lit < MIN_LIT:
        return -1.0
    padded = np.pad(mask, 1)
    surrounded = (padded[:-2, 1:-1] & padded[2:, 1:-1]
                  & padded[1:-1, :-2] & padded[1:-1, 2:])
    edges = mask & ~(mask & surrounded)
    detail = float(edges.sum()) / max(1, int(mask.sum()))
    balance = 1.0 - abs(lit - IDEAL_LIT)
    spread = min(float(mask.any(1).mean()), float(mask.any(0).mean()))
    return detail * balance * spread


def choose(image, box: int):
    """(mask, conversion name, score) for the best 1-bit reading of `image`.

    Returns (None, None, -1.0) when nothing renders at all. A caller that wants
    only confident results compares the score against `MIN_SCORE`; one drawing a
    mark it has no alternative for may take whatever comes back.
    """
    best = (None, None, -1.0)
    for name, convert in CONVERSIONS:
        mask = convert(image, box)
        value = score(mask)
        if value > best[2]:
            best = (mask, name, value)
    return best
