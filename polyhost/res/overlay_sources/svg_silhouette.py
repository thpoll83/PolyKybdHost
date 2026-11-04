"""An icon's SVG as the silhouette the icon picker and the fetch scripts shade.

`silhouette(spec)` renders a "source:name" SVG (the SOURCES of
cnc_remastered/fetch_icons.py: Font Awesome, Material Design Icons,
game-icons.net) at 512 px, crops it to the shape and scales its alpha so the
longest side is PX. tools/gen_icon_picker.py embeds exactly this in the page,
and a fetch script re-rasterizing a picked icon starts from it, so both draw
the same pixels.
"""
from __future__ import annotations

import io

import numpy as np

PX = 128


def silhouette(spec: str, px: int = PX) -> np.ndarray:
    import cairosvg
    from PIL import Image

    from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc
    src, name = spec.split(":", 1)
    png = cairosvg.svg2png(bytestring=cnc._get(cnc.SOURCES[src].format(name)), output_width=512, output_height=512)
    alpha = Image.open(io.BytesIO(png)).convert("RGBA").getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    k = px / max(alpha.size)
    return np.asarray(alpha.resize((max(1, round(alpha.width * k)), max(1, round(alpha.height * k))), Image.LANCZOS))
