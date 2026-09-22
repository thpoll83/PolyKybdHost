"""macOS input-source switching through Text Input Source Services (TIS).

⚠️ **`languagesetup` is not this.** Until now `MacOSInputHelper.set_language()`
ran ``sudo languagesetup -langspec de-DE`` through osascript *"with
administrator privileges"*. That command sets the **system UI language** — the
language of menus and dialogs — which is not what a language key on the
keyboard asks for, needs a password dialog on every single call, and takes
effect at the next login rather than now. What the keyboard means is *"select
the German input source"*, and that is `TISSelectInputSource`: no privileges,
no dialog, effective immediately.

**No new dependency and no pyobjc.** The TIS entry points live in
Carbon/HIToolbox, which pyobjc does not wrap, so they are called through
`ctypes`; their CoreFoundation return values are unwrapped through `ctypes`
against CoreFoundation as well, rather than by bridging into pyobjc. Both
frameworks are part of macOS itself.

⚠️ **UNMEASURED ON REAL HARDWARE.** The matching half (`pick_input_source` and
its table) is selftested offline in `tests/input/macos_input_source_test.py`;
the four ctypes calls below have never run against a live macOS. Read a first
success as one sample, not as coverage. Nothing here raises — every entry point
returns a reason string instead, because the caller is a tray app reacting to a
keypress.

**What TIS can and cannot do.** `TISSelectInputSource` only selects a source
the user has already **enabled** in System Settings → Keyboard → Input Sources;
it cannot add one. So "the language is present" is a precondition the host
cannot create, and a miss is reported with the enabled list so the log says
which sources were actually on offer.
"""

from __future__ import annotations

import ctypes

_CF_PATH = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
_CARBON_PATH = "/System/Library/Frameworks/Carbon.framework/Carbon"

_UTF8 = 0x08000100          # kCFStringEncodingUTF8
_KEYBOARD_CATEGORY = "TISCategoryKeyboardInputSource"

#: Disambiguation hints, keyed by the PolyKybd ``(lang, country)`` pair and
#: listing input-source ID suffixes (the part after ``com.apple.keylayout.``)
#: in preference order.
#:
#: They are consulted ONLY to choose between sources that already match the
#: requested LANGUAGE, because macOS reports a layout's languages without a
#: region: "U.S.", "British" and "Dvorak" all answer ``("en",)`` and nothing in
#: the TIS metadata separates them. A missing or wrong entry therefore costs at
#: worst the wrong regional variant of the right language, never the wrong
#: language — which is why the table is allowed to be a handful of common cases
#: rather than a complete one.
_ID_HINTS = {
    ("en", "US"): ("US", "USExtended", "ABC"),
    ("en", "GB"): ("British", "British-PC"),
    ("de", "DE"): ("German", "German-DIN-2137"),
    ("de", "AT"): ("Austrian", "German"),
    ("de", "CH"): ("SwissGerman",),
    ("fr", "FR"): ("French", "French-numerical", "AZERTY"),
    ("fr", "CH"): ("SwissFrench",),
    ("fr", "CA"): ("Canadian-CSA", "CanadianFrench"),
    ("fr", "BE"): ("Belgian",),
    ("nl", "BE"): ("Belgian",),
    ("nl", "NL"): ("Dutch",),
    ("it", "IT"): ("Italian-Pro", "Italian"),
    ("pt", "BR"): ("Brazilian",),
    ("pt", "PT"): ("Portuguese",),
    ("es", "ES"): ("Spanish-ISO", "Spanish"),
    ("es", "MX"): ("LatinAmerican",),
    ("sv", "SE"): ("Swedish-Pro", "Swedish"),
    ("nb", "NO"): ("Norwegian",),
    ("no", "NO"): ("Norwegian",),
}


# ----------------------------------------------------------------------
# Matching (pure — no macOS needed, and selftested)
# ----------------------------------------------------------------------

def normalize_tag(lang, country):
    """Build an IETF-ish tag from a PolyKybd ``lang``/``country`` pair.

    ⚠️ The country arrives from `get_lang_and_country`, which slices a 4-char
    keyboard code (``"deDE"``) — but the same helper is applied to debug-menu
    TEXT, where it can hand back ``"-US"`` or ``""``. Strip anything that is
    not a letter rather than trusting the caller, or ``"en--US"`` reaches the
    comparison and matches nothing."""
    lang = "".join(c for c in (lang or "") if c.isalpha()).lower()
    country = "".join(c for c in (country or "") if c.isalpha()).upper()
    return f"{lang}-{country}" if lang and country else lang


def _source_id_suffix(source_id):
    return (source_id or "").rsplit(".", 1)[-1]


def pick_input_source(sources, lang, country):
    """Choose the enabled input source that best matches ``lang``/``country``.

    ``sources`` is a list of dicts as `list_input_sources` returns them
    (``id``, ``name``, ``languages``, ``selectable``). Returns the chosen dict,
    or None when no enabled source speaks the language."""
    lang = "".join(c for c in (lang or "") if c.isalpha()).lower()
    country = "".join(c for c in (country or "") if c.isalpha()).upper()
    if not lang:
        return None
    tag = f"{lang}-{country}" if country else lang

    usable = [s for s in sources if s.get("selectable", True)]

    # 1. A source that names the full region tag. Rare (most layouts answer a
    #    bare language) but unambiguous when it happens. Compared in lower case
    #    on BOTH sides: the region half is upper case here and lower case in
    #    some sources' metadata, and a case-sensitive test silently fell
    #    through to the language match.
    tag_lower = tag.lower()
    for src in usable:
        if any((l or "").lower() == tag_lower for l in src.get("languages") or ()):
            return src

    # 2. Sources whose PRIMARY language is the one asked for, ordered by the
    #    hint table when it has something to say about this country.
    primary = [s for s in usable
               if ((s.get("languages") or [""])[0] or "")[:2].lower() == lang]
    if primary:
        for suffix in _ID_HINTS.get((lang, country), ()):
            for src in primary:
                if _source_id_suffix(src.get("id")) == suffix:
                    return src
        return primary[0]

    # 3. A source that lists the language anywhere (a multi-language IME).
    for src in usable:
        if any((l or "")[:2].lower() == lang for l in src.get("languages") or ()):
            return src
    return None


def tag_for_source(source):
    """The language tag a source reports, for comparison and for the menu."""
    if not source:
        return None
    langs = source.get("languages") or []
    return langs[0] if langs else None


# ----------------------------------------------------------------------
# The ctypes bridge (macOS only)
# ----------------------------------------------------------------------

_bridge = None          # (cf, carbon) once loaded
_bridge_error = None    # why it could not be loaded


def _load():
    """Load CoreFoundation + Carbon and pin the signatures. Never raises."""
    global _bridge, _bridge_error
    if _bridge is not None or _bridge_error is not None:
        return _bridge
    try:
        cf = ctypes.cdll.LoadLibrary(_CF_PATH)
        carbon = ctypes.cdll.LoadLibrary(_CARBON_PATH)

        # Pinning argtypes/restype is not optional: on 64-bit a pointer
        # returned through the default `int` restype is truncated, which is a
        # crash rather than a wrong answer.
        cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
        cf.CFArrayGetCount.restype = ctypes.c_long
        cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
        cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
        cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                          ctypes.c_long, ctypes.c_uint32]
        cf.CFStringGetCString.restype = ctypes.c_bool
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        cf.CFRelease.restype = None

        carbon.TISCreateInputSourceList.argtypes = [ctypes.c_void_p, ctypes.c_bool]
        carbon.TISCreateInputSourceList.restype = ctypes.c_void_p
        carbon.TISCopyCurrentKeyboardInputSource.argtypes = []
        carbon.TISCopyCurrentKeyboardInputSource.restype = ctypes.c_void_p
        carbon.TISGetInputSourceProperty.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        carbon.TISGetInputSourceProperty.restype = ctypes.c_void_p
        carbon.TISSelectInputSource.argtypes = [ctypes.c_void_p]
        carbon.TISSelectInputSource.restype = ctypes.c_int32

        _bridge = (cf, carbon)
    except (OSError, AttributeError) as ex:
        _bridge_error = f"{type(ex).__name__}: {ex}"
        _bridge = None
    return _bridge


def bridge_error():
    """The reason the TIS bridge is unusable, or None once it has loaded."""
    _load()
    return _bridge_error


def _cfstr(cf, ptr):
    """CFStringRef -> str (None for NULL or an undecodable string)."""
    if not ptr:
        return None
    buf = ctypes.create_string_buffer(1024)
    if not cf.CFStringGetCString(ctypes.c_void_p(ptr), buf, len(buf), _UTF8):
        return None
    return buf.value.decode("utf-8", "replace")


def _cfstr_list(cf, ptr):
    """CFArrayRef of CFStringRef -> list[str] ([] for NULL)."""
    if not ptr:
        return []
    out = []
    for i in range(cf.CFArrayGetCount(ctypes.c_void_p(ptr))):
        text = _cfstr(cf, cf.CFArrayGetValueAtIndex(ctypes.c_void_p(ptr), i))
        if text:
            out.append(text)
    return out


def _prop(carbon, src, key_name):
    """Read one TIS property. The key is a CFStringRef exported as a global
    symbol by the framework, so it is read out of the loaded image rather than
    constructed. Properties follow the CF **get** rule: not owned, not
    released."""
    key = _global_string(carbon, key_name)
    if key is None:
        return None
    return carbon.TISGetInputSourceProperty(ctypes.c_void_p(src), ctypes.c_void_p(key))


def _describe(cf, carbon, src):
    """One input source as a plain dict (no pointers escape this module)."""
    return {
        "id": _cfstr(cf, _prop(carbon, src, "kTISPropertyInputSourceID")),
        "name": _cfstr(cf, _prop(carbon, src, "kTISPropertyLocalizedName")),
        "languages": _cfstr_list(
            cf, _prop(carbon, src, "kTISPropertyInputSourceLanguages")),
        "selectable": _is_true(
            cf, _prop(carbon, src, "kTISPropertyInputSourceIsSelectCapable")),
    }


def _keyboard_category(cf, carbon):
    """The value of `kTISCategoryKeyboardInputSource`.

    Read out of the framework rather than hardcoded, because the comparison it
    feeds DROPS every source that disagrees — a constant that ever changed
    would empty the list rather than merely mislabel it. The literal is the
    fallback for a build that does not export the symbol."""
    return _cfstr(cf, _global_string(carbon, "kTISCategoryKeyboardInputSource")) \
        or _KEYBOARD_CATEGORY


def _global_string(lib, name):
    """A CFStringRef exported as a global symbol, or None if absent."""
    try:
        return ctypes.c_void_p.in_dll(lib, name).value
    except ValueError:
        return None


def _is_true(cf, ptr):
    """CFBooleanRef -> bool by POINTER identity against `kCFBooleanTrue`.

    A CFBoolean wrapped and coerced with `bool()` is true for both values (it
    is a non-NULL object either way), so the comparison has to be against the
    singleton. A property macOS does not answer is treated as True: a source
    that refuses selection reports it explicitly, and defaulting to False would
    silently empty the candidate list on any future macOS that drops the key."""
    if not ptr:
        return True
    true_ptr = _global_string(cf, "kCFBooleanTrue")
    if true_ptr is None:
        return True
    return ptr == true_ptr


def list_input_sources():
    """Enumerate the ENABLED keyboard input sources.

    Returns ``(sources, error)`` — the list is ALWAYS a list, empty when
    `error` is set. ⚠️ Every entry point here answers in that shape rather than
    the repo's usual ``(ok, value_or_reason)``, because a second element whose
    TYPE depends on the first makes the caller's loop iterate a string on the
    failure path if the flag is ever mis-read; CodeQL flagged exactly that
    (alert 357). The value never changes type, so the bug cannot be written.

    ``False`` for the second argument of `TISCreateInputSourceList` is what
    restricts the list to what the user has enabled — passing True would offer
    every layout macOS ships, and selecting one of those does nothing."""
    bridge = _load()
    if not bridge:
        return [], f"Text Input Source Services unavailable ({_bridge_error})"
    cf, carbon = bridge
    arr = carbon.TISCreateInputSourceList(None, False)
    if not arr:
        return [], "TISCreateInputSourceList returned no input sources"
    try:
        sources = []
        for i in range(cf.CFArrayGetCount(ctypes.c_void_p(arr))):
            src = cf.CFArrayGetValueAtIndex(ctypes.c_void_p(arr), i)
            if not src:
                continue
            category = _cfstr(
                cf, _prop(carbon, src, "kTISPropertyInputSourceCategory"))
            if category and category != _keyboard_category(cf, carbon):
                continue
            info = _describe(cf, carbon, src)
            if info["id"]:
                sources.append(info)
        return sources, None
    finally:
        # TISCreateInputSourceList follows the CF **create** rule, so this call
        # owns the array. The per-source dicts above hold no pointers into it.
        cf.CFRelease(ctypes.c_void_p(arr))


def current_input_source():
    """The keyboard input source in effect right now.

    Returns ``(source, error)``: a dict, or None with the reason."""
    bridge = _load()
    if not bridge:
        return None, f"Text Input Source Services unavailable ({_bridge_error})"
    cf, carbon = bridge
    src = carbon.TISCopyCurrentKeyboardInputSource()
    if not src:
        return None, "TISCopyCurrentKeyboardInputSource returned nothing"
    try:
        return _describe(cf, carbon, src), None
    finally:
        cf.CFRelease(ctypes.c_void_p(src))


def select_input_source(source_id):
    """Select the enabled keyboard input source with this ID.

    The source is re-found here rather than carried in from a previous
    enumeration, so no `TISInputSourceRef` ever outlives the CFArray that owns
    it. Returns ``(selected, error)``."""
    bridge = _load()
    if not bridge:
        return False, f"Text Input Source Services unavailable ({_bridge_error})"
    cf, carbon = bridge
    arr = carbon.TISCreateInputSourceList(None, False)
    if not arr:
        return False, "TISCreateInputSourceList returned no input sources"
    try:
        for i in range(cf.CFArrayGetCount(ctypes.c_void_p(arr))):
            src = cf.CFArrayGetValueAtIndex(ctypes.c_void_p(arr), i)
            if not src:
                continue
            found = _cfstr(cf, _prop(carbon, src, "kTISPropertyInputSourceID"))
            if found != source_id:
                continue
            status = carbon.TISSelectInputSource(ctypes.c_void_p(src))
            if status != 0:
                return False, f"TISSelectInputSource({source_id}) failed with OSStatus {status}"
            return True, None
        return False, f"Input source {source_id} is no longer enabled"
    finally:
        cf.CFRelease(ctypes.c_void_p(arr))
