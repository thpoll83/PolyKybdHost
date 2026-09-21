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
from polyhost.services.shortcut_source.model import (
    MOD_ALT, MOD_CTRL, MOD_GUI, displayable_hid)

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

# A derived name is a real hit but a weaker one than a curated concept, so it
# sorts BELOW every lexicon match when two shortcuts contend for one key and
# when the plan is trimmed to MAX_SLOTS. Deliberately under `match()`'s own 0.6
# floor for the same reason: it is the answer of last resort.
DERIVED_CONFIDENCE = 0.5
MIN_CONFIDENCE = 0.85


# Why a harvested shortcut got no icon. These are the words the log prints, so
# they are phrased as what the READER has to do about it — the three want
# genuinely different fixes and a single "no icon" line cannot say which.
NO_KEYCAP = "the keyboard has no keycap for that key"
NO_MODIFIER = "a bare keypress on a key that types a character"
NO_CONCEPT = "no icon concept matched the label"
NO_CATALOG_ICON = "the concept has no catalog icon, only a font-pack glyph"
OVER_CAP = f"over the {MAX_SLOTS}-icon cap for one app"

# ⚠️ Keys that INSERT A CHARACTER, where a bare-keypress shortcut must not be
# drawn: 0x04..0x38 is letters, digits, Enter, Backspace, Tab, Space and
# punctuation, minus Esc. Anything above (F-keys, the nav cluster, the arrows,
# the keypad) types nothing, so a bare shortcut there is real and is kept.
#
# ⚠️ Esc is excluded from the set for a second reason as well as typing
# nothing: it is where the PROGRAM MARK goes, so it is spoken for anyway.
_HID_ESC = 0x29
_TYPING_HID = frozenset(range(0x04, 0x39)) - {_HID_ESC}

# The modifiers that make a keypress a SHORTCUT rather than typing. ⚠️ Shift is
# NOT one of them -- Shift+E is a capital E, so its overlay lands on the Shift
# layer of a key that still types.
_REAL_MODS = MOD_CTRL | MOD_ALT | MOD_GUI


def needs_a_modifier(hid, mods) -> bool:
    """Would drawing this shortcut promise an action the key will not perform?

    ⚠️ **A bare-key "shortcut" on a letter is always wrong on this keyboard**,
    and the reason is what the overlay REPLACES: an unmodified chord is drawn on
    the unmodified layer, i.e. over the letter the key actually types. Reported
    from the field (macOS Safari, 2026-09-21) — `D`, `E` and `F` each got an
    icon from a menu item whose real binding needs a modifier this backend
    cannot see (fn/globe is not in the Carbon mask, so it decodes as no
    modifiers at all), and in a browser those keys just type `d`, `e`, `f`.

    So the test is not "did the app claim a shortcut" but "does this key type
    something". A bare F5, Home or arrow is left alone: those keys insert
    nothing, and an icon on them is honest.

    Pure, and separate from `plan_report`, so the rule can be exercised over
    every HID usage without building a plan.
    """
    if hid is None or hid not in _TYPING_HID:
        return False
    return not (int(mods or 0) & _REAL_MODS)


# HID usage -> the name a person would type, for the log only. Letters and
# digits are derived; everything else that a shortcut realistically lands on is
# named here, and anything unnamed prints as its usage id rather than guessing.
_KEY_NAMES = {0x28: "Enter", 0x29: "Esc", 0x2A: "Backspace", 0x2B: "Tab",
              0x2C: "Space", 0x2D: "-", 0x2E: "=", 0x2F: "[", 0x30: "]",
              0x31: "\\", 0x33: ";", 0x34: "'", 0x35: "`", 0x36: ",",
              0x37: ".", 0x38: "/", 0x46: "PrtScn", 0x47: "ScrollLock",
              0x48: "Pause", 0x49: "Insert", 0x4A: "Home", 0x4B: "PgUp",
              0x4C: "Delete", 0x4D: "End", 0x4E: "PgDn", 0x4F: "Right",
              0x50: "Left", 0x51: "Down", 0x52: "Up", 0x53: "NumLock",
              0x65: "Menu"}
for _i in range(12):
    _KEY_NAMES[0x3A + _i] = f"F{_i + 1}"
_MOD_NAMES = ((0x01, "Ctrl"), (0x02, "Shift"), (0x04, "Alt"), (0x08, "GUI"))


def key_name(hid) -> str:
    if hid is None:
        return "?"
    if 0x04 <= hid <= 0x1D:
        return chr(ord("A") + hid - 0x04)
    if 0x1E <= hid <= 0x26:
        return chr(ord("1") + hid - 0x1E)
    if hid == 0x27:
        return "0"
    return _KEY_NAMES.get(hid, f"0x{hid:02x}")


def pretty_key(mods: int, hid) -> str:
    """`Ctrl+Shift+S` — how the log names one (modifier, keycode)."""
    return "+".join([n for bit, n in _MOD_NAMES if mods & bit] + [key_name(hid)])


def describe(sc) -> str:
    """`Ctrl+S 'Save'` — one harvested shortcut, for a refusal line."""
    label = (getattr(sc, "label", "") or "").strip()
    key = pretty_key(int(getattr(sc, "mods", 0) or 0), getattr(sc, "hid", None))
    return f"{key} {label!r}" if label else key


@dataclass(frozen=True)
class Plan:
    """What `plan_report` decided: the slots, and what it refused and why."""
    slots: list
    refused: dict          # reason -> [describe(sc), ...]

    def summary(self) -> str:
        """`20 drawn, 2 refused (no icon concept matched the label: ...)`."""
        parts = [f"{len(self.slots)} drawn"]
        for why, items in sorted(self.refused.items()):
            parts.append(f"{len(items)} because {why}")
        return ", ".join(parts)


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
         limit: int = MAX_SLOTS, known_names=None) -> list[Slot]:
    """The slots alone — see `plan_report` for what was refused and why."""
    return plan_report(shortcuts, hints, min_confidence, limit, known_names).slots


def plan_report(shortcuts, hints: dict | None = None,
                min_confidence: float = MIN_CONFIDENCE,
                limit: int = MAX_SLOTS, known_names=None) -> "Plan":
    """Decide which harvested shortcuts get an icon, and on which key.

    Returns the REFUSALS as well as the slots, because a shortcut the keyboard
    silently declined to draw is the single most useful thing this feature can
    report: it is what the user sees missing, and it is the input Phase 3's
    curation file is built from. A count alone cannot tell "no icon for this
    label" apart from "that key has no keycap", and those want opposite fixes.

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
    refused: dict[str, list[str]] = {}

    def refuse(why, sc):
        refused.setdefault(why, []).append(describe(sc))

    for sc in shortcuts:
        hid = getattr(sc, "hid", None)
        if not displayable_hid(hid):
            refuse(NO_KEYCAP, sc)
            continue
        mods = int(getattr(sc, "mods", 0) or 0)
        if not 0 <= mods <= 0x0F:
            refuse(NO_KEYCAP, sc)
            continue
        if needs_a_modifier(hid, mods):
            # ⚠️ Before the icon lookup, not after: a bare letter must be
            # refused whether or not its label happens to match a concept, and
            # refusing it here also keeps it out of the MAX_SLOTS budget, where
            # it would displace a real shortcut.
            refuse(NO_MODIFIER, sc)
            continue
        # ⚠️ No empty-label guard here, deliberately: `match()` normalizes and
        # refuses "" on its own, so one would be dead code. Mutation-checked --
        # removing a guard that nothing can reach is the one mutation a suite
        # CANNOT catch, and the escape is what said the guard was redundant.
        label = (getattr(sc, "label", "") or "").strip()
        hit = shortcut_icons.match(label, min_confidence=min_confidence,
                                   allow_fuzzy=True, hints=hints)
        concept, icon, confidence = None, None, 0.0
        if hit is not None and hit.confidence >= min_confidence and hit.icon:
            # ⚠️ QUALIFIED (`fluent:copy`), not the bare Material spelling the
            # lexicon stores. Which catalog draws a concept is a property of the
            # concept, so it has to travel with the slot -- the alternative is a
            # second lookup at render time that can disagree with this one.
            concept, confidence = hit.concept, hit.confidence
            icon = shortcut_icons.icon_for(concept) or hit.icon
        elif known_names:
            # ⚠️ The lexicon gets to answer FIRST, always. It is the precision
            # layer -- a chosen icon for a label somebody looked at -- and this
            # is recall: the first catalog name derivable from the label that
            # the fetched table actually carries. Measured over 46 real labels
            # the lexicon resolves 41 and this rescues the other 5 (Rotate,
            # Crop, Export as PDF, Import, Toggle Sidebar), so a label nobody
            # has curated now gets an icon with NO config entry.
            #
            # `known_names` is the reject: derivation proposes and the catalog
            # disposes, exactly as `app_icons.candidates()` leaves a bad slug to
            # the 404. Without a table the fall-back is skipped entirely, which
            # is the behaviour before it existed.
            derived = next((n for n in shortcut_icons.derive_names(label)
                            if n in known_names), None)
            if derived:
                # `known_names` is the MATERIAL table, so a derivation is a
                # Material name by construction -- Fluent's vocabulary is its
                # own and nothing derives into it (see FLUENT_ICONS).
                concept, confidence = derived, DERIVED_CONFIDENCE
                icon = f"{icon_catalog.MATERIAL}:{derived}"
        if not icon:
            refuse(NO_CONCEPT if (hit is None or not hit.icon
                                  or hit.confidence < min_confidence)
                   else NO_CATALOG_ICON, sc)
            continue
        slot = Slot(modifier=mods, keycode=int(hid), concept=concept,
                    icon=icon, label=label, confidence=confidence)
        # Two shortcuts on one key: keep the more confident, and on a tie the
        # first seen, so the result does not depend on dict ordering upstream.
        current = best.get((mods, slot.keycode))
        if current is None or slot.confidence > current.confidence:
            best[(mods, slot.keycode)] = slot
    out = sorted(best.values(), key=lambda s: (-s.confidence, s.modifier, s.keycode))
    for dropped in out[limit:]:
        refused.setdefault(OVER_CAP, []).append(
            f"{pretty_key(dropped.modifier, dropped.keycode)}={dropped.label}")
    return Plan(out[:limit], refused)


def icon_names(slots) -> list[str]:
    """The QUALIFIED catalog names this plan needs, e.g. `fluent:copy`."""
    return sorted({s.icon for s in slots if s.icon})


def icon_names_by_face(slots) -> dict:
    """{face: [bare name, ...]} — one subset request per catalog.

    ⚠️ Grouped rather than flattened because the two catalogs are fetched
    differently: Material serves a server-side subset of exactly the names
    asked for, Fluent ships one whole font. A single flat list would have to
    pick one of those behaviours for both.
    """
    out: dict[str, set] = {}
    for slot in slots:
        if not slot.icon:
            continue
        face, name = icon_catalog.split_face(slot.icon)
        out.setdefault(face, set()).add(name)
    return {face: sorted(names) for face, names in out.items()}


def source_name(concept: str, height: int, placement: str,
                face: str = icon_catalog.DEFAULT_FACE) -> str:
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

    ⚠️ THE FACE IS IN THE KEY, and it is not decoration. `get_or_allocate` takes
    an exact key hit BEFORE it compares bytes, so a keyboard already holding
    `@sc:copy:36lower_right` would keep drawing whatever face was current when
    that slot was filled -- switching catalogs under the same name changes no
    pixels on the device until a reconnect clears the cache. Same reason height
    and placement are here.
    """
    return f"@sc:{face}:{concept}:{height}{placement}"


def render(slots, font_path: str, codepoints: dict,
           height: int | None = None, placement: str | None = None,
           face: str | None = None) -> dict:
    """{source_name: {(modifier, keycode): mask}} for everything drawable.

    Draws ONE catalog's slots: `font_path`/`codepoints` belong to `face`, and a
    slot qualified for a different face is skipped. The caller loops the faces
    it fetched fonts for and merges -- which keeps the multi-catalog
    orchestration next to the fetching rather than spread across both.

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
    face = icon_catalog.DEFAULT_FACE if face is None else face
    masks: dict[str, object] = {}
    out: dict[str, dict] = {}
    for slot in slots:
        slot_face, bare = icon_catalog.split_face(slot.icon)
        if slot_face != face:
            continue
        if slot.concept not in masks:
            masks[slot.concept] = icon_catalog.render_overlay(
                bare, font_path, codepoints, height=height,
                placement=placement)
        mask = masks[slot.concept]
        if mask is None:
            continue
        name = source_name(slot.concept, height, placement, face)
        out.setdefault(name, {})[(slot.modifier, slot.keycode)] = mask
    return out
