#!/usr/bin/env python3
"""Round-3 faithful preview: every glyph now resolves through gfx_font (the 5/8
new resident glyphs were injected into gfx_icons.h), so this renders exactly what
the firmware draws, including the Win+R frame at its new (3px-lower) position.
Run from the PolyKybdHost repo root."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from gfx_font import GfxGlyphRenderer, OLED_W, OLED_H, BUFFER_X
from PIL import Image, ImageDraw, ImageFont
FONTDIR = os.environ.get("POLYKYBD_FONTS", os.path.abspath(os.path.join(
    os.path.dirname(__file__), "../../qmk_firmware/keyboards/polykybd/base/fonts")))
OUT = os.environ.get("POLYKYBD_OUT", tempfile.gettempdir())
R = GfxGlyphRenderer(FONTDIR)
SP = 0x20


def cell(cps, nsp):
    img = Image.new("L", (OLED_W, OLED_H), 0); px = img.load(); x = BUFFER_X
    for cp in [SP]*nsp + cps:
        x = R._blit(px, cp, x)
    return img


def frame_R():
    img = cell([0x9A, 0x9B], 5)            # prompt glyphs already +3px in the header
    d = ImageDraw.Draw(img)                # firmware: round_rect(62,7,36,32,4)+(63,8,34,30,3) in buffer coords
    d.rounded_rectangle([34, 7, 69, 38], radius=4, outline=255)   # -28 on x -> preview coords
    d.rounded_rectangle([35, 8, 68, 37], radius=3, outline=255)
    return img


# (label, action, cell-image)
items = [
    ("Win+A",            "⚡ lightning",          cell([0x26A1], 6)),
    ("Win+E",            "Explorer folder",       cell([0x9C], 4)),
    ("Win+R",            "prompt + frame, 3px down", frame_R()),
    ("Win+Left",         "snap-left (tall bar)",  cell([0xA2], 6)),
    ("Win+Right",        "snap-right (tall bar)", cell([0xA3], 6)),
    ("Win+Ctrl+D",       "🖵+ new desktop",       cell([0xA1, ord('+')], 4)),
    ("Win+Ctrl+Left",    "←🖵 prev desktop",      cell([0x83, 0xA1], 5)),
    ("Win+Ctrl+Right",   "🖵→ next desktop",      cell([0xA1, 0x84], 5)),
    ("Win+Ctrl+F4",      "🖵x close desktop",     cell([0xA1, ord('x')], 4)),
    ("Win+Ctrl+Shift+B", "☠ restart graphics",   cell([0x2620], 5)),
    ("Win+Ctrl+F",       "🖧 networked computers",cell([0x9D], 5)),
    ("Win+1",            "📌1 small pin",         cell([0x9E, ord('1')], 6)),
    ("Win+5",            "📌5 small pin",         cell([0x9E, ord('5')], 6)),
    ("Win+B",            "🔔 system tray",        cell([0x1F514], 3)),
    ("Win+Plus",         "🔍 + in lens",          cell([0x9F], 6)),
    ("Win+Minus",        "🔍 − in lens",          cell([0xA0], 6)),
]

scale = 5; cw, ch = OLED_W*scale, OLED_H*scale; lab = 30; cols = 3; pad = 10
rows = (len(items)+cols-1)//cols
W = cols*(cw+pad)+pad; H = rows*(ch+lab+pad)+pad
sh = Image.new("RGB", (W, H), (24, 24, 24)); dr = ImageDraw.Draw(sh)
try:
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
except Exception:
    f = sub = ImageFont.load_default()
for i, (label, action, im) in enumerate(items):
    r, c = divmod(i, cols)
    ox = pad + c*(cw+pad); oy = pad + r*(ch+lab+pad)
    sh.paste(im.convert("RGB").resize((cw, ch), Image.NEAREST), (ox, oy))
    dr.rectangle([ox, oy, ox+cw-1, oy+ch-1], outline=(80, 80, 80))
    dr.text((ox+2, oy+ch+1), label, fill=(255, 230, 120), font=f)
    dr.text((ox+2, oy+ch+16), action, fill=(170, 170, 170), font=sub)
out = os.path.join(OUT, "win_hints_v3.png")
sh.save(out); print("wrote", out, sh.size)
