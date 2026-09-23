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
# concept -> (font-pack codepoint or None, catalog icon name, phrases).
#
# TWO icon sources, and the difference decides what is possible:
#   * the CODEPOINT draws from a `.plyf` bundle already on the keyboard -- no
#     network, but every glyph must be chosen in advance and reshipped.
#   * the ICON NAME is fetched from the catalog on demand (icon_catalog.py) --
#     any of 4277 icons, no firmware change, at the cost of one small download.
# A concept may have only the second: `format_bold` and friends have no bundle
# glyph and never will without a reship, which is exactly the wall the catalog
# route removes. Prefer the codepoint when present (it always works offline) and
# fall back to the name.
#
# Phrases are matched longest-first, so a compound ("save as") wins over the word
# it contains ("save").
LEXICON: dict[str, tuple[int | None, str, tuple[str, ...]]] = {
    # --- file ---------------------------------------------------------------
    "save":        (0x1F4BE, "save", ("save", "write", "store")),
    "save as":     (0x1F5AB, "save_as", ("save as", "save a copy", "save copy",
                                         "save all")),
    "open":        (0x1F4C2, "folder_open", ("open", "open file", "open recent",
                                             "load")),
    "new":         (0x1F5B9, "note_add", ("new", "new file", "new document",
                                          "new from template")),
    "print":       (0x2399,  "print", ("print", "print preview")),
    "reload":      (0x1F5D8, "refresh", ("reload", "refresh", "revert", "restore")),
    # --- edit ---------------------------------------------------------------
    "cut":         (0x2702,  "content_cut", ("cut",)),
    "copy":        (0x1F5D7, "content_copy", ("copy", "duplicate",
                                              "duplicate line")),
    "paste":       (0x1F4CB, "content_paste", ("paste", "paste special",
                                               "paste as column")),
    "undo":        (0x1F504, "undo", ("undo",)),
    "redo":        (0x1F503, "redo", ("redo", "repeat")),
    "delete":      (0x232B,  "delete", ("delete", "erase", "clear",
                                        "delete line")),
    "select all":  (0x2610,  "select_all", ("select all", "select")),
    # --- search -------------------------------------------------------------
    "find":        (0x1F50D, "search", ("find", "search", "incremental search",
                                        "highlight all")),
    "find next":   (0x1F50E, "find_in_page", ("find next", "find previous",
                                              "search next", "search again")),
    "replace":     (0x1F501, "find_replace", ("replace", "find and replace",
                                              "substitute")),
    "go to":       (0x1F4CD, "my_location", ("go to", "goto", "jump to",
                                             "go to line")),
    # --- view ---------------------------------------------------------------
    "fullscreen":  (0x1F5D6, "fullscreen", ("fullscreen", "full screen",
                                            "maximize", "maximise")),
    "minimize":    (0x1F5D5, "minimize", ("minimize", "minimise", "iconify")),
    # ⚠️ "hide" earns an entry because WITHOUT one the derived-name fall-back
    # answers from the WRONG WORD. Every macOS app puts "Hide <AppName>" on
    # Cmd+H, `derive_names` offers the tail word once the head fails, and the
    # app's own name is very often a catalog icon -- so Terminal drew a
    # terminal, Notes a note and Chess a chess piece, each on a key whose
    # entire meaning is the verb (field, 2026-09-21). A wrong keycap, not a
    # missing one, and it repeated the program mark already on ESC.
    #
    # The lexicon answers BEFORE the derivation, so one entry closes the whole
    # family -- "Hide Others", "Hide Folders", "Hide Alternative Screen" and
    # "Hide Downloads" included, none of which drew anything before.
    "hide":        (None,    "visibility_off", ("hide", "hide others",
                                                "hide all")),
    # ⚠️ "close window" is NOT here — it is under `close`, with its two siblings.
    # A window frame on Ctrl+W says WINDOW where the action is CLOSE, and the
    # keycap then cannot be told from "New Window". Found by reading the
    # shortcut-icon log on a real harvest (2026-09-14), not by reading the table:
    # `close tab` and `close document` already drew an X, so this one entry made
    # three identically-shaped labels disagree.
    "window":      (0x1F5D4, "web_asset", ("window", "new window")),
    # U+1F5DA/DB are literally INCREASE/DECREASE FONT SIZE SYMBOL, so they serve
    # both the view-zoom and the text-size wording. Word spells them Grow/Shrink Font.
    "zoom in":     (0x1F5DA, "zoom_in", ("zoom in", "increase font", "larger",
                                         "bigger", "increase font size",
                                         "grow font", "larger font")),
    "zoom out":    (0x1F5DB, "zoom_out", ("zoom out", "decrease font", "smaller",
                                          "decrease font size", "shrink font",
                                          "smaller font")),
    # --- navigation (the codepoints are RESIDENT -- no font pack needed) -----
    "up":          (ICON_UP,    "arrow_upward", ("up", "line up", "one line up",
                                                 "scroll up", "move up",
                                                 "previous line")),
    "down":        (ICON_DOWN,  "arrow_downward", ("down", "line down",
                                                   "one line down", "scroll down",
                                                   "move down", "next line")),
    "left":        (ICON_LEFT,  "arrow_back", ("left", "word left",
                                               "one word left", "back",
                                               "backward", "previous")),
    "right":       (ICON_RIGHT, "arrow_forward", ("right", "word right",
                                                  "one word right", "forward",
                                                  "next")),
    # --- misc ---------------------------------------------------------------
    "indent":      (0x2348,  "format_indent_increase", ("indent",
                                                        "increase indent")),
    "outdent":     (0x2347,  "format_indent_decrease", ("outdent", "unindent",
                                                        "decrease indent")),
    "settings":    (0x2699,  "settings", ("settings", "preferences", "options",
                                          "configure", "properties")),
    "help":        (0x2753,  "help", ("help", "about", "contents",
                                      "documentation", "keyboard shortcuts")),
    "close":       (0x1F5D9, "close", ("close", "cancel", "close tab",
                                       "close document", "close window")),
    "wrap text":   (None,    "wrap_text", ("wrap text", "word wrap",
                                           "line wrap", "soft wrap")),
    "quit":        (0x1F6AA, "logout", ("quit", "exit")),
    "bookmark":    (0x1F516, "bookmark", ("bookmark", "favorite", "favourite",
                                          "mark")),
    "lock":        (0x1F512, "lock", ("lock", "read only", "viewer mode")),
    "comment":     (0x0023,  "comment", ("comment", "uncomment",
                                         "toggle comment")),
    # --- text / document (Office wording) ------------------------------------
    "change case": (0x1F520, "match_case", ("change case", "to uppercase",
                                            "to lowercase", "to title case",
                                            "to opposite case",
                                            "to sentence case", "capitalize")),
    "paragraph":   (0x00B6,  "format_paragraph", ("paragraph",
                                                  "paragraph settings")),
    "alignment":   (0x2630,  "format_align_left", ("alignment", "align",
                                                   "align text")),
    "styles":      (0x1F3A8, "palette", ("styles", "cell styles", "style")),
    "share":       (0x1F517, "share", ("share", "link", "copy link")),
    "insert":      (0x271A,  "add", ("insert", "add", "insert row",
                                     "insert column")),
    # --- CATALOG-ONLY: no bundle glyph exists, and none is needed ------------
    # Every one of these was `text` while the font pack was the only route. The
    # shipped fonts carry no bold, italic or paintbrush glyph among their 7242
    # codepoints, and adding them meant fontconvert plus a bundle reship. The
    # catalog has all six, so the wall is simply gone.
    "bold":        (None, "format_bold", ("bold",)),
    "italic":      (None, "format_italic", ("italic",)),
    "underline":   (None, "format_underlined", ("underline", "underlined")),
    "superscript": (None, "superscript", ("superscript",)),
    "subscript":   (None, "subscript", ("subscript",)),
    "paint":       (None, "format_paint", ("format painter", "painter",
                                           "copy formatting")),
}

# Labels currently left to the TEXT fallback -- Bold, Italic, Underline,
# Superscript, Subscript, Format Painter -- live in res/shortcut_hints.yaml with
# their reasons, because that is data a reviewer edits rather than code. Most are
# "not yet" rather than "never": the letterforms exist in a catalog source font
# and read fine at keycap size, they just do not ship in a bundle. The rule behind
# all of them is unchanged -- a glyph earns an entry only when it beats the word,
# and a glyph that is not flashed draws nothing at all.

# --- the Fluent spelling of each concept ------------------------------------
#
# A SECOND dict rather than a fourth field on LEXICON, because absence is the
# whole mechanism: a concept with no entry here draws from Material. That makes
# "Fluent first, Material for what it lacks or loses" one lookup instead of a
# rule somebody has to apply.
#
# ⚠️ EXPLICIT, never derived. Fluent's vocabulary is systematically its own --
# `undo` is `arrow_undo`, `close` is `dismiss`, `paste` is `clipboard_paste`,
# `quit` is `sign_out` -- so only 20 of the 48 derive from the Material
# spelling, and a substring search invents false friends: `fireplace` for
# "replace", `briefcase` for "change case", `arrow_clockwise` for "lock". A
# name here is one somebody looked at, in the rendered 36 px 1-bit form.
#
# ⚠️ FIVE CONCEPTS ARE DELIBERATELY ABSENT, and each is a render verdict rather
# than a missing icon -- Fluent has all five. Measured on the contact sheet at
# the shipped size:
#   copy / paste   Material fills the front sheet and the clipboard body, which
#                  reads instantly; Fluent draws both as thin outlines that
#                  muddle into one shape at 36 px.
#   select all     Material's dashed marquee IS the conventional mark; Fluent
#                  draws a checkbox on a square, which reads as "done".
#   subscript /    Material's bold X-with-digit stays crisp; Fluent's thin
#   superscript    crossing strokes read as scissors once thresholded.
# Re-judge them by rendering, not by reading this list.
FLUENT_ICONS: dict[str, str] = {
    "alignment": "text_align_left", "bold": "text_bold", "bookmark": "bookmark",
    "change case": "text_change_case", "close": "dismiss", "comment": "comment",
    "cut": "cut", "delete": "delete", "down": "arrow_down", "find": "search",
    "find next": "search_square", "fullscreen": "full_screen_maximize",
    "go to": "location", "help": "question_circle",
    "indent": "text_indent_increase", "insert": "add", "italic": "text_italic",
    "hide": "eye_off",
    "left": "arrow_left", "lock": "lock_closed", "minimize": "arrow_minimize",
    "new": "document_add", "open": "folder_open",
    "outdent": "text_indent_decrease", "paint": "paint_brush",
    "paragraph": "text_paragraph", "print": "print", "quit": "sign_out",
    "redo": "arrow_redo", "reload": "arrow_sync", "replace": "arrow_swap",
    "right": "arrow_right", "save": "save", "save as": "save_edit",
    "settings": "settings", "share": "share", "styles": "color",
    "underline": "text_underline", "undo": "arrow_undo", "up": "arrow_up",
    "window": "window", "wrap text": "text_wrap", "zoom in": "zoom_in",
    "zoom out": "zoom_out",
}


def icon_for(concept: str) -> str:
    """The QUALIFIED catalog name for a concept — `fluent:copy`, `material:save`.

    Fluent first because it is the house style every hand-made template already
    draws from, so a generic app and a templated one put the same picture on the
    same key. Material is the fall-back for what Fluent lacks and the override
    for the five concepts it loses at 36 px (see FLUENT_ICONS).

    Returns "" for a concept with no catalog icon at all, which `plan_report`
    already refuses.
    """
    stem = FLUENT_ICONS.get(concept)
    if stem:
        return f"fluent:{stem}"
    entry = LEXICON.get(concept)
    material = entry[1] if entry else ""
    return f"material:{material}" if material else ""


# Longest phrase first so "save as" beats "save"; ties broken alphabetically so
# the table order cannot silently decide a match.
_PHRASES: list[tuple[str, str]] = sorted(
    ((phrase, concept) for concept, (_, _, phrases) in LEXICON.items()
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


_HINTS_CACHE: dict[str, str] | None = None
SUPPRESS = "text"


def default_hints_path() -> str:
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "res", "shortcut_hints.yaml")


def load_hints(path: str | None = None) -> dict[str, str]:
    """The curated label -> glyph overrides, keyed on the NORMALIZED label.

    Cached, because match() is called per shortcut per application. Missing or
    unparseable file yields {} -- the hints are an improvement on the rules, never
    a prerequisite for them, so the mapper must work with none.
    """
    global _HINTS_CACHE
    explicit = path is not None
    if not explicit and _HINTS_CACHE is not None:
        return _HINTS_CACHE
    out: dict[str, str] = {}
    try:
        import yaml
        with open(path or default_hints_path(), encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        for key, value in (raw.get("hints") or {}).items():
            out[normalize(str(key))] = str(value).strip()
    except Exception:
        out = {}
    if explicit:
        return out
    # ⚠️ Assign THEN return the global, rather than returning `out`. The two
    # sibling caches (`_RENDER_SETTINGS_CACHE`, `_LANG_FLAGS_CACHE`) are
    # written this way, and the difference is not
    # cosmetic: an assignment whose value is never read on its own path is what
    # CodeQL py/unused-global-variable reports, and deleting it on that advice
    # would silently disable the memo.
    _HINTS_CACHE = out
    return _HINTS_CACHE


def resolve_hint(value: str) -> int | None:
    """A hint value to a font-pack codepoint, if it names one."""
    value = value.strip()
    if value == SUPPRESS or value.startswith(ICON_PREFIX):
        return None
    if value.upper().startswith("U+"):
        try:
            return int(value[2:], 16)
        except ValueError:
            return None
    entry = LEXICON.get(value)
    return entry[0] if entry else None


def resolve_hint_icon(value: str) -> str:
    """A hint value to a CATALOG icon name, if it names one.

    ``icon:<name>`` is explicit rather than "any bare word we do not recognise",
    so a typo'd concept name still fails the lint in the tests instead of being
    silently taken for a catalog icon that does not exist.
    """
    value = value.strip()
    if value.startswith(ICON_PREFIX):
        return value[len(ICON_PREFIX):].strip()
    entry = LEXICON.get(value)
    return entry[1] if entry else ""


def hint_is_valid(value: str) -> bool:
    """Whether a hint file value names something -- the lint the tests apply."""
    value = value.strip()
    return (value == SUPPRESS or bool(resolve_hint_icon(value))
            or resolve_hint(value) is not None)


def suppressed(label: str, hints: dict[str, str] | None = None) -> bool:
    """True when a hint says this label should draw its text, deliberately.

    match() returns None for "no icon found" and for "no icon wanted" alike, and
    the caller needs to tell them apart: only the first belongs in the review
    queue. A label that keeps resurfacing after somebody decided it is text is a
    queue nobody will keep reading.
    """
    hints = load_hints() if hints is None else hints
    return hints.get(normalize(label), "").strip() == SUPPRESS


ICON_PREFIX = "icon:"


@dataclass(frozen=True)
class IconMatch:
    """A concept, and the two ways it can be drawn.

    `codepoint` is a glyph already on the keyboard (None when the concept has
    none); `icon` is a catalog name to fetch. A caller prefers the codepoint when
    it has one -- it needs no network -- and falls back to the name.
    """
    codepoint: int | None
    concept: str
    confidence: float
    rule: str
    icon: str = ""

    @property
    def char(self) -> str:
        return chr(self.codepoint) if self.codepoint is not None else ""


def match(label: str, min_confidence: float = 0.6, allow_fuzzy: bool = False,
          hints: dict[str, str] | None = None) -> IconMatch | None:
    """Best glyph for a label, or None when nothing clears `min_confidence`.

    Four rules, tried in descending confidence. The confidence is the point: a
    caller that gets 1.0 should draw the icon, and one that gets 0.62 is better
    off drawing the label text. Returning a single best guess with no score
    would make those indistinguishable.
    """
    text = normalize(label)
    if not text:
        return None

    # 0. A curated hint always wins -- it exists precisely because the rules got
    #    this label wrong or missed it, so letting a rule override it would make
    #    the review loop unable to correct anything.
    hint = (load_hints() if hints is None else hints).get(text)
    if hint is not None:
        if hint.strip() == SUPPRESS:
            return None
        cp, icon = resolve_hint(hint), resolve_hint_icon(hint)
        if cp is None and not icon:
            return None                      # unknown value; the lint catches it
        return IconMatch(cp, hint, 1.0, "hint", icon)

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
                         0.95 if hit.rule == "exact" else 0.85, "spelling",
                         hit.icon)

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
        return _for(best_concept, round(best_ratio, 3), "fuzzy")
    return None


def _for(concept: str, confidence: float, rule: str) -> IconMatch:
    codepoint, icon, _ = LEXICON[concept]
    return IconMatch(codepoint, concept, confidence, rule, icon)


def _literal_rules(text: str, table=None) -> IconMatch | None:
    """Exact phrase, then contained phrase, then single keyword -- no scoring."""
    table = _PHRASES if table is None else table
    for phrase, concept in table:
        if text == phrase:
            return _for(concept, 1.0, "exact")
    for phrase, concept in table:
        parts = phrase.split()
        if len(parts) > 1 and _contains_sequence(text.split(), parts):
            return _for(concept, 0.9, "phrase")
    # ⚠️ The EARLIEST matching word in the label wins, not the first matching
    # phrase in the table. A menu label is imperative -- the verb leads and the
    # rest is its object -- so "Hide App Store" is a hide, and taking the table's
    # order instead made it a SAVE (the "store" phrase sorts ahead of "hide"
    # because it is one character longer, which is as arbitrary a decider as the
    # table order the sort comment set out to remove). Two DIFFERENT one-word
    # phrases are two different words, so they can never share a position and
    # there is no tie to break -- a label with one matching word is unaffected.
    positions: dict[str, int] = {}
    for index, word in enumerate(text.split()):
        positions.setdefault(word, index)
    best_at, best_concept = None, None
    for phrase, concept in table:
        if " " in phrase:
            continue
        at = positions.get(phrase)
        if at is not None and (best_at is None or at < best_at):
            best_at, best_concept = at, concept
    if best_concept is not None:
        return _for(best_concept, 0.75, "keyword")
    return None


def _contains_sequence(haystack: list[str], needle: list[str]) -> bool:
    """True when `needle` appears as consecutive whole words in `haystack`."""
    n = len(needle)
    return any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


# ---------------------------------------------------------------------------
# Derived names: the no-config fall-back for a label the lexicon has never seen
# ---------------------------------------------------------------------------
#
# ⚠️ A FALL-BACK, not a replacement, and the measurement is why. Over 46 real
# menu labels the lexicon resolves 41 and derivation alone 46 -- so on RECALL
# derivation wins outright, and replacing the table would still be wrong. The
# lexicon is a PRECISION layer: it holds the chosen icon for a label somebody
# looked at, where derivation takes the first catalog name that happens to
# exist. Both resolve "Add Layer"; derivation answers `add`, which is a true hit
# and a worse keycap. Hit-counting cannot tell those apart, and this repo's rule
# is that a wrong icon is worse than none.
#
# So: the lexicon answers where it has an opinion, and this covers the tail --
# which is the point, because a label nobody has curated now gets an icon with
# no config entry at all. The five it rescued on that sample were Rotate, Crop,
# Export as PDF, Import and Toggle Sidebar.
#
# ⚠️ NOTHING HERE VALIDATES A NAME. These are candidates; the caller keeps the
# first one the fetched codepoint table actually carries, exactly as
# `app_icons.candidates()` leaves the catalog's own 404 to reject a bad slug.
# Guessing and verifying are deliberately different jobs in different places.

# Material Symbols groups a lot of its set behind a category prefix, so the bare
# English word misses: `copy` is `content_copy`, `bold` is `format_bold`, `open`
# is `file_open`. Measured -- a direct name lookup resolves 16 of those 46
# labels, and these five prefixes take it to 33.
NAME_PREFIXES = ("", "content_", "format_", "file_", "text_")

# ⚠️ A QUOTED run in a menu label is the user's OBJECT, not part of the command.
# macOS puts the selected item's name there -- `Quick Look "Chess"`,
# `Slideshow "Holiday"` -- so deriving from it names whatever happens to be
# selected: a folder called Chess drew a chess piece on Quick Look (field,
# 2026-09-21). Only DOUBLE quotes, curly or straight: the curly single quote is
# how macOS spells an apostrophe ("Don't Save"), so pairing on it would eat the
# words between two ordinary contractions.
_QUOTED_OBJECT = re.compile(r'[\u201c"][^\u201c\u201d"]{0,80}[\u201d"]')

# Words that carry no icon of their own, dropped before the join. "Toggle" is
# here because a toggle is not a picture: the icon belongs to what is toggled.
# ⚠️ "hide" was here and must NOT come back: a word the LEXICON names as a
# concept is by definition not filler. Stripping it made the app's own name the
# HEAD word, so `derive_names("Hide Terminal")` answered `terminal` -- the thing
# the key hides rather than the thing it does. "show" and "toggle" stay because
# neither is a concept: "Show Sidebar" really is a sidebar.
FILLER_WORDS = frozenset((
    "this", "page", "the", "a", "as", "to", "toggle", "show", "all",
))

# Where the catalog's word is simply a different word. Each target was checked
# against the shipped codepoint table rather than assumed -- these are the 13
# that closed the gap from 33 to 46.
NAME_SYNONYMS = {
    "find": "search",
    "replace": "find_replace",
    "quit": "logout",
    "preferences": "settings",
    "reload": "refresh",
    "duplicate": "content_copy",
    "rotate": "rotate_right",
    "import": "file_download",
    "about": "info",
    "underline": "format_underlined",
    "split": "splitscreen",
    "sidebar": "side_navigation",
    "next": "navigate_next",
}


def app_words(app: str | None) -> frozenset:
    """The words of the focused application's own name.

    ⚠️ A derivation must never answer with one. The ESC mark already carries
    the app's icon, so drawing it again on a letter key says nothing about what
    the key does -- and it is what the label's object usually IS on macOS, where
    every app puts "Hide <AppName>" on Cmd+H. Terminal drew a terminal, App
    Store a shop, Chess a chess piece (field, 2026-09-21).
    """
    return frozenset(w for w in normalize(app or "").split() if w)


def derive_names(label: str, app: str | None = None) -> list[str]:
    """Candidate Material Symbols names for `label`, best guess first.

    Ordered most-specific to least: the whole label, then the label without
    filler, then a synonym for any word the catalog names differently, and only
    then a single head or tail word. That tail is where a generic answer comes
    from (`Add Layer` -> `add`), so it sorts last and the lexicon gets to answer
    before any of it runs.

    `app` is the focused application, and every candidate naming it is dropped
    -- see `app_words`. That rejection is what lets the tail stay unconditional:
    an earlier fix suppressed the tail whenever the head was a lexicon concept,
    which blocked the app name but also cost `Show Previous Tab` its `tab` and
    `Mark as Bookmark` its `bookmark`.
    """
    label = _QUOTED_OBJECT.sub(" ", label)
    words = [w for w in normalize(label).split() if w]
    if not words:
        return []
    out: list[str] = []

    def add(name):
        if name and name not in out:
            out.append(name)

    kept = [w for w in words if w not in FILLER_WORDS] or words
    for group in (words, kept):
        joined = "_".join(group)
        for prefix in NAME_PREFIXES:
            add(prefix + joined)
    add("".join(kept))                      # findnext, fullscreen
    for word in kept:
        if word in NAME_SYNONYMS:
            add(NAME_SYNONYMS[word])
    for prefix in NAME_PREFIXES:
        add(prefix + kept[0])
    if len(kept) > 1:
        for prefix in NAME_PREFIXES:
            add(prefix + kept[-1])
    # ⚠️ Filtered at the END rather than per candidate, so a PREFIXED form of the
    # app's name goes too: `content_terminal` names the app exactly as much as
    # `terminal` does. The head is offered before the tail, so on an ordinary
    # label this drops nothing -- "New Mail" in Mail still derives `new`, which
    # already outranks `mail`.
    blocked = app_words(app)
    if blocked:
        out = [n for n in out
               if not any(n == prefix + word
                          for prefix in NAME_PREFIXES for word in blocked)]
    return out
