"""User-interface translations for the tray app and the forwarder.

Qt-free on purpose: the GUI marks its strings with the helpers below, and
``PolyCore`` must stay importable without PyQt5 (tests/core/import_guard_test.py).
Only the two GUI processes call :func:`install`; the headless daemon, ``polyctl``
and every log line stay English, because support bundles and the problem scan
must read the same text on every machine.

Catalogs are the ``.po`` files in ``polyhost/res/locale/``, parsed here at
startup. There is no compiled ``.mo``: a generated binary next to its source is
a second copy that can drift, and the parse costs a few milliseconds.
``scripts/update_translations.py`` extracts the strings and merges them into
every catalog.

How a GUI module uses it::

    from polyhost.i18n import _, _f, _nf, N_

    menu.addAction(_("Settings…"))
    label.setText(_f("Firmware {version} is available", version=v))
    _nf("{n} bundle", "{n} bundles", n)
    LABELS = {"fontpack": N_("font pack")}      # marked now, _() at use

``_f`` formats AND isolates each value for right-to-left languages, so a
version number or a path inside an Arabic sentence keeps its own direction.
Use it instead of ``_("…").format(…)`` wherever a value is inserted.
"""

import gettext
import logging
import math
import os
import re
import string
from collections import namedtuple

_log = logging.getLogger(__name__)

LOCALE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "res", "locale")
DOMAIN = "polyhost"

SOURCE_LANGUAGE = "en"
SETTING_AUTO = "auto"
PSEUDO = "pseudo"
# Development override for one run: a language code or "pseudo". It wins over
# the setting, so a screenshot or a check of a translation needs no OS change.
ENV_OVERRIDE = "POLYHOST_LANG"

Language = namedtuple("Language", "code endonym english rtl")

# The supported UI languages, in the order the settings dropdown lists them.
# `endonym` is the language's name in itself and is never translated: someone
# who picked a language they cannot read must still find their own.
LANGUAGES = (
    Language("en", "English", "English", False),
    Language("de", "Deutsch", "German", False),
    Language("fr", "Français", "French", False),
    Language("es", "Español", "Spanish", False),
    Language("pt_BR", "Português (Brasil)", "Portuguese (Brazil)", False),
    Language("ja", "日本語", "Japanese", False),
    Language("zh_CN", "简体中文", "Chinese (Simplified)", False),
    Language("ko", "한국어", "Korean", False),
    Language("it", "Italiano", "Italian", False),
    Language("pl", "Polski", "Polish", False),
    Language("ru", "Русский", "Russian", False),
    Language("ar", "العربية", "Arabic", True),
    Language("tr", "Türkçe", "Turkish", False),
    Language("uk", "Українська", "Ukrainian", False),
    Language("zh_TW", "繁體中文", "Chinese (Traditional)", False),
    Language("vi", "Tiếng Việt", "Vietnamese", False),
    Language("id", "Bahasa Indonesia", "Indonesian", False),
    Language("fa", "فارسی", "Persian", True),
    Language("nl", "Nederlands", "Dutch", False),
    Language("cs", "Čeština", "Czech", False),
)
_BY_CODE = {lang.code: lang for lang in LANGUAGES}

# Traditional-script Chinese regions. A plain "zh" with no script or region is
# read as Simplified, which is what every OS reports for mainland China.
_ZH_TRADITIONAL_REGIONS = {"TW", "HK", "MO"}

# Unicode first-strong isolate / pop directional isolate.
_FSI, _PDI = "⁨", "⁩"


def language(code):
    """The :class:`Language` for ``code``, or None."""
    return _BY_CODE.get(code)


def match_os_language(tag):
    """Map one OS language tag ("de-AT", "zh-Hant-TW", "pt_PT", "C") to a
    supported code, or None when we do not ship that language.

    Every regional variant uses its base language (``de-CH`` → ``de``), and
    European Portuguese uses the Brazilian translation until there is one of
    its own. Chinese is decided by script, then by region: Taiwan, Hong Kong
    and Macau read Traditional, and Simplified is no substitute for them.
    """
    if not tag:
        return None
    parts = [p for p in str(tag).replace("_", "-").split(".")[0].split("@")[0].split("-") if p]
    if not parts:
        return None
    base = parts[0].lower()
    rest = parts[1:]
    if base == "zh":
        scripts = {p.title() for p in rest if len(p) == 4}
        regions = {p.upper() for p in rest if len(p) == 2}
        if "Hant" in scripts or (not scripts and regions & _ZH_TRADITIONAL_REGIONS):
            return "zh_TW"
        return "zh_CN"
    if base == "pt":
        return "pt_BR"
    return base if base in _BY_CODE else None


def resolve(setting, os_languages, env=None):
    """The language code to run in.

    ``env`` (the ``POLYHOST_LANG`` value) wins, then a ``setting`` naming a
    shipped language, then the first of ``os_languages`` we ship, then English.
    A setting naming a language we no longer ship falls back like "auto".
    """
    for override in (env, setting):
        if not override or override == SETTING_AUTO:
            continue
        if override == PSEUDO or override in _BY_CODE:
            return override
        matched = match_os_language(override)
        if matched:
            return matched
        _log.warning("UI language %r is not available; following the OS instead.", override)
    for tag in os_languages or ():
        matched = match_os_language(tag)
        if matched:
            return matched
    return SOURCE_LANGUAGE


# --- catalogs ---------------------------------------------------------------

def _unescape(text):
    out = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            out.append({"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}.get(nxt, "\\" + nxt))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_po(text):
    """Parse ``.po`` text into ``(header, entries)``.

    ``entries`` is a list of dicts with ``msgctxt``, ``msgid``, ``msgid_plural``,
    ``msgstr`` (a list, one item per plural form) and ``fuzzy``. Covers the
    subset Babel writes: comments, flags, context, plurals and continued
    strings. Obsolete ``#~`` entries are comments here, and so are dropped.
    """
    entries = []
    cur = None
    field = None
    fuzzy_next = False

    def finish():
        nonlocal cur
        if cur is not None and cur.get("msgid") is not None:
            entries.append(cur)
        cur = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            finish()
            field = None
            continue
        if line.startswith("#"):
            if line.startswith("#,") and "fuzzy" in line:
                finish()
                fuzzy_next = True
            continue
        if line.startswith('"'):
            if cur is None or field is None:
                continue
            chunk = _unescape(line[1:-1])
            if isinstance(field, tuple):
                cur["msgstr"][field[1]] += chunk
            else:
                cur[field] += chunk
            continue
        keyword, _, value = line.partition(" ")
        value = _unescape(value.strip()[1:-1])
        if keyword in ("msgctxt", "msgid") and cur is not None and (
                keyword == "msgctxt" or cur.get("msgid") is not None):
            finish()
        if cur is None:
            cur = {"msgctxt": None, "msgid": None, "msgid_plural": None,
                   "msgstr": [], "fuzzy": fuzzy_next}
            fuzzy_next = False
        if keyword in ("msgctxt", "msgid", "msgid_plural"):
            cur[keyword] = value
            field = keyword
        elif keyword == "msgstr":
            cur["msgstr"] = [value]
            field = ("msgstr", 0)
        elif keyword.startswith("msgstr["):
            index = int(keyword[7:-1])
            while len(cur["msgstr"]) <= index:
                cur["msgstr"].append("")
            cur["msgstr"][index] = value
            field = ("msgstr", index)
    finish()

    header = {}
    for entry in entries:
        if entry["msgid"] == "" and entry["msgctxt"] is None and entry["msgstr"]:
            for hline in entry["msgstr"][0].splitlines():
                key, sep, val = hline.partition(":")
                if sep:
                    header[key.strip()] = val.strip()
            break
    return header, [e for e in entries if e["msgid"] != ""]


def _plural_function(header):
    forms = header.get("Plural-Forms", "")
    for part in forms.split(";"):
        key, sep, expr = part.partition("=")
        if sep and key.strip() == "plural":
            try:
                return gettext.c2py(expr.strip())
            except (ValueError, SyntaxError):
                _log.warning("Unreadable Plural-Forms %r; using n != 1.", forms)
    return lambda n: int(n != 1)


class PoTranslations(gettext.NullTranslations):
    """A ``gettext`` translation object built straight from a ``.po`` file.

    Untranslated and fuzzy entries are left out, so they fall through to the
    English source text rather than showing a draft nobody approved.
    """

    def __init__(self, text=""):
        super().__init__()
        header, entries = parse_po(text)
        self._plural = _plural_function(header)
        self._catalog = {}
        for entry in entries:
            if entry["fuzzy"] or not any(entry["msgstr"]):
                continue
            key = (entry["msgctxt"], entry["msgid"])
            if entry["msgid_plural"] is not None:
                if all(entry["msgstr"]):
                    self._catalog[key] = list(entry["msgstr"])
            else:
                self._catalog[key] = entry["msgstr"][0]

    def __len__(self):
        return len(self._catalog)

    def gettext(self, message):
        return self.pgettext(None, message)

    def pgettext(self, context, message):
        found = self._catalog.get((context, message))
        return found if isinstance(found, str) else message

    def ngettext(self, msgid1, msgid2, n):
        return self.npgettext(None, msgid1, msgid2, n)

    def npgettext(self, context, msgid1, msgid2, n):
        forms = self._catalog.get((context, msgid1))
        if isinstance(forms, list):
            index = self._plural(n)
            if 0 <= index < len(forms):
                return forms[index]
        return msgid1 if n == 1 else msgid2


_PSEUDO_MAP = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "àƀçđéƒĝĥîĵķĺɱñöþǫŕšţûṽŵẋýžÀßÇĐÉƑĜĤÎĴĶĹṀÑÖÞǪŔŠŢÛṼŴẊÝŽ")


# What the pseudo-locale must leave alone: format fields, printf conversions,
# markup tags and HTML entities.
_PSEUDO_KEEP = re.compile(r"\{[^{}]*\}|%(?:\([^)]*\))?[-#0 +]*\d*(?:\.\d+)?[a-zA-Z%]|<[^>]*>|&[a-zA-Z#0-9]+;")


def pseudo_translate(text):
    """Accent every letter and pad by 40 %, keeping placeholders and markup.

    A string the pseudo-locale shows without brackets was never marked, and a
    bracket cut off by its widget is a layout too narrow for German.
    """
    if not text:
        return text
    out = []
    pos = 0
    for match in _PSEUDO_KEEP.finditer(text):
        out.append(text[pos:match.start()].translate(_PSEUDO_MAP))
        out.append(match.group(0))
        pos = match.end()
    out.append(text[pos:].translate(_PSEUDO_MAP))
    return f"[{''.join(out)} {'~' * math.ceil(len(text) * 0.4)}]"


class PseudoTranslations(gettext.NullTranslations):
    """The ``pseudo`` locale: every marked string, visibly transformed."""

    def gettext(self, message):
        return pseudo_translate(message)

    def pgettext(self, context, message):
        return pseudo_translate(message)

    def ngettext(self, msgid1, msgid2, n):
        return pseudo_translate(msgid1 if n == 1 else msgid2)

    def npgettext(self, context, msgid1, msgid2, n):
        return self.ngettext(msgid1, msgid2, n)


def po_path(code):
    return os.path.join(LOCALE_DIR, f"{code}.po")


def load(code):
    """The translation object for ``code`` (English source text on any failure)."""
    if code == PSEUDO:
        return PseudoTranslations()
    if code == SOURCE_LANGUAGE or code not in _BY_CODE:
        return gettext.NullTranslations()
    path = po_path(code)
    try:
        # Our own file, UTF-8 by definition. The platform default is cp1252
        # on Windows and would turn every translation into mojibake.
        with open(path, encoding="utf-8") as fh:
            return PoTranslations(fh.read())
    except (OSError, ValueError) as e:
        _log.warning("Could not load the %s translation (%s); using English.", code, e)
        return gettext.NullTranslations()


# --- the process-wide active translation -------------------------------------

_active = gettext.NullTranslations()
_active_code = SOURCE_LANGUAGE


def install(code):
    """Make ``code`` the language every marked string is shown in."""
    global _active, _active_code
    _active = load(code)
    _active_code = code if code == PSEUDO or code in _BY_CODE else SOURCE_LANGUAGE
    return _active_code


def current_language():
    return _active_code


def is_rtl(code=None):
    lang = _BY_CODE.get(_active_code if code is None else code)
    return bool(lang and lang.rtl)


def _(message):
    return _active.gettext(message)


def N_(message):
    """Mark a string for extraction without translating it yet (module
    constants are built before :func:`install` runs). Translate with ``_()``
    where it is shown."""
    return message


def ngettext(singular, plural, n):
    return _active.ngettext(singular, plural, n)


def pgettext(context, message):
    return _active.pgettext(context, message)


def isolate(value):
    """Wrap ``value`` so its direction cannot reorder the text around it.

    Only while a right-to-left language is active: an LTR UI has nothing to
    protect, and some tray tooltips draw the isolate marks as boxes."""
    text = str(value)
    return f"{_FSI}{text}{_PDI}" if is_rtl() else text


class _IsolatingFormatter(string.Formatter):
    """str.format, except each value is isolated AFTER its format spec ran,
    so ``{size:,}`` and ``{pct:.0f}`` keep working under every language."""

    def format_field(self, value, format_spec):
        return isolate(super().format_field(value, format_spec))


_FORMATTER = _IsolatingFormatter()


def _f(message, **values):
    """Translate ``message``, then fill its ``{name}`` fields from ``values``,
    each one isolated for right-to-left languages. Format specs work."""
    return _FORMATTER.format(_active.gettext(message), **values)


def _nf(singular, plural, n, **values):
    """Plural-aware :func:`_f`: picks the form for ``n`` (also available to
    the message as ``{n}``), then fills and isolates like ``_f``."""
    values.setdefault("n", n)
    return _FORMATTER.format(_active.ngettext(singular, plural, n), **values)


# ---------------------------------------------------------------------------
# Messages from code that must stay English (the device layer, the updaters)
# ---------------------------------------------------------------------------
#
# The flash code, the update downloaders and the WinCompose installer report
# their status as English text: the same text goes to the log, to polyctl and,
# in client mode, across the daemon -> GUI event boundary as a plain string.
# A dialog that shows such a message translates it HERE, by matching the
# English against the template it was built from and rebuilding the sentence
# from the translated template. No message object has to cross a process.
#
# A template is registered by ``M_()`` when its module is imported, so every
# ``M_()`` call must be a MODULE constant: a template built inside a function
# is unknown to a GUI process that never ran that function (the daemon did).
# tests/i18n_test.py enforces that, and that no template carries a format spec
# (the values come back as the text the English carried).

_MESSAGE_TEMPLATES = {}
_FIELD = re.compile(r"\{(\w+)\}")


def M_(template):
    """Mark an English status message the GUI may show, and register it for
    :func:`translate_message`. Returns the template unchanged; the producer
    fills it with ``template.format(...)``."""
    if template not in _MESSAGE_TEMPLATES:
        _MESSAGE_TEMPLATES[template] = (_compile_template(template, "*?"),
                                        _compile_template(template, "*"))
    return template


def _compile_template(template, quantifier):
    pattern, seen, pos = [], set(), 0
    for m in _FIELD.finditer(template):
        pattern.append(re.escape(template[pos:m.start()]))
        name = m.group(1)
        pattern.append(f"(?P={name})" if name in seen else f"(?P<{name}>.{quantifier})")
        seen.add(name)
        pos = m.end()
    pattern.append(re.escape(template[pos:]))
    return re.compile("".join(pattern), re.DOTALL)


def _is_registered_message(value):
    return any(lazy.fullmatch(value) for lazy, _greedy in _MESSAGE_TEMPLATES.values())


def _literal_length(template):
    return len(_FIELD.sub("", template))


def translate_message(message):
    """The active language's version of an English status ``message`` built
    from an ``M_()`` template, or ``message`` itself when none matches.

    The most specific template (most literal text) wins. Each value is
    translated in turn, so a message carrying another message as a value
    (``"{step} — {elapsed}s elapsed"``) comes out translated as a whole.

    ⚠️ A value can contain the template's own separator: a ``step`` of
    "Erasing staging area — keyboard will reconnect when done" holds the
    `` — `` that follows ``{step}``. The shortest split then cuts the value in
    two, so the longest split is tried as well, and the one whose values are
    registered messages wins."""
    if not isinstance(message, str) or not message or _active_code == SOURCE_LANGUAGE:
        return message
    for template in sorted(_MESSAGE_TEMPLATES, key=_literal_length, reverse=True):
        candidates = [m for m in (p.fullmatch(message) for p in _MESSAGE_TEMPLATES[template])
                      if m is not None]
        if not candidates:
            continue
        best = max(candidates, key=lambda m: sum(
            _is_registered_message(v) for v in m.groupdict().values()))
        values = {k: translate_message(v) for k, v in best.groupdict().items()}
        return _f(template, **values)
    return message
