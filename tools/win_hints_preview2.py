#!/usr/bin/env python3
"""Round-2 preview for the Windows shortcut-hint revisions. Renders the firmware
hints (shipped glyphs via tools/gfx_font.py) plus, for glyphs not yet in the
firmware fonts, faithful approximations: the Explorer folder pixmap (from the
overlay icon PNG), the 🖧 networked-computers glyph (from the Noto source TTF),
and the magnifier-with-sign composites. Produces two contact sheets:
proposed_v2.png and alternatives_v2.png. Run from the PolyKybdHost repo root."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from gfx_font import GfxGlyphRenderer, OLED_W, OLED_H, BUFFER_X
from PIL import Image, ImageDraw, ImageFont

FW = "/home/user/qmk_firmware/keyboards/polykybd"
R = GfxGlyphRenderer(FW + "/base/fonts")
SP = 0x20
SYM2 = FW + "/fonts/Noto_Sans_Symbols_2/NotoSansSymbols2-Regular.ttf"
EXPLORER_PNG = "polyhost/res/overlay_sources/explorer/icons/explorer.png"


def cell_glyphs(cps):
    """Render a leading-space + glyph string the firmware way; auto-pick spaces."""
    best = fallback = None
    for nsp in range(0, 7):
        img = Image.new("L", (OLED_W, OLED_H), 0); px = img.load(); x = BUFFER_X
        for cp in [SP]*nsp + cps:
            x = R._blit(px, cp, x)
        pts = [(xx, yy) for yy in range(OLED_H) for xx in range(OLED_W) if px[xx, yy]]
        if not pts: continue
        xs = [p[0] for p in pts]; mn, mx = min(xs), max(xs)
        if not (mx >= 71 or mn <= 0): best = (img, (mn, mx))
        if fallback is None or mx < fallback[1][1]: fallback = (img, (mn, mx))
    return best or fallback or (Image.new("L", (OLED_W, OLED_H), 0), (28, 28))


def frame(img, box, dy=0):
    """2px rounded-rect outline hugging box; dy shifts it up (negative)."""
    mn, mx = box; d = ImageDraw.Draw(img)
    x0, x1, y0, y1 = mn-3, mx+3, 2+dy, OLED_H-5+dy
    for t in range(2):
        d.rounded_rectangle([x0-t, y0-t, x1+t, y1+t], radius=4, outline=255)
    return img


def cell_ttf(cp, target_h=30, right=66):
    """Rasterise one codepoint from the Noto source TTF, threshold to 1-bit, drop
    it into the 72x40 cell right-of-centre (approximates the generated glyph)."""
    big = ImageFont.truetype(SYM2, 64)
    tmp = Image.new("L", (96, 96), 0)
    ImageDraw.Draw(tmp).text((10, 10), chr(cp), fill=255, font=big)
    bb = tmp.getbbox()
    if not bb: return Image.new("L", (OLED_W, OLED_H), 0)
    g = tmp.crop(bb)
    g = g.point(lambda v: 255 if v >= 110 else 0)
    scale = target_h / g.height
    g = g.resize((max(1, round(g.width*scale)), target_h), Image.NEAREST)
    g = g.point(lambda v: 255 if v >= 110 else 0)
    out = Image.new("L", (OLED_W, OLED_H), 0)
    out.paste(g, (right - g.width, (OLED_H - g.height)//2))
    return out


def cell_png(path, target_h=32, right=66):
    im = Image.open(path).convert("RGBA")
    bgw = Image.new("L", im.size, 0)
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            bgw.putpixel((x, y), 255 if (a > 40 and (r+g+b)/3 > 90) else 0)
    bb = bgw.getbbox() or (0, 0, im.width, im.height)
    g = bgw.crop(bb)
    scale = target_h / g.height
    g = g.resize((max(1, round(g.width*scale)), target_h), Image.NEAREST).point(lambda v: 255 if v >= 110 else 0)
    out = Image.new("L", (OLED_W, OLED_H), 0)
    out.paste(g, (right - g.width, (OLED_H - g.height)//2))
    return out


def cell_mag(sign):
    """Magnifier (🔍 1F50D) with a + or - drawn inside the lens (approx of the
    custom glyph to be injected)."""
    img, box = cell_glyphs([0x1F50D])
    mn, mx = box
    # lens of 1F50D is the upper-left disc; sign goes near its centre
    cx, cy = mn + (mx-mn)//2 - 3, OLED_H//2 - 4
    d = ImageDraw.Draw(img)
    d.line([cx-4, cy, cx+4, cy], fill=255, width=2)
    if sign == "+":
        d.line([cx, cy-4, cx, cy+4], fill=255, width=2)
    return img


def sheet(entries, out, cols=3, scale=5, title=None):
    cw, ch = OLED_W*scale, OLED_H*scale
    lab = 32; pad = 10
    rows = (len(entries)+cols-1)//cols
    top = 28 if title else 0
    W = cols*(cw+pad)+pad
    H = rows*(ch+lab+pad)+pad+top
    sh = Image.new("RGB", (W, H), (24, 24, 24)); dr = ImageDraw.Draw(sh)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
        sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except Exception:
        f = sub = ImageFont.load_default()
    if title:
        dr.text((pad, 6), title, fill=(120, 220, 255), font=f)
    for i, (label, action, cell) in enumerate(entries):
        r, c = divmod(i, cols)
        ox = pad + c*(cw+pad); oy = top + pad + r*(ch+lab+pad)
        sh.paste(cell.convert("RGB").resize((cw, ch), Image.NEAREST), (ox, oy))
        dr.rectangle([ox, oy, ox+cw-1, oy+ch-1], outline=(80, 80, 80))
        dr.text((ox+2, oy+ch+1), label, fill=(255, 230, 120), font=f)
        dr.text((ox+2, oy+ch+16), action, fill=(170, 170, 170), font=sub)
    sh.save(out)
    print("wrote", out, sh.size)


# ---- decided / proposed revisions -----------------------------------------
rcell, rbox = cell_glyphs([0x9A, 0x9B])
proposed = [
    ("Win+A",          "⚡ (was bell)",          cell_glyphs([0x26A1])[0]),
    ("Win+E",          "Explorer folder pixmap", cell_png(EXPLORER_PNG)),
    ("Win+R",          "frame moved 2px up",     frame(rcell.copy(), rbox, dy=-2)),
    ("Win+Left",       "⭰ snap-to-edge",         cell_glyphs([0x2B70])[0]),
    ("Win+Right",      "⭲ snap-to-edge",         cell_glyphs([0x2B72])[0]),
    ("Win+Ctrl+D",     "🖵+ new desktop",        cell_glyphs([0x1F5B5, ord('+')])[0]),
    ("Win+Ctrl+Left",  "←🖵 prev desktop",       cell_glyphs([0x83, 0x1F5B5])[0]),
    ("Win+Ctrl+Right", "🖵→ next desktop",       cell_glyphs([0x1F5B5, 0x84])[0]),
    ("Win+Ctrl+F4",    "🖵x close desktop",      cell_glyphs([0x1F5B5, ord('x')])[0]),
    ("Win+Ctrl+Shift+B","☠ restart graphics",    cell_glyphs([0x2620])[0]),
    ("Win+Ctrl+F",     "🖧 networked computers", cell_ttf(0x1F5A7)),
    ("Win+1",          "📌1 (native pin)",       cell_glyphs([0x1F4CC, ord('1')])[0]),
    ("Win+5",          "📌5 (native pin)",       cell_glyphs([0x1F4CC, ord('5')])[0]),
    ("Win+Plus",       "🔍 with + in lens",      cell_mag("+")),
    ("Win+Minus",      "🔍 with − in lens",      cell_mag("-")),
]
sheet(proposed, "/tmp/claude-0/-home-user/b1c7a410-51de-5f9e-b52a-703d37ab2f61/scratchpad/proposed_v2.png",
      title="PROPOSED revisions (Explorer/🖧/magnifier are approximations of glyphs to be generated)")

# ---- alternatives for the open items ---------------------------------------
alts = [
    ("Win+Home  A", "❐ keep-one (current)",  cell_glyphs([0x2750])[0]),
    ("Win+Home  B", "🗗 minimize window",     cell_glyphs([0x1F5D7])[0]),
    ("Win+Home  C", "❒ shadowed window",     cell_glyphs([0x2752])[0]),
    ("Win+Home  D", "🗕→🗗 (maximize one)",    cell_glyphs([0x1F5D6])[0]),
    ("Win+;  A",    "📽 projector (current)",  cell_glyphs([0x1F4FD])[0]),
    ("Win+;  B",    "🎬 clapper / movie",      cell_glyphs([0x1F3AC])[0]),
    ("Win+;  C",    "📹 video camera",         cell_glyphs([0x1F4F9])[0]),
    ("Win+Shift+S A","✄ white scissors (cur)", cell_glyphs([0x2704])[0]),
    ("Win+Shift+S B","✂ scissors",             cell_glyphs([0x2702])[0]),
    ("Win+Shift+S C","📷 camera (capture)",     cell_glyphs([0x1F4F7])[0]),
    ("Win+B  A",    "🔔 bell (now free)",      cell_glyphs([0x1F514])[0]),
    ("Win+B  B",    "🔊 speaker (tray)",       cell_glyphs([0x1F50A])[0]),
    ("Win+B  C",    "▲ up (corner)",          cell_glyphs([0x81])[0]),
]
sheet(alts, "/tmp/claude-0/-home-user/b1c7a410-51de-5f9e-b52a-703d37ab2f61/scratchpad/alternatives_v2.png",
      title="ALTERNATIVES — pick one each for Win+Home, Win+;, Win+Shift+S, Win+B")
