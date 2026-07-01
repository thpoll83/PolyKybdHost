#!/usr/bin/env python3
"""Full overview of every Windows (GUI/Super) keycap shortcut-hint the firmware
draws, rendered faithfully from the generated GFX headers (exact glyphs, exact
leading spaces, and the Win+R rounded frame). Grouped by modifier chord.
Run from the PolyKybdHost repo root."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from gfx_font import GfxGlyphRenderer, OLED_W, OLED_H, BUFFER_X
from PIL import Image, ImageDraw, ImageFont
R = GfxGlyphRenderer("/home/user/qmk_firmware/keyboards/polykybd/base/fonts")
SP = 0x20

# section title -> list of (label, action, [codepoints], leading-spaces, frame?)
SECTIONS = [
    ("Win + <key>", [
        ("Win+A", "Action Center",        [0x26A1], 6, False),
        ("Win+B", "System tray",          [0x1F50A], 3, False),
        ("Win+D", "Show desktop",         [0x1F5B3], 4, False),
        ("Win+E", "File Explorer",        [0x9C], 4, False),
        ("Win+H", "Dictation",            [0x1F5E3], 3, False),
        ("Win+I", "Settings",             [0x2699], 3, False),
        ("Win+K", "Cast",                 [0x1F4F6], 3, False),
        ("Win+L", "Lock",                 [0x1F512], 4, False),
        ("Win+M", "Minimize all",         [0x1F5D7], 5, False),
        ("Win+P", "Display / project",    [0x1F5B5], 4, False),
        ("Win+R", "Run dialog",           [0x9A, 0x9B], 5, True),
        ("Win+S", "Search",               [0x2630], 3, False),
        ("Win+T", "Cycle taskbar",        [0x1F504], 3, False),
        ("Win+U", "Accessibility",        [0x267F], 6, False),
        ("Win+V", "Clipboard history",    [0x1F4DC], 3, False),
        ("Win+X", "Quick-link menu",      [0x1F4D1], 4, False),
        ("Win+,", "Peek desktop",         [0x1F441], 3, False),
        ("Win+.", "Emoji panel",          [0x1F600], 3, False),
        ("Win+;", "GIF panel",            [0x1F3AC], 3, False),
        ("Win+Home",  "Minimize others",  [0x2752], 5, False),
        ("Win+Left",  "Snap left",        [0xA1], 6, False),
        ("Win+Right", "Snap right",       [0xA2], 6, False),
        ("Win+Up",    "Maximize",         [0x1F5D6], 5, False),
        ("Win+Down",  "Minimize",         [0x1F5D7], 5, False),
        ("Win+Tab",   "Task view",        [0x1F5BD], 4, False),
        ("Win+Pause", "System properties",[0x1F4BB], 3, False),
        ("Win+PrtScn","Screenshot",       [0x1F4F8], 3, False),
        ("Win + +",   "Magnifier in",     [0x9F], 6, False),
        ("Win + -",   "Magnifier out",    [0xA0], 6, False),
        ("Win+1..9",  "Taskbar app N",    [0x9E, ord('1')], 6, False),
    ]),
    ("Win + Ctrl (virtual desktops + network)", [
        ("Win+Ctrl+D",     "New desktop",   [0x1F5B5, ord('+')], 2, False),
        ("Win+Ctrl+Left",  "Prev desktop",  [0x83, 0x1F5B5], 2, False),
        ("Win+Ctrl+Right", "Next desktop",  [0x1F5B5, 0x84], 2, False),
        ("Win+Ctrl+F4",    "Close desktop", [0x1F5B5, ord('x')], 2, False),
        ("Win+Ctrl+F",     "Search network",[0x9D], 5, False),
    ]),
    ("Win + Ctrl + Shift  /  Win + Alt  /  Win + Shift", [
        ("Win+Ctrl+Shift+B", "Restart graphics", [0x2620], 5, False),
        ("Win+Alt+R",        "Screen recording", [0x1F4F9], 3, False),
        ("Win+Shift+S",      "Snipping Tool",    [0x1F4F7], 3, False),
    ]),
]


def cell(cps, nsp, frame):
    img = Image.new("L", (OLED_W, OLED_H), 0); px = img.load(); x = BUFFER_X
    for cp in [SP]*nsp + cps:
        x = R._blit(px, cp, x)
    if frame:                                  # Win+R: buffer(62,7,36,32)+(63,8,34,30) -> preview -28 on x
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([34, 7, 69, 38], radius=4, outline=255)
        d.rounded_rectangle([35, 8, 68, 37], radius=3, outline=255)
    return img


scale = 4
cw, ch = OLED_W*scale, OLED_H*scale
lab = 26; cols = 6; pad = 8; hdr = 30
try:
    hf = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    lf = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
    sf = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
except Exception:
    hf = lf = sf = ImageFont.load_default()

# compute total height
rowh = ch + lab + pad
H = pad
for title, items in SECTIONS:
    rows = (len(items)+cols-1)//cols
    H += hdr + rows*rowh + pad
W = cols*(cw+pad)+pad
sheet = Image.new("RGB", (W, H), (18, 18, 18))
dr = ImageDraw.Draw(sheet)

y = pad
for title, items in SECTIONS:
    dr.text((pad, y+4), title, fill=(120, 220, 255), font=hf)
    y += hdr
    for i, (label, action, cps, nsp, frame) in enumerate(items):
        r, c = divmod(i, cols)
        ox = pad + c*(cw+pad); oy = y + r*rowh
        im = cell(cps, nsp, frame)
        sheet.paste(im.convert("RGB").resize((cw, ch), Image.NEAREST), (ox, oy))
        dr.rectangle([ox, oy, ox+cw-1, oy+ch-1], outline=(80, 80, 80))
        dr.text((ox+2, oy+ch+1), label, fill=(255, 230, 120), font=lf)
        dr.text((ox+2, oy+ch+13), action, fill=(165, 165, 165), font=sf)
    rows = (len(items)+cols-1)//cols
    y += rows*rowh + pad

out = "/tmp/claude-0/-home-user/b1c7a410-51de-5f9e-b52a-703d37ab2f61/scratchpad/win_hints_overview.png"
sheet.save(out)
n = sum(len(it) for _, it in SECTIONS)
print(f"wrote {out} {sheet.size}  ({n} hints)")
