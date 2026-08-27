"""Encode and decode a macro body.

The wire format is QMK's own send-string encoding, which is what the firmware plays and
what ``dynamic_keymap_macro_send()`` would play if it ever had to. A macro is a run of
bytes terminated by NUL; the whole buffer is those runs back to back, and macro N is
found by counting N terminators from the start.

    <printable>              type that character
    0x01 0x01 <kc>           tap keycode
    0x01 0x02 <kc>           press keycode
    0x01 0x03 <kc>           release keycode
    0x01 0x04 <ascii digits> wait N ms, terminated by the first non-digit

Keycodes are 8 bit, i.e. basic keycodes. That still covers every modifier
(KC_LCTL..KC_RGUI are 0xE0..0xE7), so chords are expressible; mod-taps and layer
keycodes are not.

Qt-free: the CLI writes macros with this and so does the editor.
"""

from __future__ import annotations

from dataclasses import dataclass

PREFIX = 0x01
OP_TAP = 0x01
OP_DOWN = 0x02
OP_UP = 0x03
OP_DELAY = 0x04

# Basic keycodes worth naming for a chord. Deliberately not a full table: the point of
# these is the modifiers, and a macro that needs an obscure keycode can carry its number.
MODIFIERS = {
    "ctrl": 0xE0, "shift": 0xE1, "alt": 0xE2, "gui": 0xE3,
    "rctrl": 0xE4, "rshift": 0xE5, "ralt": 0xE6, "rgui": 0xE7,
}


@dataclass(frozen=True)
class Step:
    """One decoded step. ``kind`` is 'char' | 'tap' | 'down' | 'up' | 'delay'."""

    kind: str
    code: int = 0
    ms: int = 0


class MacroError(ValueError):
    """A macro could not be encoded -- e.g. text the keyboard cannot type."""


def encode_text(text: str) -> bytes:
    """Encode plain text as the taps that type it.

    Rejects anything outside printable ASCII rather than dropping it: a macro that
    silently types less than you asked for is worse than one that refuses. The
    firmware's send_string translation covers 0x20..0x7E plus tab/newline.
    """
    out = bytearray()
    for ch in text:
        o = ord(ch)
        if ch in ("\n", "\t"):
            out.append(o)
            continue
        if o < 0x20 or o > 0x7E:
            raise MacroError(
                f"{ch!r} cannot be typed by a macro -- the keyboard sends keycodes, "
                f"not Unicode. Printable ASCII, tab and newline only.")
        if o == PREFIX:  # unreachable given the range check, kept so the invariant is local
            raise MacroError("0x01 is the escape byte and cannot appear as text")
        out.append(o)
    return bytes(out)


def encode_steps(steps: list[Step]) -> bytes:
    """Encode a step list (the 'sequence' mode of the editor)."""
    out = bytearray()
    for s in steps:
        if s.kind == "char":
            out += encode_text(chr(s.code))
        elif s.kind in ("tap", "down", "up"):
            if not 0 <= s.code <= 0xFF:
                raise MacroError(f"keycode {s.code:#x} does not fit in one byte")
            out += bytes((PREFIX, {"tap": OP_TAP, "down": OP_DOWN, "up": OP_UP}[s.kind], s.code))
        elif s.kind == "delay":
            if not 0 <= s.ms <= 0xFFFF:
                raise MacroError(f"delay {s.ms} ms out of range (0..65535)")
            out += bytes((PREFIX, OP_DELAY)) + str(int(s.ms)).encode("ascii")
        else:
            raise MacroError(f"unknown step kind {s.kind!r}")
    return bytes(out)


def decode(body: bytes) -> list[Step]:
    """Decode one macro body (no terminator) back into steps.

    Mirrors base/macro_decode.c, including the detail that the byte ending a delay is
    NOT consumed -- it is re-read as the next step. Consuming it would silently swallow
    the character after every delay.
    """
    steps: list[Step] = []
    i = 0
    n = len(body)
    while i < n:
        b = body[i]
        if b == 0:
            break
        if b != PREFIX:
            steps.append(Step("char", code=b))
            i += 1
            continue
        if i + 1 >= n:
            break
        op = body[i + 1]
        if op == OP_DELAY:
            j = i + 2
            digits = ""
            while j < n and 0x30 <= body[j] <= 0x39:
                digits += chr(body[j])
                j += 1
            steps.append(Step("delay", ms=min(int(digits or 0), 0xFFFF)))
            i = j
            continue
        if i + 2 >= n:
            break
        kind = {OP_TAP: "tap", OP_DOWN: "down", OP_UP: "up"}.get(op)
        if kind is None:
            break  # unknown op: its argument is not known to be an argument
        steps.append(Step(kind, code=body[i + 2]))
        i += 3
    return steps


def to_text(steps: list[Step]) -> str | None:
    """Render `steps` back as plain text, or None when it is not expressible.

    This is what decides whether the editor can show a macro in its Text tab. A macro
    with a chord or a delay is not text, and pretending otherwise would lose the parts
    that are not characters the moment the user saved.
    """
    if any(s.kind != "char" for s in steps):
        return None
    return "".join(chr(s.code) for s in steps)


def split_buffer(buf: bytes, count: int) -> list[bytes]:
    """Split the whole body buffer into `count` macro bodies.

    Trailing macros that were never written come back as b"" -- the buffer is zero
    filled, so a slot past the last terminator reads as an immediate NUL, which is the
    same thing the firmware sees.
    """
    out: list[bytes] = []
    start = 0
    for _ in range(count):
        end = buf.find(0, start)
        if end < 0:
            out.append(buf[start:])
            start = len(buf)
            continue
        out.append(buf[start:end])
        start = end + 1
    return out


def join_buffer(bodies: list[bytes], capacity: int) -> bytes:
    """Pack macro bodies back into a whole buffer, NUL-terminated and zero-filled.

    Raises when they do not fit: the bodies share one buffer, so a long macro takes
    room from the others and the caller has to be told which way the trade went.
    """
    out = bytearray()
    for b in bodies:
        out += b
        out.append(0)
    # Trailing empty macros cost nothing -- the zero fill already reads as "empty" --
    # so drop the terminators past the last non-empty body before checking the fit.
    while len(out) > 0 and out[-1] == 0 and (len(out) < 2 or out[-2] == 0):
        out.pop()
    if len(out) > capacity:
        raise MacroError(
            f"macros need {len(out)} bytes but only {capacity} are available -- "
            f"shorten one of them")
    return bytes(out) + b"\0" * (capacity - len(out))
