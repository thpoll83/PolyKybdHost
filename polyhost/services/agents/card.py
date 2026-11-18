"""Render an agent card: the 72x40 1-bit image a number key shows in AI mode.

    +------------------------------------+
    | [mark] title, first words          |   line 1  rows  0..12
    | the title goes on, full width      |   line 2  rows 13..25
    | and ends with '…' when it is cut   |   line 3  rows 26..39
    +------------------------------------+

The vendor mark is the lower 12 rows of the logo at 26 px, cut by the top edge
(2026-11-18), top left, with the text 1 px to its right; only
line 1 is beside it, lines 2 and 3 use the full width. A cloud session's mark has a cloud outline drawn over the logo's
lower right, inside the logo's box (with_cloud). Marks are never scaled. Three lines of 14 px text
(card experiments, 2026-11-17). The state icon (12 px) is in the bottom right
corner on every page, with a cleared margin of ICON_CLEAR px; only line 3 meets it,
and ends before that margin.

One page per card: a title that does not fit ends with '…'. The controller draws
a session title without its small words (model.card_words). Each line takes as
many characters as fit, so words are split at any letter. Text is Pillow's
bundled sans font (Aileron) drawn without anti-aliasing; a character Aileron does
not have comes from FALLBACK_FONTS (Korean, Japanese: Galmuri11).

The result is 360 bytes, the same packing as OverlayData.all_bytes (np.packbits,
row-major, MSB first), uploaded with cmd 46 straight into a pool slot.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass

from polyhost.services.agents.model import AgentState, no_brackets, vendor

log = logging.getLogger("PolyHost")

PANEL_W, PANEL_H = 72, 40
MARK_BOX = 26          # a logo is rendered at this size; its lower part shows
MARK_SHOWN = 12        # rows of the logo shown at the top edge: beside line 1 only
MARK_GAP = 1           # px between the mark and the text beside it
FONT_SIZE = 14
LINE_PITCH = 13        # three lines in 40 rows; a descender may touch the cap below
LINES = 3
TEXT_W = PANEL_W - 2   # a full-width line: 1 px margin each side
ICON = 12              # the state icon, bottom right: it touches line 3 only
ICON_CLEAR = 1         # px kept free left of and above the state icon
MAX_PAGES = 1          # one page; a longer title ends with '…'
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


# Fallback fonts for characters Aileron does not have (2026-11-18: Pillow's copy
# of Aileron is ASCII only, so a German, Korean or Chinese title showed boxes). A
# character is drawn with the first font that has it. Galmuri11 is bundled
# (res/fonts/agent-cards/), so European titles work offline. The others are
# downloaded into font_downloader's cache the first time a title needs one
# (`ranges`), when agents_download_fonts is on (PolyCore sets MISSING_FONT_HOOK);
# the card shows boxes until then and is drawn again after (fonts_version()).
@dataclass(frozen=True)
class FallbackFont:
    name: str                    # the bundled file, or the font_downloader catalog name
    px: int
    bundled: bool = False
    url: str = ""                # a download that is not in noto-fonts.yaml
    filename: str = ""           # its file name in the cache
    ranges: tuple = ()           # (first, last) code points it is downloaded for


CJK = ((0x3000, 0x303F), (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF),
       (0xFF00, 0xFFEF))
FALLBACK_FONTS = (
    FallbackFont("Galmuri11.ttf.xz", 12, bundled=True),  # European, Greek, Cyrillic, Korean, Japanese
    FallbackFont("WenQuanYi Zen Hei Mono (CJK)", 12,     # the Chinese characters Galmuri lacks
                 url="https://www.polykybd.org/fonts/agent-cards/WenQuanYiZenHeiMono-cjk.ttf",
                 filename="WenQuanYiZenHeiMono-cjk.ttf", ranges=CJK),
    FallbackFont("Noto Sans Devanagari", 13, ranges=((0x0900, 0x097F), (0xA8E0, 0xA8FF))),
    FallbackFont("Noto Sans Thai", 13, ranges=((0x0E00, 0x0E7F),)),
    FallbackFont("Noto Sans Armenian", 13, ranges=((0x0530, 0x058F), (0xFB13, 0xFB17))),
    FallbackFont("Noto Sans Hebrew", 13, ranges=((0x0590, 0x05FF), (0xFB1D, 0xFB4F))),
    FallbackFont("Noto Sans Arabic", 13, ranges=((0x0600, 0x06FF), (0x0750, 0x077F),
                                                 (0x08A0, 0x08FF), (0xFB50, 0xFDFF),
                                                 (0xFE70, 0xFEFF))),
)
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "res", "fonts", "agent-cards")
# Called with a FallbackFont that is not on disk and would draw a character of a
# title; returns True when a download started (not asked again for RETRY_S, so a
# failed download is tried again then), False when downloads are off. PolyCore
# sets it.
MISSING_FONT_HOOK = None
RETRY_S = 600.0                  # a failed or refused download is asked for again after this
_FALLBACKS = None
_FONTS_VERSION = 0
_REQUESTED = {}                  # font name -> time.monotonic() of the last request
_MISSING = set()                 # names of fonts a drawn card needed
_HAS = {}
_FALLBACK_LOCK = threading.RLock()


def _probe_draw():
    from PIL import Image, ImageDraw
    draw = ImageDraw.Draw(Image.new("1", (1, 1)))
    draw.fontmode = "1"
    return draw


def download_spec(entry: FallbackFont):
    """The font_downloader.NotoFont that fetches a downloaded entry: its own URL,
    or the catalog entry of that name; None when the catalog has none."""
    from polyhost.services import font_downloader
    if entry.url:
        return font_downloader.NotoFont(entry.name, entry.url, entry.filename)
    return next((f for f in font_downloader.load_catalog() if f.name == entry.name), None)


def _font_bytes(entry: FallbackFont):
    """The TTF bytes of an entry: the bundled file (xz-compressed), or the
    downloaded file when it is in the cache; None when it is not there."""
    import lzma
    if entry.bundled:
        with open(os.path.join(FONT_DIR, entry.name), "rb") as fh:
            data = fh.read()
        return lzma.decompress(data) if entry.name.endswith(".xz") else data
    from polyhost.services import font_downloader
    spec = download_spec(entry)
    if spec is None or not font_downloader.is_downloaded(spec):
        return None
    with open(font_downloader.local_path(spec), "rb") as fh:
        return fh.read()


def fonts_version() -> int:
    """Increased each time a downloaded font becomes usable: a card drawn with
    an older version is drawn again."""
    return _FONTS_VERSION


def fonts_changed() -> None:
    """A font was downloaded: load the fallback fonts again."""
    global _FALLBACKS, _FONTS_VERSION
    with _FALLBACK_LOCK:
        _FALLBACKS = None
        _FONTS_VERSION += 1


def _fallbacks() -> list:
    """(font, dy, entry) for each FALLBACK_FONTS entry that is on disk. dy moves its
    baseline so its capital H has the same top as Aileron's: a CJK glyph is as
    tall as that H and would otherwise stand above the line. A font without an H
    (the Chinese one) aligns the top of an ideograph instead."""
    global _FALLBACKS
    with _FALLBACK_LOCK:
        if _FALLBACKS is None:
            import io
            import lzma
            from PIL import ImageFont
            _HAS.clear()            # keyed by id(font): a new font can reuse an old id
            draw = _probe_draw()
            base_top = draw.textbbox((0, 0), "H", font=_font(FONT_SIZE), anchor="ls")[1]
            out = []
            for entry in FALLBACK_FONTS:
                try:
                    data = _font_bytes(entry)
                    if data is None:
                        continue                    # not downloaded (yet)
                    font = ImageFont.truetype(io.BytesIO(data), entry.px)
                except (OSError, ValueError, lzma.LZMAError) as e:
                    log.warning("Agent cards: fallback font %s not loaded: %s", entry.name, e)
                    continue
                ref = next((c for c in "H\u4eec\u8fd9\u8bf4\u65f6\u5bf9\u8fc7\u56fd"
                            if _has(font, c)), "H")
                top = draw.textbbox((0, 0), ref, font=font, anchor="ls")[1]
                out.append((font, base_top - top, entry))
            _FALLBACKS = out
        return _FALLBACKS


def _note_missing(ch: str) -> None:
    """No loaded font has `ch`: remember the entry whose ranges hold it, and ask
    for it (request_missing)."""
    cp = ord(ch)
    entry = next((e for e in FALLBACK_FONTS
                  if any(a <= cp <= b for a, b in e.ranges)), None)
    if entry is not None:
        _MISSING.add(entry.name)
        request_missing()


def request_missing() -> None:
    """Ask MISSING_FONT_HOOK for each font a drawn card needed and that is not
    loaded, at most once per RETRY_S. The controller calls it on every pass too:
    an unchanged card is not drawn again, so a failed download, or downloads
    turned on later, would otherwise never be asked again."""
    hook = MISSING_FONT_HOOK
    if hook is None or not _MISSING:
        return
    loaded = {e.name for _f, _d, e in _fallbacks()}
    for entry in FALLBACK_FONTS:
        if entry.name not in _MISSING:
            continue
        if entry.name in loaded:
            _MISSING.discard(entry.name)
            continue
        now = time.monotonic()
        last = _REQUESTED.get(entry.name)
        if last is not None and now - last < RETRY_S:
            continue
        try:
            if hook(entry):          # False: downloads are off; asked again next time
                _REQUESTED[entry.name] = now
        except Exception as e:  # noqa: BLE001 - drawing a card must not fail on it
            log.warning("Agent cards: font download for %s not started: %s", entry.name, e)


def _has(font, ch: str) -> bool:
    """Whether `font` draws `ch` as its own glyph: its drawing differs from the one
    of a code point no font has (the .notdef box)."""
    if ch.isspace():
        return True
    key = (id(font), ch)
    if key not in _HAS:
        from PIL import Image, ImageDraw

        def drawn(c):
            img = Image.new("1", (48, 48))
            draw = ImageDraw.Draw(img)
            draw.fontmode = "1"
            draw.text((8, 8), c, font=font, fill=1)
            return img.tobytes()
        notdef = _HAS.setdefault((id(font), None), drawn("\U0010fffd"))
        _HAS[key] = drawn(ch) != notdef
    return _HAS[key]


def _runs(text: str, size: int = FONT_SIZE) -> list[tuple]:
    """(font, dy, part) runs of `text`: each character in the first font of
    Aileron at `size` and _fallbacks() that has it (Aileron when none has it)."""
    import unicodedata
    base = _font(size)
    runs = []
    for ch in text:
        # A combining mark (a Devanagari vowel sign, a Thai tone mark) stays in the
        # run of its letter: drawn alone, the shaper puts it on a dotted circle.
        # A space stays in the run before it too, so a right-to-left phrase is one
        # run that the shaper orders as a whole.
        if runs and (unicodedata.category(ch).startswith("M") or ch.isspace()):
            runs[-1] = (runs[-1][0], runs[-1][1], runs[-1][2] + ch)
            continue
        font, dy = base, 0
        if not _has(base, ch):
            font, dy = next(((f, d) for f, d, _e in _fallbacks() if _has(f, ch)), (base, 0))
            if font is base and not ch.isspace():
                _note_missing(ch)
        if runs and runs[-1][0] is font:
            runs[-1] = (font, dy, runs[-1][2] + ch)
        else:
            runs.append((font, dy, ch))
    return runs


def _measure(text, size=FONT_SIZE):
    """(left, top, right, bottom) of `text` as drawn WITHOUT anti-aliasing, through
    the fallback fonts as _draw_text draws it.
    ⚠️ Not font.getbbox(): with fontmode "1" the hinting differs, and getbbox read
    "polykybd-docs" as 65 px wide when it draws 76 px, so the headline was clipped."""
    draw = _probe_draw()
    runs = _runs(text, size)
    if len(runs) <= 1 and (not runs or runs[0][0] is _font(size)):
        return draw.textbbox((0, 0), text, font=_font(size))
    ascent = _font(size).getmetrics()[0]
    x, box = 0.0, None
    for font, dy, part in runs:
        b = draw.textbbox((x, ascent + dy), part, font=font, anchor="ls")
        box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]),
                                     max(box[2], b[2]), max(box[3], b[3]))
        x += draw.textlength(part, font=font)
    return tuple(int(v) for v in box)


def is_rtl(text: str) -> bool:
    """Whether `text` reads right to left: its first letter is Hebrew or Arabic."""
    import unicodedata
    for ch in text or "":
        kind = unicodedata.bidirectional(ch)
        if kind in ("R", "AL"):
            return True
        if kind == "L":
            return False
    return False


def _draw_text(draw, xy, text, size=FONT_SIZE, rtl=None):
    """Draw `text` with its top left at `xy` as draw.text does with Aileron, each
    character in the font _runs picks. In a right-to-left text (`rtl`, else
    is_rtl(text)) the runs are drawn from right to left; the shaper orders the
    characters inside each run (a Latin word or a number in it stays left to
    right)."""
    x, y = xy
    ascent = _font(size).getmetrics()[0]
    runs = _runs(text, size)
    if is_rtl(text) if rtl is None else rtl:
        from PIL import ImageFont
        # Drawn from the last run to the first. The space after a run in the text
        # (a space stays in the run before it) is drawn left of that run, between
        # it and the run drawn next, so the width is the same as _measure's.
        visual = list(reversed(runs))
        for k, (font, dy, part) in enumerate(visual):
            shown = part.rstrip()
            # Only a raqm font takes a direction (Pillow's Aileron is basic layout,
            # and draws left to right). A card has no brackets (model.no_brackets),
            # so no character needs mirroring.
            kw = ({"direction": "rtl" if is_rtl(shown) else "ltr"}
                  if getattr(font, "layout_engine", None) == ImageFont.Layout.RAQM else {})
            draw.text((x, y + ascent + dy), shown, font=font, anchor="ls", fill=1, **kw)
            x += draw.textlength(shown, font=font)
            if k + 1 < len(visual):
                trail = visual[k + 1][2][len(visual[k + 1][2].rstrip()):]
                if trail:
                    x += draw.textlength(trail, font=visual[k + 1][0])
        return
    for font, dy, part in runs:
        draw.text((x, y + ascent + dy), part, font=font, anchor="ls", fill=1)
        x += draw.textlength(part, font=font)


def _text_centred(draw, text, y, size=FONT_SIZE):
    box = _measure(text, size)
    draw.text(((PANEL_W - (box[2] - box[0])) // 2 - box[0], y), text, font=_font(size), fill=1)


def fit_text(text: str, width: int = TEXT_W, size: int = FONT_SIZE) -> str:
    """Cut `text` to what fits `width` pixels in the card font, with a trailing '.'."""
    text = " ".join((text or "").split())
    if _measure(text, size)[2] <= width:
        return text
    while text and _measure(text + ".", size)[2] > width:
        text = text[:-1]
    return text.rstrip() + "."


# Letters (category Lo) that are spacing marks of the letter before them in the
# grapheme break rules: Thai and Lao Sara Am.
_SPACING_MARKS = frozenset("\u0e33\u0eb3")


def _clusters(text: str) -> list[str]:
    """`text` split where a line may break: a letter with its combining marks, and
    a Devanagari-style conjunct (a letter after a virama or a zero-width joiner)
    stay together. Split inside one, the shaper draws a dotted circle."""
    import unicodedata
    out = []
    for ch in text:
        if out and (unicodedata.category(ch).startswith("M") or ch in _SPACING_MARKS
                    or ch == "\u200d"
                    or out[-1][-1] == "\u200d" or unicodedata.combining(out[-1][-1]) == 9):
            out[-1] += ch
        else:
            out.append(ch)
    return out


def _cut_with_ellipsis(text: str, width: int, size: int = FONT_SIZE) -> str:
    """`text` cut to what fits `width` pixels, ending with '…'."""
    parts = _clusters(text.rstrip())
    while parts and _ink_width("".join(parts) + "\u2026", size) > width:
        parts.pop()
        while parts and parts[-1].isspace():
            parts.pop()
    return "".join(parts) + "\u2026"


def _ink_width(text: str, size: int = FONT_SIZE) -> int:
    box = _measure(text, size)
    return box[2] - box[0]


def _code_points(ranges: str) -> frozenset:
    """The characters of `ranges`: hex code points and ranges, "0620 0622-064A"."""
    out = set()
    for item in ranges.split():
        lo, _, hi = item.partition("-")
        out.update(map(chr, range(int(lo, 16), int(hi or lo, 16) + 1)))
    return frozenset(out)


# Unicode joining types (DerivedJoiningType.txt, Unicode 16.0) of U+0600..U+08FF:
# Arabic, Syriac, N'Ko, Mandaic. _JOINS_NEXT: dual-joining, left-joining and
# join-causing (tatweel) characters, which join the letter after them.
# _JOINS_PREVIOUS: dual-joining, right-joining and join-causing ones, which join
# the letter before them. Alef, dal, reh and waw join only the letter before them;
# hamza joins neither side. Python's unicodedata has no joining type.
_JOINS_NEXT = _code_points(
    "0620 0626 0628 062A-062E 0633-0647 0649-064A 066E-066F 0678-0687 069A-06BF "
    "06C1-06C2 06CC 06CE 06D0-06D1 06FA-06FC 06FF 0712-0714 071A-071D 071F-0727 "
    "0729 072B 072D-072E 074E-0758 075C-076A 076D-0770 0772 0775-0777 077A-077F "
    "07CA-07EA 07FA 0841-0845 0848 084A-0853 0855 0860 0862-0865 0868 0883-0886 "
    "0889-088D 08A0-08A9 08AF-08B0 08B3-08B8 08BA-08C8 "
)
_JOINS_PREVIOUS = _code_points(
    "0620 0622-064A 066E-066F 0671-0673 0675-06D3 06D5 06EE-06EF 06FA-06FC 06FF "
    "0710 0712-072F 074D-077F 07CA-07EA 07FA 0840-0858 0860 0862-0865 0867-086A "
    "0870-0886 0889-088E 08A0-08AC 08AE-08C8 "
)


def _transparent(ch: str) -> bool:
    """A character that joining skips (joining type T): a mark (Mn, Me) or a
    format character (Cf) such as U+061C ARABIC LETTER MARK. ZWNJ and ZWJ are not:
    they stop or cause a join."""
    return unicodedata.category(ch) in ("Mn", "Me", "Cf") and ch not in "\u200c\u200d"


def _joins(left: str, right: str) -> bool:
    """Whether the text `left` ends with a letter that is drawn joined to the letter
    `right` starts with, by the Unicode joining types. Transparent characters in
    between (vowel marks, U+061C) are skipped on both sides."""
    left = left.rstrip("".join(c for c in set(left) if _transparent(c)))
    right = right.lstrip("".join(c for c in set(right) if _transparent(c)))
    a, b = left[-1:], right[:1]
    return a in _JOINS_NEXT and b in _JOINS_PREVIOUS


def flow(text: str, widths, size: int = FONT_SIZE) -> list[str]:
    """`text` in lines; line k is `widths[k]` px wide (the last width repeats). Each
    line takes as many characters as fit, so a word is split at any letter (the
    card shows as much of the title as it can, 2026-11-18), but never inside a
    _clusters() unit. A space at the start of a line is dropped."""
    lines, cur = [], ""

    def width():
        return widths[min(len(lines), len(widths) - 1)]

    for ch in _clusters(" ".join((text or "").split())):
        if not cur and ch == " ":
            continue
        if _ink_width(cur + ch, size) <= width():
            cur += ch
            continue
        if _joins(cur, ch):
            # An Arabic word split here keeps its joined letter forms.
            lines.append(cur + "\u200d")
            cur = "\u200d" + ch
            continue
        lines.append(cur.rstrip())
        cur = "" if ch == " " else ch
    if cur:
        lines.append(cur)
    return lines


def _spans(mark, icon) -> list[tuple[int, int]]:
    """(left, right) x of each text line (right exclusive): a line whose rows meet
    the vendor mark (top left) starts MARK_GAP right of it, a line that meets the
    state icon (bottom right) or its cleared margin ends before them."""
    spans = []
    for k in range(LINES):
        top = k * LINE_PITCH
        left, right = 1, PANEL_W - 1
        if mark is not None and top < mark.shape[0]:
            left = mark.shape[1] + MARK_GAP
        if icon is not None and top + LINE_PITCH > PANEL_H - icon.shape[0] - ICON_CLEAR:
            right = PANEL_W - icon.shape[1] - ICON_CLEAR
        spans.append((left, right))
    return spans


def _beside(mask) -> int:
    """How many text lines sit right of a mark this tall."""
    if mask is None:
        return 0
    return min(LINES, -(-mask.shape[0] // LINE_PITCH))   # 1..13 rows: 1, 14..26: 2


def paginate(text: str, mask=None, icon=None, size: int = FONT_SIZE,
             number: int = 0) -> list[list[str]]:
    """The pages of a card: lists of at most LINES lines. Each line is as wide as
    _spans allows: the vendor mark narrows lines on page 1 only, the state icon on
    every page. One flow over all pages, cut every LINES lines. Brackets are left
    out (model.no_brackets). `number` (two
    agents whose cards show the same title) follows the title, and stays after the
    '…' of a cut title: it is what tells the two keys apart."""
    suffix = f" {number}" if number else ""
    text = no_brackets(text or "") + suffix
    first = [r - l for l, r in _spans(mask, icon)]
    later = [r - l for l, r in _spans(None, icon)]
    # Enough lines for any title: each line holds at least one character.
    widths = first + later * (len(text) // LINES + 2)
    lines = flow(text, widths, size)
    pages = [lines[i:i + LINES] for i in range(0, max(1, len(lines)), LINES)]
    if len(pages) > MAX_PAGES:
        pages = pages[:MAX_PAGES]
        last = len(pages[-1]) - 1
        # Its own line's width: the state icon can make it shorter than TEXT_W.
        room = later[last] - (_ink_width(suffix, size) + 1 if suffix else 0)
        pages[-1][last] = _cut_with_ellipsis(pages[-1][last], room, size) + suffix
    return pages


# A vendor slug "agent:<name>" is a finished card mark shipped as
# res/icons/agents/<name>.png (tools/gen_agent_marks.py), for vendors that
# Simple Icons and MDI do not carry. It is used as it is, never scaled.
AGENT_MARK_PREFIX = "agent:"
AGENT_MARK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "res", "icons", "agents")


def _crop(mask):
    rows, cols = mask.any(1).nonzero()[0], mask.any(0).nonzero()[0]
    if not len(rows):
        return None
    return mask[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]


def _shipped_mark(name: str):
    """A shipped mark (res/icons/agents/), as it is: drawn for the card, at most
    MARK_SHOWN rows tall."""
    try:
        import numpy as np
        from PIL import Image
        with Image.open(os.path.join(AGENT_MARK_DIR, name + ".png")) as img:
            mask = np.array(img.convert("L")) > 127
    except Exception as e:  # noqa: BLE001 - cosmetic: fall back to the next slug
        log.debug("Agent mark %s: %s", name, e)
        return None
    return _crop(mask[-MARK_SHOWN:]) if mask.any() else None


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
                    # render_overlay centres the logo in the full 40-row panel; keep
                    # its ink box, then only its lower MARK_SHOWN rows.
                    mask = _crop(mask[:, PANEL_W - MARK_BOX:])
                    return None if mask is None else mask[-MARK_SHOWN:]
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


def _paste(canvas, mask, x, y):
    """OR a bool mask into the (40, 72) canvas at (x, y), clipped to the panel."""
    h = min(mask.shape[0], canvas.shape[0] - y)
    w = min(mask.shape[1], canvas.shape[1] - x)
    canvas[y:y + h, x:x + w] |= mask[:h, :w]


# Cloud sessions: a cloud outline drawn over the lower right of the agent's logo
# (card experiments, 2026-11-17). Since the logo strip is 12 rows (2026-11-18) the
# cloud stays inside it, so the mark is no wider and no taller and lines 2 and 3
# keep the full width.
CLOUD_W, CLOUD_H = 16, 10   # px


def with_cloud(logo):
    """`logo` with a 1 px cloud outline drawn in front of its lower right corner,
    inside the logo's box. The cloud's inside and a 1 px border are cleared first,
    so the outline reads over the logo. A wordmark gets the same cloud at its
    right end; a mark smaller than the cloud grows to hold it."""
    import numpy as np
    from polyhost.services.agents import icons
    logo = np.asarray(logo, dtype=bool)
    shape = icons.cloud(CLOUD_W, CLOUD_H)
    x = max(0, logo.shape[1] - CLOUD_W)
    y = max(0, logo.shape[0] - CLOUD_H)
    out = np.zeros((max(logo.shape[0], y + CLOUD_H), max(logo.shape[1], x + CLOUD_W)),
                   dtype=bool)
    out[:logo.shape[0], :logo.shape[1]] = logo
    region = np.zeros_like(out)
    region[y:y + CLOUD_H, x:x + CLOUD_W] = shape
    out &= ~icons.grow(region)
    out[y:y + CLOUD_H, x:x + CLOUD_W] |= icons.outline(shape, 1)
    return out


def _text_mark(text: str):
    """The vendor's short name as a mark, while its logo is not fetched yet."""
    import numpy as np
    from PIL import Image
    img = Image.new("1", (PANEL_W, PANEL_H), 0)
    _draw(img).text((0, 0), text, font=_font(10), fill=1)
    return _crop(np.array(img, dtype=bool))


_STATE_ICONS = {}


def state_icon(state):
    """The ICON x ICON mask for a state (services/agents/icons.py), or None."""
    from polyhost.services.agents import icons
    if not _STATE_ICONS:
        # The icons of the 16 px card corner (2026-11-11), scaled to ICON: '!'
        # from its 19 px drawing, the rest from 16 px.
        _STATE_ICONS.update({k: icons.scaled(v, ICON) for k, v in {
            AgentState.WAITING: icons.waiting(),
            AgentState.IDLE: icons.idle_16(), AgentState.WORKING: icons.working_16()}.items()})
        # Drawn at 12 px: scaled, the '?' lost its dot and the check was 1 px wide.
        _STATE_ICONS[AgentState.STALE] = (icons.stale_12() if ICON == 12
                                          else icons.scaled(icons.stale_16(), ICON))
        _STATE_ICONS[AgentState.DONE] = (icons.done_12() if ICON == 12
                                         else icons.scaled(icons.done(), ICON))
    return _STATE_ICONS.get(state)


@dataclass
class CardLayout:
    """What an agent card shows: the vendor mark (or None), the state icon (or
    None) and the pages of text."""
    mark: object
    pages: list
    icon: object = None

    @property
    def page_count(self) -> int:
        return len(self.pages)


def card_layout(vendor_id: str, headline: str, marks: VendorMarks | None = None,
                state=None, cloud: bool = False, number: int = 0) -> CardLayout:
    """The mark and pages for one agent. `cloud`: a cloud session, whose mark has
    the cloud over the logo (with_cloud). `number`: see paginate. No mark is
    scaled: a first word that does not fit beside the mark starts below it."""
    logo = marks.get(vendor_id) if marks is not None else None
    if logo is None:
        logo = _text_mark(vendor(vendor_id).short[:3])
    mark = with_cloud(logo) if cloud and logo is not None else logo
    icon = state_icon(state)
    return CardLayout(mark, paginate(headline, mark, icon, number=number), icon)


def render_page(layout: CardLayout, page: int = 0):
    """A (40, 72) bool array: one page of an agent card. Lines start at the top;
    a title that fits beside the vendor mark is centred on the mark."""
    import numpy as np
    from PIL import Image
    index = page % max(1, layout.page_count)
    lines = layout.pages[index] if layout.pages else []
    mark = layout.mark if index == 0 else None
    spans = _spans(mark, layout.icon)
    beside = _beside(mark)
    cap = _measure("H")[1]
    rtl = is_rtl("".join(line for page in layout.pages for line in page))
    text_h = (len(lines) - 1) * LINE_PITCH + (_measure("Hg")[3] - cap) if lines else 0
    shift = (mark.shape[0] - text_h) // 2 if mark is not None and len(lines) <= beside else 0
    img = Image.new("1", (PANEL_W, PANEL_H), 0)
    draw = _draw(img)
    for k, line in enumerate(lines):
        if not line:
            continue
        box = _measure(line)
        left, right = spans[k]
        if k < beside:
            x = left - box[0]                                   # against the mark
        else:
            x = left + (right - left - (box[2] - box[0])) // 2 - box[0]
        _draw_text(draw, (x, max(0, shift) + k * LINE_PITCH - cap), line, rtl=rtl)
    canvas = np.array(img, dtype=bool)
    if mark is not None:
        _paste(canvas, np.asarray(mark, dtype=bool), 0, 0)
    if layout.icon is not None:
        _paste(canvas, layout.icon, PANEL_W - layout.icon.shape[1],
               PANEL_H - layout.icon.shape[0])
    return canvas


def render_card(vendor_id: str, headline: str, marks: VendorMarks | None = None, page: int = 0,
                state=None, cloud: bool = False):
    """A (40, 72) bool array for one page of one agent card."""
    return render_page(card_layout(vendor_id, headline, marks, state, cloud), page)


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
