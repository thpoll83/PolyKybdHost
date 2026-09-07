"""PolyKybd's OWN keycodes, for the layout editor's keycode browser.

The browser's table is QMK's (`res/keycodes.h`), which knows nothing about this
keyboard: it names `QK_KB_0`..`QK_KB_31` and stops there. PolyKybd puts 39 of its
own keycodes in that block, so before this module

  * the seven slots from `QK_KB_32` up were **not in the browser at all** — no tile
    to click, so `KC_AI` (0x7E26 = `QK_KB_38`) could not be assigned to a key by
    any route the app offers; and
  * the 32 below it were assignable only under QMK's placeholder name, so a user
    hunting for "the language key" had to know it was `QK_KB_0`.

⚠️ This is deliberately SEPARATE from `keycap_preview`, which resolves the same
names for a different purpose. Hanging the browser off that would tie *whether a
key can be assigned* to *whether its picture can be drawn* — and the preview
carries a whole rendering pipeline (PIL, the font pack, `oled_preview`) that has
several documented ways to be unavailable. The keycode list must survive all of
them, so it reads nothing but JSON and a C header. Same reasoning as the
"load the two halves independently" rule in CLAUDE.md, one level out.

Two layers, and the second is what makes the block reachable with no data at all:

  `names()`  — PolyKybd's real names, from the shipped export or a newer firmware
               checkout, by the same precedence the previews use.
  `slots()`  — every remaining slot in QMK's `QK_KB` range as `QK_KB_<n>`, so the
               block is fully assignable even when `names()` comes back empty.
"""
import json
import logging
import os
import pathlib
import re

from polyhost.services import macro_label as ml
from polyhost.services import preview_data as pdata

log = logging.getLogger("CustomKeycodes")

# QMK's keyboard-keycode block (quantum/keycodes.h): QK_KB .. QK_KB_MAX. Note the
# header only NAMES the first 32 of these 64 values, which is the gap above.
QK_KB_FIRST = 0x7E00
QK_KB_LAST = 0x7E3F

_KEYCODE_ANCHORS = {"QK_KB_0": QK_KB_FIRST, "QK_USER_0": 0x7E40}
_ENUM_RE = re.compile(r"enum\s+\w+\s*\{(.*?)\n\};", re.S)
_FW_VERSION_RE = re.compile(r'#define\s+FW_VERSION\s+"([^"]+)"')


def _strip_c_comments(s: str) -> str:
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return re.sub(r"//[^\n]*", "", s)


def _resolve_init(init: str, anchors: dict, seen: dict):
    """An enum initialiser -> its value, or None if we cannot be sure.

    Handles the three forms the firmware actually uses: an anchor (`QK_KB_0`), an
    integer, and `<earlier member> + <n>` -- the emoji/language block is laid out
    with `KC_EMJ_PAGE_PREV = KC_EMJ_CAT_BASE + 12`. Bailing on those cost every
    keycode AFTER them, which is most of the settings layer.
    """
    init = init.strip()
    if init in anchors:
        return anchors[init]
    by_name = {n: v for v, n in seen.items()}
    m = re.fullmatch(r"(\w+)\s*\+\s*(\d+)", init)
    if m and m.group(1) in by_name:
        return by_name[m.group(1)] + int(m.group(2))
    if init in by_name:
        return by_name[init]
    try:
        return int(init, 0)
    except ValueError:
        return None


def parse_custom_keycodes(header: str) -> dict:
    """`keycode_helper.h`'s enums -> {value: name}.

    ⚠️ Parsed positionally, so a member with an explicit `= something` other than a
    known anchor would desynchronise every name after it. There is no such member
    today; the two that exist (`= QK_KB_0`, `= QK_USER_0`) are the anchors, and an
    unrecognised initialiser abandons the rest of that enum rather than guessing.
    """
    out, text = {}, _strip_c_comments(header)
    for body in _ENUM_RE.findall(text):
        value = None
        for member in body.split(","):
            member = member.strip()
            if not member:
                continue
            if "=" in member:
                name, _, init = (x.strip() for x in member.partition("="))
                resolved = _resolve_init(init, _KEYCODE_ANCHORS, out)
                if resolved is None:
                    break          # unknown initialiser: the rest would be a guess
                value = resolved
            else:
                name = member
                if value is None:
                    break          # enum with no anchor we understand
                value += 1
            if name.isidentifier():
                out[value] = name
    return out


def _checkout_pk() -> str:
    """<fw>/keyboards/polykybd beside this repo, or "" when there is none.

    Resolved through `macro_label.default_font_dir()` so this, the previews, the
    macro label meter and `scripts/export_preview_data.py` all look in one place.
    """
    try:
        pk = os.path.dirname(os.path.dirname(ml.default_font_dir()))
    except Exception:
        return ""
    return pk if os.path.isdir(pk) else ""


def _checkout(pk: str) -> tuple[dict, str]:
    """(names, FW_VERSION) from a firmware checkout. ({}, "") if unreadable.

    "" sorts oldest in `choose_source`, so an unparseable tree never beats the
    shipped export.
    """
    try:
        header = pathlib.Path(pk, "keycode_helper.h").read_text(
            encoding="utf-8", errors="ignore")
        cfg = pathlib.Path(pk, "config.h").read_text(
            encoding="utf-8", errors="ignore")
    except OSError as e:
        log.debug("no custom keycodes from the checkout (%s)", e)
        return {}, ""
    m = _FW_VERSION_RE.search(cfg)
    return parse_custom_keycodes(header), (m.group(1) if m else "")


def _shipped(preview_dir=None) -> tuple[dict, str]:
    """(names, FW_VERSION) from `res/preview/legends.json`.

    Reads the ONE key it needs out of the export rather than going through
    `PreviewData.load()`, which also loads the font packs and fails as a unit when
    they are missing -- exactly the coupling this module exists to avoid.
    """
    path = pathlib.Path(preview_dir or pdata.PREVIEW_DIR) / "legends.json"
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        log.debug("no custom keycodes from the shipped export (%s)", e)
        return {}, ""
    names = {int(k): str(v) for k, v in (blob.get("custom") or {}).items()}
    return names, str(blob.get("fw_version") or "")


def names(preview_dir=None, checkout_pk=None) -> dict:
    """{keycode: PolyKybd's name}, from whichever source is current.

    Same precedence as the keycap previews (`preview_data.choose_source`): a
    firmware checkout wins ONLY by being strictly newer than the shipped export,
    since a developer's tree is ahead of the last release and a merely-old clone is
    the stale-clone failure that rule was written for.
    """
    ship_names, ship_ver = _shipped(preview_dir)
    pk = _checkout_pk() if checkout_pk is None else checkout_pk
    co_names, co_ver = _checkout(pk) if pk else ({}, "")
    pick = pdata.choose_source(ship_ver, co_ver)
    chosen = co_names if pick == "checkout" else ship_names
    # Fall back rather than return nothing: either source alone is better than a
    # browser that cannot name the block at all.
    return chosen or co_names or ship_names


def slots(known: dict | None = None) -> dict:
    """{name: keycode} covering QMK's whole QK_KB block.

    `known` is a {keycode: name} map (what `names()` returns) whose entries win, so
    a slot PolyKybd has named shows as `KC_AI` and the rest as `QK_KB_38`. Every
    value in the block gets an entry either way — that is the point: the browser
    stays able to place a custom keycode even with no export and no checkout, which
    is the one guarantee that does not depend on data being current.
    """
    known = known or {}
    out: dict[str, int] = {}
    for value in range(QK_KB_FIRST, QK_KB_LAST + 1):
        name = known.get(value) or f"QK_KB_{value - QK_KB_FIRST}"
        out[name] = value
    return out


def browser_entries(preview_dir=None, checkout_pk=None) -> dict:
    """{name: keycode} for the browser's PolyKybd tab — `names()` over `slots()`."""
    return slots(names(preview_dir, checkout_pk))
