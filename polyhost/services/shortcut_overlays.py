"""Turn an application's harvested shortcuts into keycap overlay masks.

The middle of Phase 2: `shortcut_source` discovers that this app binds Ctrl+S to
a thing called "Save", `shortcut_icons` decides "Save" means the concept `save`,
`icon_catalog` draws that concept into a corner of a 72x40 frame — and this
module is what joins them and says WHICH KEY each mask belongs on.

Nothing here touches the device or the network. `plan()` is pure given a hints
dict, and `render()` needs only a font file and a codepoint table, so the whole
decision layer is testable offline — which matters because the half that cannot
be tested offline (the harvest) is also the half that yields nothing in this
container.
"""

from __future__ import annotations

from dataclasses import dataclass

from polyhost.services import icon_catalog, shortcut_icons
from polyhost.services.shortcut_source.model import displayable_hid

# ⚠️ A BOUND ON A LIST NOBODY CURATES. A classic menubar app measured 26
# shortcuts, but an app is free to expose hundreds of ribbon controls and every
# one of them costs a render, a pool slot and (on a miss) an upload. The cap is
# generous rather than tight -- it exists to stop a pathological app, not to
# ration a normal one -- and the planner keeps the HIGHEST-confidence slots when
# it bites, so what is dropped is the guesswork rather than the sure things.
MAX_SLOTS = 48

# Below this a label is better left alone: the keycap already says what the key
# is, and a wrong icon is worse than none (the same reasoning that keeps
# app-slug matching strict). `match()` itself refuses anything under 0.6.
MIN_CONFIDENCE = 0.85


@dataclass(frozen=True)
class Slot:
    """One icon, bound to one (modifier, keycode) of one application."""
    modifier: int           # the L/R-folded QMK nibble — see the note in plan()
    keycode: int
    concept: str
    icon: str               # catalog icon name
    label: str              # the app's own wording, for the log and curation
    confidence: float


def plan(shortcuts, hints: dict | None = None,
         min_confidence: float = MIN_CONFIDENCE,
         limit: int = MAX_SLOTS) -> list[Slot]:
    """Decide which harvested shortcuts get an icon, and on which key.

    ⚠️ `Shortcut.mods` IS `Modifier`'s value, with no mapping in between: both
    are the L/R-folded QMK nibble (bit0 Ctrl, bit1 Shift, bit2 Alt, bit3 GUI),
    because both were written against the firmware's `overlay_mod_variant()`.
    They were defined independently in `shortcut_source.model` and `device.keys`,
    so a test pins the agreement rather than leaving it to be noticed later.

    Four reasons a shortcut is dropped here, all silent:
      * the key has no keycap slot (`displayable_hid` — a keypad or media key);
      * no concept clears `min_confidence` (drawing a guess is worse than
        nothing, and the label lands in the curation file instead);
      * the concept has no CATALOG name, only a font-pack codepoint. A codepoint
        needs a glyph the keyboard already has; this path renders pixels, so it
        can only use the fetchable half. `save` has both, `format_bold` has only
        the name -- which is the wall the catalog route exists to remove.
      * something better already claimed that (modifier, keycode).

    NOT dropped: a shortcut with NO modifier. F5 or Delete is a real accelerator
    and its overlay is simply always on screen, which is what the hand-made
    templates already do for those keys.
    """
    hints = shortcut_icons.load_hints() if hints is None else hints
    best: dict[tuple[int, int], Slot] = {}
    for sc in shortcuts:
        hid = getattr(sc, "hid", None)
        if not displayable_hid(hid):
            continue
        mods = int(getattr(sc, "mods", 0) or 0)
        if not 0 <= mods <= 0x0F:
            continue
        # ⚠️ No empty-label guard here, deliberately: `match()` normalizes and
        # refuses "" on its own, so one would be dead code. Mutation-checked --
        # removing a guard that nothing can reach is the one mutation a suite
        # CANNOT catch, and the escape is what said the guard was redundant.
        label = (getattr(sc, "label", "") or "").strip()
        hit = shortcut_icons.match(label, min_confidence=min_confidence,
                                   allow_fuzzy=True, hints=hints)
        if hit is None or hit.confidence < min_confidence or not hit.icon:
            continue
        slot = Slot(modifier=mods, keycode=int(hid), concept=hit.concept,
                    icon=hit.icon, label=label, confidence=hit.confidence)
        # Two shortcuts on one key: keep the more confident, and on a tie the
        # first seen, so the result does not depend on dict ordering upstream.
        current = best.get((mods, slot.keycode))
        if current is None or slot.confidence > current.confidence:
            best[(mods, slot.keycode)] = slot
    out = sorted(best.values(), key=lambda s: (-s.confidence, s.modifier, s.keycode))
    return out[:limit]


def icon_names(slots) -> list[str]:
    """The catalog names one subset request has to carry for this plan."""
    return sorted({s.icon for s in slots if s.icon})


def source_name(concept: str, height: int, placement: str) -> str:
    """The pseudo-filename a concept's mask is cached and mapped under.

    ⚠️ THE NAME IS THE MRU CACHE KEY and an exact key hit is returned WITHOUT
    comparing bytes (`overlay_cache.get_or_allocate`), so everything that changes
    the pixels has to be in it. The concept alone is not enough: the icon's
    height and corner are user settings, so `@sc:save` would keep serving a 32 px
    lower-left mask out of the pool after the user asked for 16 px upper-right,
    until the next reconnect cleared the cache.

    Keying on the CONCEPT rather than the app is deliberate and is the opposite
    of `@prog:<slug>`: a program mark differs per app by definition, while a save
    icon is the same pixels whoever drew it -- so Word and Notepad both putting
    Save on Ctrl+S share one pool slot and one upload, and switching between them
    re-sends nothing.
    """
    return f"@sc:{concept}:{height}{placement}"


def render(slots, font_path: str, codepoints: dict,
           height: int | None = None, placement: str | None = None) -> dict:
    """{source_name: {(modifier, keycode): mask}} for everything drawable.

    One mask per CONCEPT, reused across every key that concept lands on -- the
    icon does not depend on the key, so rendering it per slot would be the same
    pixels several times and (worse) several pool slots.

    A concept the subset font does not actually carry is dropped rather than
    drawn: `icon_catalog.render_overlay` returns None for a name Google silently
    omitted, and a missing glyph renders as `.notdef`, a filled box that wipes
    the legend underneath it.
    """
    height = icon_catalog.icon_height() if height is None else height
    placement = icon_catalog.icon_placement() if placement is None else placement
    masks: dict[str, object] = {}
    out: dict[str, dict] = {}
    for slot in slots:
        if slot.concept not in masks:
            masks[slot.concept] = icon_catalog.render_overlay(
                slot.icon, font_path, codepoints, height=height,
                placement=placement)
        mask = masks[slot.concept]
        if mask is None:
            continue
        name = source_name(slot.concept, height, placement)
        out.setdefault(name, {})[(slot.modifier, slot.keycode)] = mask
    return out
