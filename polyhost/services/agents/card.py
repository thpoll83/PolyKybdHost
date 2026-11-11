"""Render an agent card: the 72x40 1-bit image a number key shows in AI mode.

    +------------------------------------+
    | [lower part of mark]  [state icon] |   rows 0..15
    |  headline, up to two lines,        |
    |  centred                           |   rows 15..39
    +------------------------------------+

Only the lower 16 rows of the 26 px vendor mark show, cut by the top edge, so the
headline gets two lines in size 11 (card experiments, 2026-11-10: variant L for
the mark and the font, M for the 16 px state icon). No state word: the icon says
it. Text is Pillow's bundled sans font (Aileron) drawn without anti-aliasing.

The result is 360 bytes, the same packing as OverlayData.all_bytes (np.packbits,
row-major, MSB first), uploaded with cmd 46 straight into a pool slot.
"""
from __future__ import annotations

import logging
import os
import threading

from polyhost.services.agents.model import AgentState, vendor

log = logging.getLogger("PolyHost")

PANEL_W, PANEL_H = 72, 40
MARK_BOX = 26          # the mark is rendered at this size; its lower part shows
MARK_SHOWN = 16        # rows of the mark shown at the top edge, as tall as the icon
ICON = 16              # state icon height and width
FONT_SIZE = 11
LINE_PITCH = 12
TEXT_TOP = 15          # first of two lines; one line is centred in rows 15..39
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


def fit_text(text: str, width: int = PANEL_W - 2, size: int = FONT_SIZE) -> str:
    """Cut `text` to what fits `width` pixels in the card font, with a trailing '.'."""
    text = " ".join((text or "").split())
    if _measure(text, size)[2] <= width:
        return text
    while text and _measure(text + ".", size)[2] > width:
        text = text[:-1]
    return text.rstrip() + "."


def wrap_text(text: str, max_lines: int = 2, width: int = PANEL_W - 2,
              size: int = FONT_SIZE) -> list[str]:
    """`text` in at most `max_lines` lines of `width` pixels. Lines break after a
    space, '-', '_', '/' or '.', never inside a word; the last line is cut with a
    trailing '.' when the rest does not fit."""
    import re
    text = " ".join((text or "").split())
    tokens = [t for t in re.findall(r"[^ \-_/.]*[\-_/.]?(?: |$)?", text) if t]
    lines, cur = [], ""
    for tok in tokens:
        if not cur or _measure((cur + tok).strip(), size)[2] <= width:
            cur += tok
        else:
            lines.append(cur.strip())
            cur = tok
    if cur.strip():
        lines.append(cur.strip())
    if len(lines) > max_lines:
        lines = lines[:max_lines - 1] + [" ".join(lines[max_lines - 1:])]
    return [fit_text(line, width, size) for line in lines]


# A vendor slug "agent:<name>" is a finished card mark shipped as
# res/icons/agents/<name>.png (tools/gen_agent_marks.py), for vendors that
# Simple Icons and MDI do not carry. It is used as it is, never scaled.
AGENT_MARK_PREFIX = "agent:"
AGENT_MARK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "res", "icons", "agents")


def _shipped_mark(name: str):
    try:
        import numpy as np
        from PIL import Image
        with Image.open(os.path.join(AGENT_MARK_DIR, name + ".png")) as img:
            mask = np.array(img.convert("L")) > 127
    except Exception as e:  # noqa: BLE001 - cosmetic: fall back to the next slug
        log.debug("Agent mark %s: %s", name, e)
        return None
    return mask[-MARK_SHOWN:] if mask.any() else None


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
        for slug in vendor(vid).slugs:
            if slug.startswith(AGENT_MARK_PREFIX):
                mask = _shipped_mark(slug[len(AGENT_MARK_PREFIX):])
                if mask is not None:
                    return mask
        try:
            from polyhost.services import app_icons
        except Exception:   # noqa: BLE001 - numpy/Pillow missing: draw text instead
            return None
        for slug in vendor(vid).slugs:
            if slug.startswith(AGENT_MARK_PREFIX):
                continue
            try:
                path = app_icons.fetch_icon(slug, allow_network=allow_network)
                if not path:
                    continue
                mask = app_icons.render_overlay(path, box=MARK_BOX)
                if mask is not None:
                    # render_overlay centres the mark in the full 40-row panel; keep
                    # its ink box, then only the lower half: the card shows that
                    # half at the top edge.
                    mask = mask[:, PANEL_W - MARK_BOX:]
                    rows = mask.any(1).nonzero()[0]
                    cols = mask.any(0).nonzero()[0]
                    if not len(rows):
                        return None
                    mask = mask[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
                    return mask[max(0, mask.shape[0] - MARK_SHOWN):]
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
    """The ICON x ICON mask for a state (services/agents/icons.py), or None."""
    from polyhost.services.agents import icons
    if not _STATE_ICONS:
        # The check mark and '!' read best scaled from 19 px; '?' and the moon
        # are drawn at 16 px (compared on full cards, 2026-11-11).
        _STATE_ICONS.update({k: icons.scaled(v, ICON) for k, v in {
            AgentState.WAITING: icons.waiting(), AgentState.DONE: icons.done()}.items()})
        _STATE_ICONS[AgentState.STALE] = icons.stale_16()
        _STATE_ICONS[AgentState.IDLE] = icons.idle_16()
        # Drawn at 16 px: scaled from 19 px its ring was 1 px wide.
        _STATE_ICONS[AgentState.WORKING] = icons.working_16()
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
        draw.text((6, 1), vendor(vendor_id).short[:3], font=_font(10), fill=1)
    lines = wrap_text(headline)
    y = TEXT_TOP if len(lines) > 1 else TEXT_TOP + LINE_PITCH // 2
    for k, line in enumerate(lines):
        _text_centred(draw, line, y + k * LINE_PITCH, FONT_SIZE)
    canvas = np.array(img, dtype=bool)
    if mask is not None:
        mask = np.asarray(mask, dtype=bool)
        # Bottom-aligned with the state icon, whatever the mark's height.
        _paste(canvas, mask, 6, max(0, MARK_SHOWN - mask.shape[0]))
    icon = _state_icon(state)
    if icon is not None:
        _paste(canvas, icon, PANEL_W - icon.shape[1] - 4, 0)
    return canvas


MIC_SCALE = 1.7
WAITING_RADIUS = 15
COUNT_SIZE = 28


def render_dictation_card():
    """The '-' key in AI mode: dictation. The microphone alone, centred."""
    import numpy as np
    from polyhost.services.agents import icons
    canvas = np.zeros((PANEL_H, PANEL_W), dtype=bool)
    mic = icons.microphone(MIC_SCALE)
    _paste(canvas, mic, (PANEL_W - mic.shape[1]) // 2, (PANEL_H - mic.shape[0]) // 2)
    return canvas


def render_next_waiting_card(waiting: int):
    """The '+' key in AI mode: go to the next agent that waits. A large waiting
    icon, an arrow and how many wait, no text line. The count shrinks until it
    fits right of the arrow."""
    import numpy as np
    from PIL import Image
    from polyhost.services.agents import icons
    icon = icons.waiting_disk(WAITING_RADIUS)
    arrow = icons.right_arrow(11)
    arrow_x = 3 + icon.shape[1] + 3
    img = Image.new("1", (PANEL_W, PANEL_H), 0)
    count = str(waiting) if waiting < 100 else "99+"
    room = PANEL_W - 3 - (arrow_x + arrow.shape[1] + 2)
    size = COUNT_SIZE
    while size > 10 and _measure(count, size)[2] - _measure(count, size)[0] > room:
        size -= 2
    box = _measure(count, size)
    _draw(img).text((PANEL_W - 3 - (box[2] - box[0]) - box[0],
                     (PANEL_H - (box[3] - box[1])) // 2 - box[1]), count,
                    font=_font(size), fill=1)
    canvas = np.array(img, dtype=bool)
    _paste(canvas, icon, 3, (PANEL_H - icon.shape[0]) // 2)
    _paste(canvas, arrow, arrow_x, (PANEL_H - arrow.shape[0]) // 2)
    return canvas


def card_bytes(image) -> bytes:
    """360 bytes in the firmware's overlay layout."""
    import numpy as np
    data = np.packbits(np.asarray(image, dtype=bool), axis=None).tobytes()
    assert len(data) == PANEL_W * PANEL_H // 8
    return data
