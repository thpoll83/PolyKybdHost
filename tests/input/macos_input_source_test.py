"""Selftests for the macOS input-source matching (no macOS needed).

The ctypes half of `macos_input_source` cannot run here; what CAN be pinned
offline is the decision it feeds — which of the enabled sources a keyboard
`lang`/`country` resolves to. That is where the regression lived: the old
helper compared a keyboard code against a localized layout NAME and so never
matched anything."""

import ctypes
import importlib
import unittest

from polyhost.input.macos_input_source import (
    normalize_tag, pick_input_source, tag_for_source)
from polyhost.lang.lang_compat import LangComp


def src(ident, name, languages, selectable=True):
    return {"id": f"com.apple.keylayout.{ident}", "name": name,
            "languages": list(languages), "selectable": selectable}


US = src("US", "U.S.", ["en"])
BRITISH = src("British", "British", ["en"])
DVORAK = src("Dvorak", "Dvorak", ["en"])
GERMAN = src("German", "German", ["de"])
AUSTRIAN = src("Austrian", "Austrian", ["de"])
SWISS_DE = src("SwissGerman", "Swiss German", ["de"])
FRENCH = src("French", "French", ["fr"])
BRAZILIAN = src("Brazilian", "Brazilian", ["pt"])
PORTUGUESE = src("Portuguese", "Portuguese", ["pt"])


class NormalizeTagTest(unittest.TestCase):
    def test_keyboard_code_halves_become_a_tag(self):
        self.assertEqual(normalize_tag("de", "DE"), "de-DE")

    def test_a_stray_separator_from_the_debug_menu_is_stripped(self):
        # get_lang_and_country("en-US") hands back ("en", "-US"); without the
        # strip this became "en--US" and matched nothing.
        self.assertEqual(normalize_tag("en", "-US"), "en-US")

    def test_missing_country_leaves_a_bare_language(self):
        self.assertEqual(normalize_tag("de", ""), "de")


class PickInputSourceTest(unittest.TestCase):
    def test_language_match_is_the_baseline(self):
        self.assertIs(pick_input_source([US, GERMAN], "de", "DE"), GERMAN)

    def test_country_hint_separates_two_sources_of_one_language(self):
        # Both report ("en",) — only the hint table can tell them apart.
        self.assertIs(pick_input_source([BRITISH, US], "en", "US"), US)
        self.assertIs(pick_input_source([US, BRITISH], "en", "GB"), BRITISH)

    def test_hint_miss_falls_back_to_the_first_language_match(self):
        # No hint entry names Dvorak, and en-AU has no entry at all: the right
        # language still wins rather than the call failing.
        self.assertIs(pick_input_source([DVORAK], "en", "AU"), DVORAK)

    def test_austrian_prefers_its_own_layout_then_german(self):
        self.assertIs(pick_input_source([GERMAN, AUSTRIAN], "de", "AT"), AUSTRIAN)
        self.assertIs(pick_input_source([SWISS_DE, GERMAN], "de", "AT"), GERMAN)

    def test_regional_variants_do_not_cross_languages(self):
        self.assertIs(pick_input_source([BRAZILIAN, PORTUGUESE], "pt", "BR"), BRAZILIAN)
        self.assertIs(pick_input_source([BRAZILIAN, PORTUGUESE], "pt", "PT"), PORTUGUESE)

    def test_an_exact_region_tag_beats_the_hint_table(self):
        regional = src("Foo", "Foo", ["en-GB"])
        self.assertIs(pick_input_source([US, regional], "en", "GB"), regional)

    def test_no_source_for_the_language_is_a_miss_not_a_wrong_pick(self):
        # The caller turns this into "enable the layout in System Settings";
        # silently selecting US here would type the wrong characters.
        self.assertIsNone(pick_input_source([US, GERMAN], "ja", "JP"))

    def test_a_source_that_refuses_selection_is_skipped(self):
        locked = src("Locked", "Locked", ["de"], selectable=False)
        self.assertIs(pick_input_source([locked, GERMAN], "de", "DE"), GERMAN)
        self.assertIsNone(pick_input_source([locked], "de", "DE"))

    def test_a_secondary_language_matches_when_no_primary_does(self):
        ime = src("Multi", "Multi", ["zh-Hans", "ja"])
        self.assertIs(pick_input_source([US, ime], "ja", "JP"), ime)

    def test_empty_language_never_guesses(self):
        self.assertIsNone(pick_input_source([US, GERMAN], "", "DE"))


class TagForSourceTest(unittest.TestCase):
    def test_primary_language_is_the_tag(self):
        self.assertEqual(tag_for_source(GERMAN), "de")

    def test_a_source_without_languages_has_no_tag(self):
        self.assertIsNone(tag_for_source(src("Braille", "Braille", [])))
        self.assertIsNone(tag_for_source(None))


SPANISH = src("Spanish-ISO", "Spanish - ISO", ["es"])
LATAM = src("LatinAmerican", "Latin American", ["es"])
NORWEGIAN = src("Norwegian", "Norwegian", ["nb"])
DANISH = src("Danish", "Danish", ["da"])
SWISS_FR = src("SwissFrench", "Swiss French", ["fr"])
ZHUYIN = {"id": "com.apple.inputmethod.TCIM.Zhuyin", "name": "Zhuyin",
          "languages": ["zh-Hant"], "selectable": True}


class CompatibleLayoutFallbackTest(unittest.TestCase):
    """Folding onto a compatible layout when macOS has no source for the
    language itself.

    Roughly 60 of the 156 PolyKybd layouts are folds, and macOS ships an input
    source for none of those languages — so without this the keyboard's
    Tahitian, Filipino, Quechua or Basque key reports "no enabled input
    source" on a Mac that has exactly the right layout enabled."""

    def alternatives(self, country):
        """The real macOS file, through the real reader."""
        return LangComp("macos").get_compatible_lang_list(country)

    def test_the_macos_file_covers_every_country_the_linux_one_does(self):
        """The parity check no `cmp` can do — the two files are counterparts,
        not copies, so only their KEY SETS line up.

        A fold added to the Linux file for a new language and not mirrored
        here is invisible: that language would report "no enabled input
        source" on a Mac that has exactly the right layout, with nothing to
        say why. macOS is allowed extra keys (`es`, `gb`, `ch`, `us` — the
        countries Linux resolves natively through the country code), so the
        check is one-directional."""
        linux = set(LangComp("linux").mapping)
        macos = set(LangComp("macos").mapping)
        self.assertTrue(linux, "the Linux file parsed to nothing")
        missing = sorted(linux - macos)
        self.assertEqual(missing, [],
                         f"forced_country_match_linux.txt has folds for "
                         f"countries the macOS file does not: {missing}")

    def test_the_macos_file_states_language_tags_not_xkb_codes(self):
        """The two vocabularies are the reason for two files, and nothing but
        this notices if a Linux-shaped value is pasted into the macOS one.

        `ara` and `latam` are the tell: they are xkb layout names, not
        languages, so they would match no input source and simply be skipped —
        the fold would go quiet rather than fail."""
        xkb_only = {"ara", "latam"}
        for country, tags in LangComp("macos").mapping.items():
            for tag in tags:
                with self.subTest(country=country, tag=tag):
                    self.assertNotIn(tag, xkb_only,
                                     f"{country}={tag} is an xkb layout code, "
                                     f"not a language tag")
                    # LangComp lower-cases what it reads, so the region
                    # arrives as "en-gb"; the matcher re-normalises it. The
                    # file itself is written in proper IETF casing.
                    self.assertRegex(tag, r"^[a-z]{2}(-[a-z]{2})?$")

    def test_the_fold_walk_is_one_level_deep_by_construction(self):
        """Step 4 recurses, and the bound is structural rather than a table
        invariant: the inner call is made WITHOUT alternatives, so its own
        step 4 has nothing to walk. A cycle would hang the thread that called
        it — on macOS the Qt main thread, mid-keypress — so it is worth
        pinning rather than reading off the code."""
        depth = {"now": 0, "max": 0}
        real = pick_input_source

        def counting(sources, lang, country, alternatives=None):
            depth["now"] += 1
            depth["max"] = max(depth["max"], depth["now"])
            try:
                return real(sources, lang, country, alternatives)
            finally:
                depth["now"] -= 1

        # importlib, not `import … as`: the module is already pulled in with
        # `from … import` at the top, and having both forms is what CodeQL
        # alert 358 named. The other fixtures here reach for the module the
        # same way.
        mis = importlib.import_module("polyhost.input.macos_input_source")
        self.addCleanup(setattr, mis, "pick_input_source", real)
        mis.pick_input_source = counting
        # `se-NO` with NOTHING enabled, so the whole walk is explored: two
        # alternatives, the first of which is the pair already in hand. A
        # single-alternative country cannot tell the two shapes apart — its
        # one candidate is skipped by the equality guard either way.
        counting([], "se", "NO", self.alternatives("NO"))
        self.assertLessEqual(depth["max"], 2,
                             f"recursed {depth['max']} levels deep")

    def test_tahitian_folds_onto_french(self):
        # ty-PF: no macOS source speaks Tahitian; the file says pf=fr-FR.
        self.assertEqual(self.alternatives("PF"), ["fr-fr"])
        self.assertIs(pick_input_source([US, FRENCH], "ty", "PF",
                                        self.alternatives("PF")), FRENCH)

    def test_filipino_folds_onto_us(self):
        self.assertIs(pick_input_source([FRENCH, US], "tl", "PH",
                                        self.alternatives("PH")), US)

    def test_quechua_folds_onto_the_latin_american_layout(self):
        self.assertIs(pick_input_source([US, LATAM], "qu", "PE",
                                        self.alternatives("PE")), LATAM)

    def test_basque_folds_onto_spanish_through_its_own_country(self):
        """The LINUX file has no `es=` line — there ES resolves natively
        through the country code. macOS has no country concept to resolve
        through, so its own file states the mapping outright."""
        self.assertIsNone(LangComp("linux").get_compatible_lang_list("ES"))
        self.assertEqual(self.alternatives("ES"), ["es-es"])
        self.assertIs(pick_input_source([US, SPANISH], "eu", "ES",
                                        self.alternatives("ES")), SPANISH)

    def test_welsh_folds_onto_british_through_its_own_country(self):
        self.assertIsNone(LangComp("linux").get_compatible_lang_list("GB"))
        self.assertEqual(self.alternatives("GB"), ["en-gb"])
        self.assertIs(pick_input_source([US, BRITISH], "cy", "GB",
                                        self.alternatives("GB")), BRITISH)

    def test_romansh_folds_onto_swiss_german(self):
        self.assertIs(pick_input_source([SWISS_FR, SWISS_DE], "rm", "CH",
                                        self.alternatives("CH")), SWISS_DE)

    def test_northern_sami_takes_its_country_before_the_res_file_fold(self):
        """`se-NO`: the file folds NO onto `dk`, but the Norwegian layout is
        the one the user actually has. The country is tried first for exactly
        this case — the file's folds are what to do when it is absent."""
        self.assertEqual(self.alternatives("NO"), ["nb-no", "da-dk"])
        self.assertIs(pick_input_source([DANISH, NORWEGIAN], "se", "NO",
                                        self.alternatives("NO")), NORWEGIAN)
        # …and the file's fold still applies when it really is absent.
        self.assertIs(pick_input_source([DANISH], "se", "NO",
                                        self.alternatives("NO")), DANISH)

    def test_a_real_language_match_beats_every_fold(self):
        """zh-TW is folded onto `us` for Linux, because the xkb `tw` layout is
        not Latin. macOS has a Zhuyin IME, and matching the language first is
        what picks the IME the user installed instead of a US QWERTY."""
        self.assertEqual(self.alternatives("TW"), ["en-us"])
        self.assertIs(pick_input_source([US, ZHUYIN], "zh", "TW",
                                        self.alternatives("TW")), ZHUYIN)

    def test_a_fold_that_is_not_enabled_is_still_a_miss(self):
        # Nothing Tahitian, nothing French: refuse rather than type German.
        self.assertIsNone(pick_input_source([GERMAN], "ty", "PF",
                                            self.alternatives("PF")))

    def test_no_alternatives_and_no_country_entry_is_a_miss(self):
        self.assertIsNone(pick_input_source([US, GERMAN], "ja", "JP", None))


class FakeCoreFoundation:
    """Enough of CoreFoundation + Carbon to drive the ctypes bridge offline.

    Pointers are small ints indexing three tables. The point is not to model
    macOS — it is to run the bridge's own loops (the category filter, the
    property reads, the select re-find and the CFRelease) where a real macOS
    cannot be had, the same way `pick_input_source` is pinned above."""

    def __init__(self, sources, current=None):
        self.strings = {}
        self.arrays = {}
        self.props = {}
        self.released = []
        self.selected = []
        self.select_status = 0
        self._next = 100
        self.globals = {}
        for name in ("kTISPropertyInputSourceID", "kTISPropertyLocalizedName",
                     "kTISPropertyInputSourceLanguages",
                     "kTISPropertyInputSourceCategory",
                     "kTISPropertyInputSourceIsSelectCapable",
                     "kCFBooleanTrue", "kCFBooleanFalse"):
            self.globals[name] = self._alloc()
        self.globals["kTISCategoryKeyboardInputSource"] = self._str(
            "TISCategoryKeyboardInputSource")
        self.list_ptr = self._array([self._source(s) for s in sources])
        self.current_ptr = self._source(current) if current else 0

    def _alloc(self):
        self._next += 1
        return self._next

    def _str(self, text):
        ptr = self._alloc()
        self.strings[ptr] = text
        return ptr

    def _array(self, items):
        ptr = self._alloc()
        self.arrays[ptr] = list(items)
        return ptr

    def _source(self, spec):
        ptr = self._alloc()
        g = self.globals
        props = {
            g["kTISPropertyInputSourceID"]: self._str(spec["id"]),
            g["kTISPropertyLocalizedName"]: self._str(spec["name"]),
            g["kTISPropertyInputSourceLanguages"]: self._array(
                [self._str(l) for l in spec["languages"]]),
            g["kTISPropertyInputSourceCategory"]: self._str(
                spec.get("category", "TISCategoryKeyboardInputSource")),
            g["kTISPropertyInputSourceIsSelectCapable"]:
                g["kCFBooleanTrue"] if spec.get("selectable", True)
                else g["kCFBooleanFalse"],
        }
        self.props[ptr] = props
        return ptr

    # --- the entry points the bridge calls -------------------------------
    @staticmethod
    def _addr(ptr):
        return ptr.value if hasattr(ptr, "value") else ptr

    def CFArrayGetCount(self, ptr):
        return len(self.arrays.get(self._addr(ptr), ()))

    def CFArrayGetValueAtIndex(self, ptr, index):
        return self.arrays[self._addr(ptr)][index]

    def CFStringGetCString(self, ptr, buf, size, _encoding):
        text = self.strings.get(self._addr(ptr))
        if text is None:
            return False
        raw = text.encode("utf-8") + b"\0"
        if len(raw) > size:
            return False
        ctypes.memmove(buf, raw, len(raw))
        return True

    def CFRelease(self, ptr):
        self.released.append(self._addr(ptr))

    def TISCreateInputSourceList(self, _properties, _all_installed):
        return self.list_ptr

    def TISCopyCurrentKeyboardInputSource(self):
        return self.current_ptr

    def TISGetInputSourceProperty(self, src, key):
        return self.props.get(self._addr(src), {}).get(self._addr(key))

    def TISSelectInputSource(self, src):
        self.selected.append(self._addr(src))
        return self.select_status


class BridgeFlowTest(unittest.TestCase):
    """The ctypes bridge's own loops, against the fake above."""

    SOURCES = [
        {"id": "com.apple.keylayout.US", "name": "U.S.", "languages": ["en"]},
        {"id": "com.apple.keylayout.German", "name": "German", "languages": ["de"]},
        {"id": "com.apple.CharacterPaletteIM", "name": "Emoji",
         "languages": ["en"], "category": "TISCategoryPaletteInputSource"},
    ]

    def _install(self, fake):
        mis = importlib.import_module("polyhost.input.macos_input_source")
        self.addCleanup(setattr, mis, "_load", mis._load)
        self.addCleanup(setattr, mis, "_global_string", mis._global_string)
        mis._load = lambda: (fake, fake)
        mis._global_string = lambda _lib, name: fake.globals.get(name)
        return mis

    def test_only_keyboard_sources_are_listed(self):
        fake = FakeCoreFoundation(self.SOURCES)
        mis = self._install(fake)
        sources, error = mis.list_input_sources()
        self.assertIsNone(error)
        # The emoji palette is a selectable input source but not a keyboard
        # layout; listing it would offer a "language" that types nothing.
        self.assertEqual([s["id"] for s in sources],
                         ["com.apple.keylayout.US", "com.apple.keylayout.German"])
        self.assertEqual(sources[1]["languages"], ["de"])
        self.assertTrue(sources[1]["selectable"])

    def test_the_created_list_is_released(self):
        fake = FakeCoreFoundation(self.SOURCES)
        mis = self._install(fake)
        mis.list_input_sources()
        # TISCreateInputSourceList follows the CF create rule; the enumeration
        # runs on every language change, so a leak here is unbounded.
        self.assertIn(fake.list_ptr, fake.released)

    def test_select_finds_the_source_by_id(self):
        fake = FakeCoreFoundation(self.SOURCES)
        mis = self._install(fake)
        selected, error = mis.select_input_source("com.apple.keylayout.German")
        self.assertTrue(selected)
        self.assertIsNone(error)
        self.assertEqual(len(fake.selected), 1)
        self.assertIn(fake.list_ptr, fake.released)

    def test_a_nonzero_osstatus_is_a_failure_not_a_success(self):
        fake = FakeCoreFoundation(self.SOURCES)
        fake.select_status = -50
        mis = self._install(fake)
        selected, reason = mis.select_input_source("com.apple.keylayout.German")
        self.assertFalse(selected)
        self.assertIn("-50", reason)

    def test_selecting_a_source_that_is_no_longer_enabled_fails(self):
        fake = FakeCoreFoundation(self.SOURCES)
        mis = self._install(fake)
        selected, reason = mis.select_input_source("com.apple.keylayout.Greek")
        self.assertFalse(selected)
        self.assertIn("Greek", reason)
        self.assertEqual(fake.selected, [])

    def test_a_failure_returns_the_VALUE_TYPE_not_a_reason_string(self):
        """Every entry point answers `(value, error)`, and the value's type
        never depends on the error.

        The repo's usual `(ok, value_or_reason)` tuple hands the caller a
        STRING to iterate on the failure path the moment the flag is read
        wrongly — CodeQL alert 357 against the first revision of this PR, on
        `for source in result` in `get_languages`. Pinning the type here is
        what stops the shape drifting back."""
        mis = importlib.import_module("polyhost.input.macos_input_source")
        self.addCleanup(setattr, mis, "_load", mis._load)
        mis._load = lambda: None

        sources, error = mis.list_input_sources()
        self.assertIsInstance(sources, list)
        self.assertEqual(sources, [])
        self.assertIn("unavailable", error)

        source, error = mis.current_input_source()
        self.assertIsNone(source)
        self.assertIn("unavailable", error)

    def test_current_input_source_reads_the_copied_source(self):
        fake = FakeCoreFoundation(
            self.SOURCES,
            current={"id": "com.apple.keylayout.German", "name": "German",
                     "languages": ["de"]})
        mis = self._install(fake)
        source, error = mis.current_input_source()
        self.assertIsNone(error)
        self.assertEqual(mis.tag_for_source(source), "de")
        self.assertIn(fake.current_ptr, fake.released)


class HelperTest(unittest.TestCase):
    """`MacOSInputHelper` on top of the same fake."""

    def _helper(self, fake):
        mis = importlib.import_module("polyhost.input.macos_input_source")
        self.addCleanup(setattr, mis, "_load", mis._load)
        self.addCleanup(setattr, mis, "_global_string", mis._global_string)
        mis._load = lambda: (fake, fake)
        mis._global_string = lambda _lib, name: fake.globals.get(name)
        from polyhost.input.macos_helper import MacOSInputHelper
        return MacOSInputHelper()

    def test_set_language_selects_the_matching_source(self):
        fake = FakeCoreFoundation(BridgeFlowTest.SOURCES)
        helper = self._helper(fake)
        ok, result = helper.set_language("de", "DE")
        self.assertTrue(ok)
        self.assertEqual(result, "de")
        self.assertEqual(len(fake.selected), 1)

    def test_set_language_folds_through_the_compat_file(self):
        """End to end through the real helper, not just the pure matcher: it
        must actually consult `LangComp`. Tahitian has no macOS input source;
        `res/forced_country_match_macos.txt` says `pf=fr-FR`."""
        fake = FakeCoreFoundation([
            {"id": "com.apple.keylayout.French", "name": "French",
             "languages": ["fr"]},
        ])
        helper = self._helper(fake)
        ok, result = helper.set_language("ty", "PF")
        self.assertTrue(ok, result)
        self.assertEqual(len(fake.selected), 1)

    def test_set_language_reads_the_MACOS_table_not_the_linux_one(self):
        """Most folds survive reading the wrong file by coincidence — `pf=fr`
        is a valid language tag as well as an xkb code — so the helper must be
        checked on a country only the macOS file answers for. `es` is one:
        the Linux file has no such key at all."""
        fake = FakeCoreFoundation([
            {"id": "com.apple.keylayout.Spanish-ISO", "name": "Spanish - ISO",
             "languages": ["es"]},
        ])
        helper = self._helper(fake)
        ok, result = helper.set_language("eu", "ES")   # Basque
        self.assertTrue(ok, result)
        self.assertEqual(len(fake.selected), 1)

    def test_a_missing_language_names_what_was_enabled(self):
        fake = FakeCoreFoundation(BridgeFlowTest.SOURCES)
        helper = self._helper(fake)
        ok, reason = helper.set_language("el", "GR")
        self.assertFalse(ok)
        self.assertIn("el-GR", reason)
        self.assertIn("U.S.", reason)       # the fix is in System Settings
        self.assertEqual(fake.selected, [])

    def test_get_languages_lists_the_enabled_tags_once(self):
        fake = FakeCoreFoundation(BridgeFlowTest.SOURCES)
        helper = self._helper(fake)
        self.assertEqual(helper.get_languages(), ["en", "de"])

    def test_current_language_is_the_same_namespace_set_language_takes(self):
        # The old helper answered "German" here and "de-DE" there, so the
        # comparison in PolyHost could never be equal and the switch re-fired
        # on every probe.
        fake = FakeCoreFoundation(
            BridgeFlowTest.SOURCES,
            current={"id": "com.apple.keylayout.German", "name": "German",
                     "languages": ["de"]})
        helper = self._helper(fake)
        ok, current = helper.get_current_language()
        self.assertTrue(ok)
        _, applied = helper.set_language("de", "DE")
        self.assertEqual(current, applied)


if __name__ == "__main__":
    unittest.main()
