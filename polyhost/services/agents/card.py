"""Render an agent card: the 72x40 1-bit image a number key shows in AI mode.

    +------------------------------------+
    |  [vendor mark]        [state icon] |   rows 1..23
    |                                    |
    |  headline, one line, centred       |   rows 27..38
    +------------------------------------+

No state word: the icon says it (first hardware test, 2026-11-10). Text is
Pillow's bundled sans font (Aileron) drawn without anti-aliasing, not the old
serif bitmap face.

The result is 360 bytes, the same packing as OverlayData.all_bytes (np.packbits,
row-major, MSB first), uploaded with cmd 46 straight into a pool slot.
"""
from __future__ import annotations

import logging
import threading

from polyhost.services.agents.model import AgentState, vendor

log = logging.getLogger("PolyHost")

PANEL_W, PANEL_H = 72, 40
MARK_BOX = 22
ICON = 20
HEADLINE_Y = 26
FONT_SIZE = 10
_FONTS = {}


def _font(size: int = FONT_SIZE):
    """Pillow's bundled sans (Aileron) at `size` px; the bitmap face if Pillow was
    built without FreeType."""
    if size not in _FONTS:
        from PIL import ImageFont
        try:
            _FONTS[size] = ImageFont.load_default(size=size)
        except (TypeError, OSError):
            _FONTS[size] = ImageFont.load_default_imagefont()
    return _FONTS[size]


def _draw(img):
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.fontmode = "1"     # no anti-aliasing: the panel is 1 bit
    return draw


def _measure(text, size=FONT_SIZE):
    """(left, top, right, bottom) of `text` as drawn WITHOUT anti-aliasing.
    ⚠️ Not font.getbbox(): with fontmode "1" the hinting differs, and getbbox read
    "polykybd-docs" as 65 px wide when it draws 76 px, so the headline was clipped."""
    from PIL import Image, ImageDraw
    draw = ImageDraw.Draw(Image.new("1", (1, 1)))
    draw.fontmode = "1"
    return draw.textbbox((0, 0), text, font=_font(size))


def _text_centred(draw, text, y, size=FONT_SIZE):
    box = _measure(text, size)
    draw.text(((PANEL_W - (box[2] - box[0])) // 2 - box[0], y), text, font=_font(size), fill=1)


def fit_text(text: str, width: int = PANEL_W - 2) -> str:
    """Cut `text` to what fits `width` pixels in the card font, with a trailing '.'."""
    text = " ".join((text or "").split())
    if _measure(text)[2] <= width:
        return text
    while text and _measure(text + ".")[2] > width:
        text = text[:-1]
    return text.rstrip() + "."


class VendorMarks:
    """Vendor marks as 1-bit masks, from app_icons' cache or shipped marks.

    ⚠️ Never fetches on the caller's thread: the card is rendered on the HID
    worker, and a download there would stall the keyboard. A missing mark is
    fetched once in the background (when auto-fetch is on) and `version`
    increments, so the controller redraws the card."""

    def __init__(self):
        self._masks: dict[str, object] = {}
        self._fetching: set[str] = set()
        self._lock = threading.Lock()
        self.version = 0

    def get(self, vid: str):
        with self._lock:
            if vid in self._masks:
                return self._masks[vid]
        mask = self._load(vid, allow_network=False)
        if mask is None:
            self._fetch_later(vid)
            return None
        with self._lock:
            self._masks[vid] = mask
        return mask

    def _load(self, vid, allow_network):
        try:
            from polyhost.services import app_icons
        except Exception:   # noqa: BLE001 - numpy/Pillow missing: draw text instead
            return None
        for slug in vendor(vid).slugs:
            try:
                path = app_icons.fetch_icon(slug, allow_network=allow_network)
                if not path:
                    continue
                mask = app_icons.render_overlay(path, box=MARK_BOX)
                if mask is not None:
                    # render_overlay centres the mark in the full 40-row panel; keep
                    # only its ink rows, so the card places it at the top.
                    mask = mask[:, PANEL_W - MARK_BOX:]
                    rows = mask.any(1).nonzero()[0]
                    return mask[rows[0]:rows[-1] + 1] if len(rows) else None
            except Exception as e:  # noqa: BLE001 - cosmetic
                log.debug("Agent mark %s for %s failed: %s", slug, vid, e)
        return None

    def _fetch_later(self, vid):
        try:
            from polyhost.services import app_icons
            if not vendor(vid).slugs or not app_icons.auto_fetch_enabled():
                return
        except Exception:   # noqa: BLE001
            return
        with self._lock:
            if vid in self._fetching:
                return
            self._fetching.add(vid)

        def run():
            mask = self._load(vid, allow_network=True)
            if mask is not None:
                with self._lock:
                    self._masks[vid] = mask
                    self.version += 1
        threading.Thread(target=run, name=f"agent-mark-{vid}", daemon=True).start()


_STATE_ICONS = {}


def _state_icon(state):
    """The 19x19 mask for a state (services/agents/icons.py), or None."""
    from polyhost.services.agents import icons
    if not _STATE_ICONS:
        _STATE_ICONS.update({
            AgentState.WORKING: icons.working(), AgentState.WAITING: icons.waiting(),
            AgentState.DONE: icons.done(), AgentState.IDLE: icons.idle(),
            AgentState.STALE: icons.stale(),
        })
    return _STATE_ICONS.get(state)


def _paste(canvas, mask, x, y):
    """OR a bool mask into the (40, 72) canvas at (x, y), clipped to the panel."""
    h = min(mask.shape[0], canvas.shape[0] - y)
    w = min(mask.shape[1], canvas.shape[1] - x)
    canvas[y:y + h, x:x + w] |= mask[:h, :w]


def render_card(vendor_id: str, state: AgentState, headline: str, marks: VendorMarks | None = None):
    """A (40, 72) bool array for one agent card."""
    import numpy as np
    from PIL import Image
    img = Image.new("1", (PANEL_W, PANEL_H), 0)
    draw = _draw(img)
    mask = marks.get(vendor_id) if marks is not None else None
    if mask is None:
        draw.text((8, 6), vendor(vendor_id).short[:3], font=_font(12), fill=1)
    _text_centred(draw, fit_text(headline), HEADLINE_Y)
    canvas = np.array(img, dtype=bool)
    if mask is not None:
        _paste(canvas, np.asarray(mask, dtype=bool), 8, 1)
    icon = _state_icon(state)
    if icon is not None:
        _paste(canvas, icon, PANEL_W - icon.shape[1] - 8, 2)
    return canvas


def render_dictation_card():
    """The '-' key in AI mode: dictation."""
    import numpy as np
    from PIL import Image
    from polyhost.services.agents import icons
    img = Image.new("1", (PANEL_W, PANEL_H), 0)
    _text_centred(_draw(img), "voice", HEADLINE_Y + 2)
    canvas = np.array(img, dtype=bool)
    mic = icons.microphone()
    _paste(canvas, mic, (PANEL_W - mic.shape[1]) // 2, 1)
    return canvas


def render_next_waiting_card(waiting: int):
    """The '+' key in AI mode: go to the next agent that waits, and how many wait."""
    import numpy as np
    from PIL import Image
    from polyhost.services.agents import icons
    img = Image.new("1", (PANEL_W, PANEL_H), 0)
    draw = _draw(img)
    count = str(waiting) if waiting < 100 else "99+"
    draw.text((54, 4), count, font=_font(14), fill=1)
    _text_centred(draw, "next" if waiting else "none", HEADLINE_Y)
    canvas = np.array(img, dtype=bool)
    _paste(canvas, icons.waiting(), 8, 2)
    arrow = icons.right_arrow()
    _paste(canvas, arrow, 31, 7)
    return canvas


def card_bytes(image) -> bytes:
    """360 bytes in the firmware's overlay layout."""
    import numpy as np
    data = np.packbits(np.asarray(image, dtype=bool), axis=None).tobytes()
    assert len(data) == PANEL_W * PANEL_H // 8
    return data
