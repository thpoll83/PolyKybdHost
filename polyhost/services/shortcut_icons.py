"""Map an application's shortcut LABEL to a keycap glyph, fuzzily.

The companion to ``tools/shortcut_probe.py``. The probe discovers that Ctrl+S is
called "Save"; this decides that "Save" should be drawn as a floppy disk rather
than as the word.

Why a label and not an icon name: measured on GTK, AT-SPI exposes no icon name
at all -- a menu item's attributes are ``{'toolkit': 'gtk'}``, there is no Image
interface, and the action name is a generic 'click'. The freedesktop icon name
would have been the ideal key (standardised, language-independent) and it simply
is not reachable. The label is what there is.

EVERY CODEPOINT HERE IS VERIFIED AGAINST THE SHIPPED FONTS. Proposing a glyph the
keyboard cannot draw is worse than proposing none -- the keycap renders blank and
nothing says why -- so ``tests/services/shortcut_icons_test.py`` resolves all of
them through the same union of resident headers and shipped bundles that
``macro_look.load_render_fonts()`` builds. Several obvious choices are absent and
were replaced rather than kept: U+21BA/U+21B6 (undo), U+2398/U+29C9 (copy) and
almost the whole U+2190..U+21FF arrow block resolve to nothing.

⚠️ FUZZY MATCHING DOES NOT SOLVE LOCALIZATION, and it is worth being clear about
that before relying on it. Edit distance gets you "Preferences..." -> "preference"
and "Zoom In" -> "zoom in"; it cannot get you "Speichern" -> "save", because no
amount of fuzziness bridges a translation. On a non-English UI this returns
nothing for most labels, which is the honest answer -- the caller should fall
back to drawing the label text, which the keyboard can do in any Latin script.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

# Resident PolyKybd icons (gfx_icons.h, the C1 band). These need NO font pack --
# they are compiled into the firmware -- so a shortcut that lands on one of these
# renders on a keyboard that has never been flashed with a bundle.
ICON_UP, ICON_DOWN, ICON_LEFT, ICON_RIGHT = 0x81, 0x82, 0x83, 0x84

# concept -> (codepoint, phrases). Phrases are matched longest-first, so a
# compound ("save as") wins over the word it contains ("save").
LEXICON: dict[str, tuple[int, tuple[str, ...]]] = {
    # --- file ---------------------------------------------------------------
    "save":        (0x1F4BE, ("save", "write", "store")),
    "save as":     (0x1F5AB, ("save as", "save a copy", "save copy", "save all")),
    "open":        (0x1F4C2, ("open", "open file", "open recent", "load")),
    "new":         (0x1F5B9, ("new", "new file", "new document", "new from template")),
    "print":       (0x2399,  ("print", "print preview")),
    "reload":      (0x1F5D8, ("reload", "refresh", "revert", "restore")),
    # --- edit ---------------------------------------------------------------
    "cut":         (0x2702,  ("cut",)),
    "copy":        (0x1F5D7, ("copy", "duplicate", "duplicate line")),
    "paste":       (0x1F4CB, ("paste", "paste special", "paste as column")),
    "undo":        (0x1F504, ("undo",)),
    "redo":        (0x1F503, ("redo", "repeat")),
    "delete":      (0x232B,  ("delete", "erase", "clear", "delete line")),
    "select all":  (0x2610,  ("select all", "select")),
    # --- search -------------------------------------------------------------
    "find":        (0x1F50D, ("find", "search", "incremental search", "highlight all")),
    "find next":   (0x1F50E, ("find next", "find previous", "search next",
                              "search again")),
    "replace":     (0x1F501, ("replace", "find and replace", "substitute")),
    "go to":       (0x1F4CD, ("go to", "goto", "jump to", "go to line")),
    # --- view ---------------------------------------------------------------
    "fullscreen":  (0x1F5D6, ("fullscreen", "full screen", "maximize", "maximise")),
    "minimize":    (0x1F5D5, ("minimize", "minimise", "iconify")),
    "window":      (0x1F5D4, ("window", "new window", "close window")),
    "zoom in":     (0x1F5DA, ("zoom in", "increase font", "larger", "bigger",
                              "increase font size")),
    "zoom out":    (0x1F5DB, ("zoom out", "decrease font", "smaller",
                              "decrease font size")),
    # --- navigation (resident icons -- drawable with no font pack) ----------
    "up":          (ICON_UP,    ("up", "line up", "one line up", "scroll up",
                                 "move up", "previous line")),
    "down":        (ICON_DOWN,  ("down", "line down", "one line down",
                                 "scroll down", "move down", "next line")),
    "left":        (ICON_LEFT,  ("left", "word left", "one word left", "back",
                                 "backward", "previous")),
    "right":       (ICON_RIGHT, ("right", "word right", "one word right",
                                 "forward", "next")),
    # --- misc ---------------------------------------------------------------
    "indent":      (0x2348,  ("indent", "increase indent")),
    "outdent":     (0x2347,  ("outdent", "unindent", "decrease indent")),
    "settings":    (0x2699,  ("settings", "preferences", "options", "configure",
                              "properties")),
    "help":        (0x2753,  ("help", "about", "contents", "documentation",
                              "keyboard shortcuts")),
    "close":       (0x1F5D9, ("close", "cancel", "close tab", "close document")),
    "quit":        (0x1F6AA, ("quit", "exit")),
    "bookmark":    (0x1F516, ("bookmark", "favorite", "favourite", "mark")),
    "lock":        (0x1F512, ("lock", "read only", "viewer mode")),
    "comment":     (0x0023,  ("comment", "uncomment", "toggle comment")),
}

# Longest phrase first so "save as" beats "save"; ties broken alphabetically so
# the table order cannot silently decide a match.
_PHRASES: list[tuple[str, str]] = sorted(
    ((phrase, concept) for concept, (_, phrases) in LEXICON.items()
     for phrase in phrases),
    key=lambda pc: (-len(pc[0].split()), -len(pc[0]), pc[0]),
)

# See the measurement in match(): the floor sits in the empty bin between real
# morphology (>= 0.875) and false friends (<= 0.762).
FUZZY_FLOOR = 0.85

# --- spelling folds ---------------------------------------------------------
#
# The small, RULE-SHAPED variations between one app's wording and another's:
# a plural s, British -our/-ise, "dialogue"/"dialog", "centre"/"center". These are
# deterministic, so folding them and re-matching gives an EXACT hit -- no ratio, no
# threshold, and no possibility of the near-miss nonsense a character-similarity
# score produces ("edit" ~ "exit" at 0.75).
#
# ⚠️ A fold can DESTROY a word that already matched: "store" is a phrase for save,
# and the -re/-er rule turns it into "stoer". That is safe here only because folding
# runs AFTER the unfolded rules, never instead of them -- a fold can add a match, it
# can never take one away. Keep that ordering.
#
# ⚠️ A fold is also only ever used to PROBE the lexicon. "four" -> "for" and
# "hour" -> "hor" are wrong as English, and harmless as probes, because neither
# result is a lexicon entry so neither produces an icon.
_FOLDS = (
    (re.compile(r"our\b"), "or"),        # colour -> color, favourite -> favorite
    (re.compile(r"ise\b"), "ize"),       # maximise -> maximize
    (re.compile(r"isation\b"), "ization"),
    (re.compile(r"ue\b"), ""),           # dialogue -> dialog, catalogue -> catalog
    (re.compile(r"([^aeiou])re\b"), r"\1er"),   # centre -> center, metre -> meter
)

# Below this length a trailing "s" is more likely part of the word than a plural.
# "News" (4) must not fold to "new" and take the new-document icon; "Finds" (5) -> "find"
# is the case worth having.
_MIN_PLURAL_LEN = 5


def _fold_word(word: str) -> str:
    if len(word) >= _MIN_PLURAL_LEN and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    for pattern, repl in _FOLDS:
        word = pattern.sub(repl, word)
    return word


def fold_spelling(text: str) -> str:
    """Canonicalise the small orthographic variants, word by word."""
    return " ".join(_fold_word(w) for w in text.split())


_STRIP_TRAILING = re.compile(r"(\.\.\.|…)\s*$")
_PARENTHETICAL = re.compile(r"\s*\([^)]*\)")
_NON_WORD = re.compile(r"[^\w\s]")
_SPACES = re.compile(r"\s+")


def normalize(label: str) -> str:
    """Reduce a menu label to comparable words.

    Handles what real toolkits actually put in a label: mnemonic markers ('_' in
    GTK, '&' in Qt and Win32), a trailing ellipsis, a parenthetical, and the
    alignment padding mousepad emits ('New      ').
    """
    s = label.replace("_", "").replace("&", "")
    s = _STRIP_TRAILING.sub("", s)
    s = _PARENTHETICAL.sub("", s)
    s = _NON_WORD.sub(" ", s)
    return _SPACES.sub(" ", s).strip().lower()


# The lexicon folded the same way a label is, so the comparison is symmetric.
# Without this the folds are one-sided: the table stores "preferences" and a label
# reading "Preference" folds to itself, so the two never meet and only a similarity
# score could join them. Built once, and ordered like _PHRASES.
_FOLDED_PHRASES: list[tuple[str, str]] = sorted(
    ((fold_spelling(phrase), concept) for phrase, concept in _PHRASES),
    key=lambda pc: (-len(pc[0].split()), -len(pc[0]), pc[0]),
)


@dataclass(frozen=True)
class IconMatch:
    codepoint: int
    concept: str
    confidence: float
    rule: str

    @property
    def char(self) -> str:
        return chr(self.codepoint)


def match(label: str, min_confidence: float = 0.6,
          allow_fuzzy: bool = False) -> IconMatch | None:
    """Best glyph for a label, or None when nothing clears `min_confidence`.

    Four rules, tried in descending confidence. The confidence is the point: a
    caller that gets 1.0 should draw the icon, and one that gets 0.62 is better
    off drawing the label text. Returning a single best guess with no score
    would make those indistinguishable.
    """
    text = normalize(label)
    if not text:
        return None

    # 1-3. Exact phrase, contained phrase, then a single distinctive word.
    hit = _literal_rules(text)
    if hit is not None:
        return hit

    # 4. The same three rules again over the spelling-folded label, so a plural s
    #    or a British -our/-ise still lands on an EXACT entry rather than needing a
    #    similarity score. Deterministic, hence the high confidence.
    folded = fold_spelling(text)
    hit = _literal_rules(folded, _FOLDED_PHRASES)
    if hit is not None:
        return IconMatch(hit.codepoint, hit.concept,
                         0.95 if hit.rule == "exact" else 0.85, "spelling")

    words = set(text.split())

    # 4. Fuzzy, for MORPHOLOGY only -- "preference" vs "preferences", "maximise"
    #    vs "maximize". Restricted to single-word labels against single-word
    #    phrases, because character similarity across multi-word labels produces
    #    confident nonsense: measured, "Autosave Document" matched "close
    #    document" at 0.774, which clears any threshold worth having. A caller
    #    would then draw a door icon on a save shortcut. One word against one
    #    word cannot make that mistake.
    #
    #    FUZZY_FLOOR is MEASURED, not chosen. Over real morphological pairs and
    #    real false friends the ratios separate with an empty bin between them:
    #      morphology     preference/preferences .952, favourite/favorite .941,
    #                     setting/settings .933, colour/color .909,
    #                     maximise/maximize .875
    #      false friends  document/documentation .762, edit/exit .750,
    #                     save/safe .750, find/fine .750, case/close .667
    #    Nothing lands in 0.762..0.875. At the old 0.72 floor mousepad's own menu
    #    posts came back as "Document" -> help and "Edit" -> quit, both confident
    #    and both nonsense. A new word landing inside that gap means the floor has
    #    to be RE-DERIVED from the data, not nudged.
    if not allow_fuzzy or len(words) != 1:
        return None
    best, best_ratio, best_concept = None, 0.0, ""
    for phrase, concept in _PHRASES:
        if " " in phrase:
            continue
        # The plural guard declined to strip this "s" (too short a word), and the
        # fuzzy rule must not quietly undo that -- "news" scores 0.857 against
        # "new", clearing the floor and putting a new-document icon on an RSS
        # shortcut. A guard the next rule can defeat is not a guard.
        if (len(text) < _MIN_PLURAL_LEN and text.endswith("s")
                and text[:-1] == phrase):
            continue
        ratio = difflib.SequenceMatcher(None, text, phrase).ratio()
        if ratio > best_ratio:
            best, best_ratio, best_concept = phrase, ratio, concept
    if best is not None and best_ratio >= max(min_confidence, FUZZY_FLOOR):
        return IconMatch(LEXICON[best_concept][0], best_concept,
                         round(best_ratio, 3), "fuzzy")
    return None


def _literal_rules(text: str, table=None) -> IconMatch | None:
    """Exact phrase, then contained phrase, then single keyword -- no scoring."""
    table = _PHRASES if table is None else table
    words = set(text.split())
    for phrase, concept in table:
        if text == phrase:
            return IconMatch(LEXICON[concept][0], concept, 1.0, "exact")
    for phrase, concept in table:
        parts = phrase.split()
        if len(parts) > 1 and _contains_sequence(text.split(), parts):
            return IconMatch(LEXICON[concept][0], concept, 0.9, "phrase")
    for phrase, concept in table:
        if " " not in phrase and phrase in words:
            return IconMatch(LEXICON[concept][0], concept, 0.75, "keyword")
    return None


def _contains_sequence(haystack: list[str], needle: list[str]) -> bool:
    """True when `needle` appears as consecutive whole words in `haystack`."""
    n = len(needle)
    return any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))
