"""The macro script form -- VIA's syntax, parsed to and printed from our steps.

    hello            type the characters
    {KC_A}           tap
    {+KC_LSFT}       hold
    {-KC_LSFT}       release
    {250}            wait, in milliseconds
    \\{               a literal brace

**The syntax is VIA's, deliberately and exactly** (`the-via/app`,
`src/utils/macro-api/macro-api.common.ts`). It is the de-facto standard for this, some
people already know it, and it maps one-for-one onto the steps we already store because
both sit on QMK's send-string encoding. Inventing a fourth spelling would buy nothing.

Two conscious departures, both about round-tripping rather than taste:

* **No `{KC_LSFT,KC_A}` chord shorthand.** VIA needs it because typing three braced
  tokens is tedious; we have a step table and a recorder for that. It is also the one
  form whose expansion is not obvious from reading it -- taps, or a held group? -- and
  a script view that cannot print back exactly what it parsed is a field that lies.
* **`{KC_NO}` and the transparent placeholders are not keys**, so they are refused
  rather than encoded as a step that does nothing.

⚠️ The contract is `parse(format(steps)) == steps` for every step list -- that is the
direction the editor's Table/Script toggle needs, since it switches through this module
on every flip. The other direction NORMALISES rather than preserving: `{KC_LSFT}` prints
back as `{KC_LEFT_SHIFT}` (the canonical name) and a bare `\\` prints as `\\\\`. VIA
behaves the same way, and a script whose text survived unchanged but whose meaning did
not would be the worse trade.
"""

from __future__ import annotations

import re

from polyhost.services import macro_body as mb
from polyhost.services import macro_keys as mk

# A braced token, ignoring one escaped by a backslash. Same shape as VIA's.
_TOKEN = re.compile(r"(?<!\\)\{(.*?)\}")

# ⚠️ TWO things, not one. `_ESCAPE_CHAR` is what gets PREPENDED; `_NEEDS_ESCAPE` is the
# set of characters that need it. Conflating them prepends the whole set, so a literal
# brace prints as `\\{{` and no longer round-trips. `}` is deliberately absent: it can
# only ever be literal, because a token is found from its OPENING brace.
_ESCAPE_CHAR = "\\"
_NEEDS_ESCAPE = "\\{"


class ScriptError(ValueError):
    """A script could not be parsed. The message names the offending token."""


def parse(text: str) -> list[mb.Step]:
    """Parse a script into steps. Raises `ScriptError` with a usable message."""
    steps: list[mb.Step] = []
    pos = 0
    for match in _TOKEN.finditer(text):
        _literal(text[pos:match.start()], steps)
        steps.append(_token(match.group(1)))
        pos = match.end()
    _literal(text[pos:], steps)
    return steps


def format(steps: list[mb.Step]) -> str:
    """Print steps as a script. `parse` reads back exactly what this prints."""
    out: list[str] = []
    for step in steps:
        if step.kind == "char":
            ch = chr(step.code)
            out.append(_ESCAPE_CHAR + ch if ch in _NEEDS_ESCAPE else ch)
        elif step.kind == "delay":
            out.append(f"{{{int(step.ms)}}}")
        else:
            prefix = {"tap": "", "down": "+", "up": "-"}.get(step.kind)
            if prefix is None:
                raise ScriptError(f"unknown step kind {step.kind!r}")
            out.append(f"{{{prefix}{mk.name_for(step.code)}}}")
    return "".join(out)


def _literal(chunk: str, steps: list[mb.Step]):
    """Append the characters of a literal run, unescaping as it goes."""
    i = 0
    while i < len(chunk):
        ch = chunk[i]
        if ch == _ESCAPE_CHAR and i + 1 < len(chunk) and chunk[i + 1] in _NEEDS_ESCAPE:
            ch = chunk[i + 1]
            i += 1
        # Reject here rather than at save: the script view is where it can be fixed,
        # and `encode_text`'s message already explains why a keyboard cannot type it.
        mb.encode_text(ch)
        steps.append(mb.Step("char", code=ord(ch)))
        i += 1


def _token(body: str) -> mb.Step:
    """One braced token -> one step."""
    text = body.strip()
    if not text:
        raise ScriptError("{} is empty -- expected a keycode or a delay")
    if "," in text:
        raise ScriptError(
            f"{{{body}}} is VIA's chord shorthand, which this editor does not read -- "
            f"write the keys out ({{+KC_LSFT}}{{KC_A}}{{-KC_LSFT}}) or use the step table")

    if text.isdigit():
        ms = int(text)
        if ms > 0xFFFF:
            raise ScriptError(f"{{{text}}} is longer than the longest delay (65535 ms)")
        return mb.Step("delay", ms=ms)

    kind, name = "tap", text
    if text[0] in "+-":
        kind, name = ("down" if text[0] == "+" else "up"), text[1:].strip()
    if not name:
        raise ScriptError(f"{{{body}}} names no key")

    code = mk.value_for(name)
    if code is None:
        raise ScriptError(f"{{{body}}} is not a keycode this keyboard can send")
    if code in mk.PLACEHOLDER_VALUES:
        raise ScriptError(f"{{{body}}} is a keymap placeholder, not a key")
    return mb.Step(kind, code=code)
