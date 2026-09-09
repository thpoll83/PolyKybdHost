"""The split72 status OLED, as the editor's board plate draws it.

A PORT of the firmware's own preview tool —
`qmk_firmware/keyboards/polykybd/tools/status_oled_preview.py`, which is itself a
mirror of `split72/status_oled.c` `oled_update_buffer()`. Same coordinates, same
helpers, same names, so the two files diff against each other line for line. Only
two things change: the glyph access (host `PackFont` objects rather than the tool's
parsed-header tuples) and the fact that the layer and the layout name are arguments
rather than fixtures.

⚠️ **A port drifts, and nothing here can see the firmware move.** So it is pinned to
a GOLDEN FIXTURE — `tests/services/status_panel_golden.json`, generated from the
firmware tool by `scripts/gen_status_panel_golden.py` and compared pixel for pixel by
`tests/services/status_screen_test.py`. That test runs with no checkout, so the port
cannot drift from what the firmware drew when the fixture was taken; a second,
checkout-gated test re-derives the fixture live, so a firmware change is caught on the
machine that made it. Regenerate the fixture whenever `status_oled.c` moves a row.

⚠️ **Everything except the layer and the layout name is a REPRESENTATIVE VALUE.** The
RGB effect, WPM, brightness and language are live device state the editor does not
have; the panel shows the firmware's own placeholders so the picture reads as the
screen it is, rather than as a mostly-dark subset. They are not measurements of
anything — do not wire a UI readout to them.
"""

from __future__ import annotations

PANEL_W, PANEL_H = 128, 64

# ---- coordinates, kept in sync with split72/status_oled.c oled_update_buffer ----
TOP_BASE = 15         # first text line (layer icon / hex layer / role)
LOCK_ROW_B = 29       # layout name
LOCK_ROW_C = 48       # speed + language
LOCK_ROW_D = 63       # brightness
RGB_ROW_B = 30        # effect index + name
RGB_ROW_C = 45        # colour name + hue
RGB_ROW_D = 63        # saturation + value
# RGB-off re-flow: three rows on both panels instead of four, bottomed out on 63.
CAPS_LOCK_BASE = 43
SIDE_MARKER_BASE = 63
OFF_ROW_B, OFF_ROW_C = 37, 63
RGB_OFF_ROW_B, RGB_OFF_ROW_C = 39, 63
OFF_GLOBE_Y, OFF_CODE1_BASE, OFF_CODE2_BASE = 1, 31, 43

ICON_LAYER = 0x80
ICON_NUMLOCK_OFF, ICON_CAPSLOCK_OFF = 0x8C, 0x8E

#: The indicator column both panels reserve on their inner edge, and the RGB speed
#: gauge drawn in it (Num Lock top .. Caps Lock bottom).
COL_W = 17
SPEED_BOX_Y, SPEED_BOX_W, SPEED_BOX_H = 0, COL_W, 44
SPEED_FILL_W = SPEED_BOX_W - 6
SPEED_FILL_BOTTOM = SPEED_BOX_Y + SPEED_BOX_H - 4
SPEED_FILL_H = SPEED_BOX_H - 6

#: Brightness gauge (GAUGE_* mirror status_oled.c; FULL_BRIGHT mirrors config.h).
GAUGE_SEGMENTS, GAUGE_BAR_W, GAUGE_PITCH, GAUGE_MIN_H = 10, 4, 6, 3
FULL_BRIGHT = 50

#: Small MSB-first bitmaps the panel draws directly, out of status_oled.c.
SUN_BMP = [0x04, 0x00, 0x44, 0x40, 0x20, 0x80, 0x0e, 0x00, 0x1f, 0x00, 0xdf, 0x60,
           0x1f, 0x00, 0x0e, 0x00, 0x20, 0x80, 0x44, 0x40, 0x04, 0x00]
SUN_W = SUN_H = 11
GLOBE_BMP = [0x0f, 0x80, 0x38, 0xe0, 0x68, 0xb0, 0x48, 0x90, 0x90, 0x48, 0x90, 0x48,
             0xff, 0xf8, 0x90, 0x48, 0x90, 0x48, 0x48, 0x90, 0x68, 0xb0, 0x38, 0xe0,
             0x0f, 0x80]
GLOBE_W = GLOBE_H = 13
WPM_BMP = [0x1f, 0x00, 0x71, 0xc0, 0x43, 0x40, 0xc2, 0x60, 0x86, 0x20, 0x8e, 0x20]
WPM_ICON_W, WPM_ICON_H = 11, 6
DEGREE_BMP = [0xe0, 0xa0, 0xe0]
DEGREE_W = DEGREE_H = 3
SUPER2_BMP = [0x70, 0x88, 0x10, 0x20, 0x40, 0xf8]
SUPER2_W, SUPER2_H = 5, 6
DROPLET_BMP = [0x08, 0x00, 0x08, 0x00, 0x1c, 0x00, 0x1c, 0x00, 0x3e, 0x00,
               0x7f, 0x00, 0x7f, 0x00, 0x7f, 0x00, 0x3e, 0x00, 0x1c, 0x00]
DROPLET_W, DROPLET_H, DROPLET_Y = 9, 10, 53
SUN_SMALL_BMP = [0x08, 0x00, 0x41, 0x00, 0x1c, 0x00, 0x3e, 0x00, 0xbe, 0x80,
                 0x3e, 0x00, 0x1c, 0x00, 0x41, 0x00, 0x08, 0x00]
SUN_SMALL_W, SUN_SMALL_H, SUN_SMALL_Y = 9, 9, 54
SV_ICON_GAP = 2

#: Top-row role icons (16x16, MSB-first) — status_oled.c usb_/link_status_bitmap.
USB_BMP = [0x00, 0x80, 0x01, 0xc0, 0x01, 0xc0, 0x03, 0xe0, 0x03, 0xe0, 0x00, 0x80,
           0x00, 0xb8, 0x04, 0xb8, 0x0e, 0xb8, 0x0e, 0x90, 0x04, 0xe0, 0x03, 0x80,
           0x00, 0x80, 0x01, 0xc0, 0x03, 0x60, 0x01, 0xc0]
LINK_BMP = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x18, 0x00, 0x1c, 0x7f, 0xfe,
            0x7f, 0xfe, 0x00, 0x00, 0x00, 0x00, 0x7f, 0xfe, 0x7f, 0xfe, 0x38, 0x00,
            0x18, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

#: What the editor cannot know. See the module docstring: representative, not measured.
DEFAULT_BRIGHTNESS = 50
DEFAULT_RGB = (128, 255, 100, 80, 5, "Rainbow")   # hue, sat, val, speed, mode, name
DEFAULT_LANG = "en-US"
DEFAULT_WPM = 0


def _glyph(font, cp):
    """The glyph record for `cp`, or None — the range guard `draw()` needs.

    Out of range is SKIPPED rather than substituted, exactly as the firmware's
    `draw()` does: a missing glyph must not shift everything after it, and on the
    tool side indexing past the array would wrap negative.
    """
    if font is None or not (font.first <= cp <= font.last):
        return None
    return font.glyphs[cp - font.first]


def draw(setpix, font, x, y, text):
    """Codepoints at (x, baseline y), COLUMN-NATIVE — mirror of the firmware `draw()`.

    1 byte = 8 VERTICAL pixels, `cb` bytes per column, LSB = top of the page. Reading
    it row-major produces something that looks like dither noise rather than an error.
    """
    if font is None:
        return
    for cp in text:
        g = _glyph(font, cp)
        if g is None:
            continue
        cb = (g["height"] + 7) >> 3
        for gx in range(g["width"]):
            col = g["bitmapOffset"] + gx * cb
            for gy in range(g["height"]):
                if font.bitmap[col + (gy >> 3)] & (1 << (gy & 7)):
                    setpix(x + g["xOffset"] + gx, y + g["yOffset"] + gy)
        x += g["xAdvance"]


def draw_glyph_half(setpix, font, x, y, cp):
    """2x2-OR downsample at a literal top-left — kdisp_draw_glyph_half_at().

    No baseline or yOffset math: (x, y) is the top-left of the halved ink. OR rather
    than decimation, because decimation drops the thin strokes.
    """
    g = _glyph(font, cp)
    if g is None:
        return
    w, h = g["width"], g["height"]
    cb = (h + 7) >> 3
    for dy in range((h + 1) // 2):
        for dx in range((w + 1) // 2):
            for oy in range(2):
                for ox in range(2):
                    sx, sy = dx * 2 + ox, dy * 2 + oy
                    if sx >= w or sy >= h:
                        continue
                    if font.bitmap[g["bitmapOffset"] + sx * cb + (sy >> 3)] & (1 << (sy & 7)):
                        setpix(x + dx, y + dy)
                        break
                else:
                    continue
                break


def measure_width(font, text):
    """Rightmost lit pixel of `text` — kdisp_gfx_text_bounds' `hi`."""
    x = hi = 0
    for cp in text:
        g = _glyph(font, cp)
        if g is None:
            continue
        if g["width"]:
            hi = max(hi, x + g["xOffset"] + g["width"] - 1)
        x += g["xAdvance"]
    return hi


def draw_right(setpix, font, right_x, y, text):
    """Mirror of oled_draw_text_right: the rightmost lit pixel lands on `right_x`."""
    draw(setpix, font, max(0, right_x - measure_width(font, text)), y, text)


def fill_rect(setpix, x, y, w, h):
    for px in range(x, x + w):
        for py in range(y, y + h):
            setpix(px, py)


def round_rect(setpix, x, y, w, h, r):
    """Mirror of kdisp_draw_round_rect — the same midpoint-arc walk, so the corners
    land on the same pixels the firmware's do."""
    if w < 2 or h < 2:
        return
    x0, y0, x1, y1 = x, y, x + w - 1, y + h - 1
    r = max(0, min(r, (w - 1) // 2, (h - 1) // 2))
    for i in range(x0 + r, x1 - r + 1):
        setpix(i, y0)
        setpix(i, y1)
    for j in range(y0 + r, y1 - r + 1):
        setpix(x0, j)
        setpix(x1, j)
    cxl, cxr, cyt, cyb = x0 + r, x1 - r, y0 + r, y1 - r
    f, ddf_x, ddf_y, px, py = 1 - r, 1, -2 * r, 0, r
    while px < py:
        if f >= 0:
            py -= 1
            ddf_y += 2
            f += ddf_y
        px += 1
        ddf_x += 2
        f += ddf_x
        for sx, sy in ((cxr + px, cyt - py), (cxr + py, cyt - px),
                       (cxl - px, cyt - py), (cxl - py, cyt - px),
                       (cxr + px, cyb + py), (cxr + py, cyb + px),
                       (cxl - px, cyb + py), (cxl - py, cyb + px)):
            setpix(sx, sy)


def draw_bitmap(setpix, data, ox, oy, w=16, h=16):
    """MSB-first ROW-MAJOR — the panel's own small bitmaps, NOT the glyph layout.

    ⚠️ Two layouts coexist here and neither errors on the other: glyphs are
    column-native (see `draw`), these are row-major. Crossing them renders noise.
    """
    bw = (w + 7) // 8
    for y in range(h):
        for x in range(w):
            if data[y * bw + (x >> 3)] & (0x80 >> (x & 7)):
                setpix(ox + x, oy + y)


def draw_speed_gauge(setpix, x, speed):
    round_rect(setpix, x, SPEED_BOX_Y, SPEED_BOX_W, SPEED_BOX_H, 3)
    round_rect(setpix, x + 1, SPEED_BOX_Y + 1, SPEED_BOX_W - 2, SPEED_BOX_H - 2, 2)
    fill = (speed * SPEED_FILL_H + 127) // 255
    if fill:
        fill_rect(setpix, x + 3, SPEED_FILL_BOTTOM - fill + 1, SPEED_FILL_W, fill)


def hue_to_degrees(hue):
    """Mirror of text_helper.c hue_to_degrees()."""
    return hue * 360 // 255


def hue_name(hue, sat):
    """Mirror of text_helper.c get_hue_name()."""
    if sat < 26:
        return "White"
    deg = hue_to_degrees(hue)
    for limit, name in ((15, "Red"), (45, "Orange"), (70, "Yellow"), (100, "Lime"),
                        (165, "Green"), (195, "Cyan"), (240, "Azure"), (270, "Blue"),
                        (300, "Violet"), (330, "Magenta"), (345, "Pink")):
        if deg < limit:
            return name
    return "Red"


def byte_to_percent(v):
    return (v * 100 + 127) // 255


def brightness_to_level(contrast):
    """Segments lit, 0..GAUGE_SEGMENTS.

    ⚠️ The outer `min` can never bind — `contrast` is clamped to `FULL_BRIGHT` on the
    line above, so the division tops out at GAUGE_SEGMENTS already. It is kept because
    the firmware's expression is the same, and a port that "tidies" a redundancy stops
    diffing line for line against the thing it mirrors. Measured: deleting it is the
    one mutation of this module the suite does not catch, and it cannot be caught —
    there is no input that reaches it.
    """
    contrast = min(contrast, FULL_BRIGHT)
    return min((contrast * GAUGE_SEGMENTS + FULL_BRIGHT // 2) // FULL_BRIGHT,
               GAUGE_SEGMENTS)


def draw_brightness_bars(setpix, x, bottom_y, level):
    """An unlit segment keeps a 1px FOOT, so the whole scale stays visible."""
    for i in range(GAUGE_SEGMENTS):
        bx, h = x + i * GAUGE_PITCH, GAUGE_MIN_H + i
        if i < level:
            fill_rect(setpix, bx, bottom_y - h + 1, GAUGE_BAR_W, h)
        else:
            fill_rect(setpix, bx, bottom_y, GAUGE_BAR_W, 1)


def draw_brightness_row(setpix, small, x, base_y, brightness):
    draw_bitmap(setpix, SUN_BMP, x, base_y - 11, SUN_W, SUN_H)
    draw(setpix, small, x + 15, base_y, _cp(str(brightness)))
    draw_brightness_bars(setpix, x + 40, base_y - 1, brightness_to_level(brightness))


def draw_lang_column(setpix, tiny, globe, x, code):
    """The RGB-OFF re-flow's language column: a big globe over the code, two lines."""
    draw_glyph_half(setpix, globe, x, OFF_GLOBE_Y, 0x1F310)
    for half, base in ((0, OFF_CODE1_BASE), (1, OFF_CODE2_BASE)):
        txt = _cp(code[half * 3:half * 3 + 2])
        lo, hi, cx = 127, 0, 0
        for cp in txt:
            g = _glyph(tiny, cp)
            if g is None:
                continue
            if g["width"]:
                lo = min(lo, cx + g["xOffset"])
                hi = max(hi, cx + g["xOffset"] + g["width"] - 1)
            cx += g["xAdvance"]
        nx = x + (COL_W - (hi - lo + 1)) // 2 - lo + 1
        draw(setpix, tiny, max(x, nx), base, txt)


def _cp(text):
    return [ord(c) for c in text]


def render(side, faces, layer=0, layout="Qwerty", brightness=DEFAULT_BRIGHTNESS,
           rgb=DEFAULT_RGB, lang=DEFAULT_LANG, wpm=DEFAULT_WPM):
    """The lit pixels of one panel, as a set of (x, y).

    `side` is "left" (the USB host, which carries the layout panel) or "right" (the
    bridge, which carries the RGB panel) — the roles `is_usb_host_side()` decides on
    hardware. `rgb=None` models RGB switched off, which re-flows BOTH panels.

    `faces` wants `mid` (`_Mid_` 19px), `small` (`_Small_` 15px), `icons` (IconsFont)
    and `tiny` (`_Nano_` 10px); `globe` is needed only on the RGB-off path. A face
    that is missing drops what it draws rather than failing — the panel is decoration,
    and a partial screen still says which layer is selected.
    """
    disp, small = faces.get("mid"), faces.get("small")
    icons, tiny, globe = faces.get("icons"), faces.get("tiny"), faces.get("globe")

    rgb_on = rgb is not None
    pts: set = set()

    def setp(px, py):
        # The hardware's SET_PIXEL_CLIPPED drops what falls outside, so a row that no
        # longer fits goes missing here the same way rather than growing the image.
        if 0 <= px < PANEL_W and 0 <= py < PANEL_H:
            pts.add((px, py))

    # Each half's indicator column sits on its INNER edge, so the text origin and the
    # marker column differ per panel.
    lock_panel = side != "right"
    col_x = 108 if lock_panel else 0
    text_x = 0 if lock_panel else (20 if rgb_on else 26)
    text_r = 104 if lock_panel else 127

    # top line: layer + role icon + role word
    draw(setp, icons, text_x, TOP_BASE, [ICON_LAYER])
    draw(setp, disp, text_x + 20, TOP_BASE, _cp("%X" % max(0, layer)))
    if lock_panel:
        draw_bitmap(setp, USB_BMP, text_x + 38, 0)
        draw(setp, disp, text_x + 57, TOP_BASE, _cp("USB"))
    else:
        draw_bitmap(setp, LINK_BMP, text_x + 38, 0)
        draw(setp, disp, text_x + 57, TOP_BASE, _cp("Link"))

    # Lock LEDs render on the layout panel only (the state is identical on both
    # halves) — the RGB panel's column is the speed gauge instead.
    if lock_panel:
        draw(setp, icons, col_x, 16, [ICON_NUMLOCK_OFF])
        draw(setp, icons, col_x, CAPS_LOCK_BASE, [ICON_CAPSLOCK_OFF])
        draw(setp, small, col_x + 6, SIDE_MARKER_BASE, _cp("L"))
    else:
        draw(setp, small, col_x + 5, SIDE_MARKER_BASE, _cp("R"))

    if lock_panel:
        draw(setp, small, text_x, LOCK_ROW_B if rgb_on else OFF_ROW_B, _cp(layout))
        if rgb_on:
            # Speed (and the language slot sharing its row) sits under the layout
            # name; brightness takes the bottom row, since the ~98px meter needs one
            # to itself.
            draw_bitmap(setp, WPM_BMP, 0, LOCK_ROW_C - 8, WPM_ICON_W, WPM_ICON_H)
            draw(setp, small, 15, LOCK_ROW_C, _cp(str(wpm)))
            draw_bitmap(setp, GLOBE_BMP, 46, LOCK_ROW_C - 12, GLOBE_W, GLOBE_H)
            draw(setp, tiny, 62, LOCK_ROW_C, _cp(lang))
            draw_brightness_row(setp, small, 0, LOCK_ROW_D, brightness)
        else:
            # Brightness holds this panel's bottom row in BOTH modes, so the speed is
            # what migrates to the near-empty RGB panel.
            draw_brightness_row(setp, small, 0, OFF_ROW_C, brightness)
    elif not rgb_on:
        draw(setp, small, text_x, RGB_OFF_ROW_B, _cp("RGB"))
        draw(setp, small, text_x + 34, RGB_OFF_ROW_B, _cp("Off"))
        draw_bitmap(setp, WPM_BMP, text_x, RGB_OFF_ROW_C - 8, WPM_ICON_W, WPM_ICON_H)
        draw(setp, small, text_x + 15, RGB_OFF_ROW_C, _cp(str(wpm)))
        draw_lang_column(setp, tiny, globe, col_x, lang)
    else:
        hue, sat, val, speed, mode, name = rgb
        draw(setp, small, text_x, RGB_ROW_B, _cp(str(mode)))
        name_x = text_x + 22
        draw(setp, small, name_x, RGB_ROW_B, _cp(name.rstrip("2")))
        if name.endswith("2"):      # "Splash2" -> "Splash" + a superscript
            hi = measure_width(small, _cp(name.rstrip("2")))
            draw_bitmap(setp, SUPER2_BMP, name_x + hi + 2, 18, SUPER2_W, SUPER2_H)
        draw_speed_gauge(setp, col_x, speed)
        draw(setp, small, text_x, RGB_ROW_C, _cp(hue_name(hue, sat)))
        draw_right(setp, small, text_r - 4, RGB_ROW_C, _cp(str(hue_to_degrees(hue))))
        draw_bitmap(setp, DEGREE_BMP, text_r - 2, 34, DEGREE_W, DEGREE_H)
        draw_bitmap(setp, DROPLET_BMP, text_x, DROPLET_Y, DROPLET_W, DROPLET_H)
        draw(setp, small, text_x + DROPLET_W + SV_ICON_GAP, RGB_ROW_D,
             _cp("%d%%" % byte_to_percent(sat)))
        vtxt = _cp("%d%%" % byte_to_percent(val))
        vx = text_r - measure_width(small, vtxt)
        draw_bitmap(setp, SUN_SMALL_BMP, vx - SV_ICON_GAP - SUN_SMALL_W, SUN_SMALL_Y,
                    SUN_SMALL_W, SUN_SMALL_H)
        draw(setp, small, vx, RGB_ROW_D, vtxt)
    return pts
