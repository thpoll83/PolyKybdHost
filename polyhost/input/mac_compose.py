"""MacCompose: the host types the keyboard's Unicode characters on macOS.

QMK's macOS unicode mode holds Option and types the hex code of a character. That
works only while the "Unicode Hex Input" input source is selected, and the host
selects the input source that matches the keyboard language
(`polyhost.input.macos_input_source`), so on a German or French source the code
came out as Option characters (a 😀 typed ``∂{¶∂∂€≠≠``).

In MacCompose (firmware protocol 38+, cmd 20 value 6) the keyboard holds **F20**
instead of Option. A keyboard event tap reads the hex digits between F20 down
and F20 up, drops all of these keys and posts the character with
``CGEventKeyboardSetUnicodeString``. That works with every input source.

* The tap reads VIRTUAL key codes, which name a key position and not a
  character, so the digits decode the same on every layout (AZERTY included).
* A character above U+FFFF arrives as a UTF-16 surrogate pair (8 digits), as in
  QMK's macOS mode; `ComposeDecoder` combines the pair.
* The tap needs the Accessibility permission (System Settings → Privacy &
  Security → Accessibility), the same grant the shortcut harvest uses. Without
  it ``CGEventTapCreate`` returns None, `MacComposeTap.start` returns False and
  PolyCore keeps the plain Mac mode.

pyobjc is imported late, inside `_QuartzApi`, because this module loads on every
OS. `ComposeDecoder` is pure and tested offline
(``tests/input/mac_compose_test.py``); the Quartz calls have not run in CI.
"""

from __future__ import annotations

import logging
import threading

#: kVK_F20 (HIToolbox Events.h): the key the firmware holds in MacCompose.
KEY_F20 = 0x5A

#: Virtual key codes of the hex digits (kVK_ANSI_0..9, kVK_ANSI_A..F).
HEX_KEYS = {
    0x1D: 0x0, 0x12: 0x1, 0x13: 0x2, 0x14: 0x3, 0x15: 0x4,
    0x17: 0x5, 0x16: 0x6, 0x1A: 0x7, 0x1C: 0x8, 0x19: 0x9,
    0x00: 0xA, 0x0B: 0xB, 0x08: 0xC, 0x02: 0xD, 0x0E: 0xE, 0x03: 0xF,
}

#: The firmware sends at most 8 digits (a surrogate pair). More means the
#: sequence is not ours, so the decoder gives up on it.
MAX_DIGITS = 8


def code_point_text(digits: str) -> str | None:
    """The text for the hex ``digits`` the firmware sent, or None if invalid.

    Up to 6 digits are one code point. 8 digits above U+10FFFF are a UTF-16
    surrogate pair (high unit first), which is how QMK's macOS mode sends a
    character outside the Basic Multilingual Plane."""
    if not digits or len(digits) > MAX_DIGITS:
        return None
    value = int(digits, 16)
    if len(digits) == 8 and value > 0x10FFFF:
        hi, lo = value >> 16, value & 0xFFFF
        if not (0xD800 <= hi <= 0xDBFF and 0xDC00 <= lo <= 0xDFFF):
            return None
        value = 0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00)
    if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF:
        return None
    return chr(value)


class ComposeDecoder:
    """Turns the key events of one F20 sequence into text. Pure, no I/O.

    `feed` returns ``(swallow, text)``: ``swallow`` drops the event, ``text`` is
    the character to post (only on F20 up).

    * F20 down starts a sequence, F20 up ends it. Both are always dropped, so an
      F20 never reaches an application while the tap runs.
    * A hex digit (down or up) inside a sequence is dropped and collected.
    * Any other key inside a sequence ends the sequence without text, and passes
      through: the keyboard never sends one there, so it is the user's key.
    """

    def __init__(self) -> None:
        self._digits: list[str] | None = None   # None: no sequence open

    @property
    def composing(self) -> bool:
        return self._digits is not None

    def feed(self, keycode: int, is_down: bool, is_repeat: bool = False):
        if keycode == KEY_F20:
            if is_down:
                if not is_repeat:
                    self._digits = []
                return True, None
            digits, self._digits = self._digits, None
            return True, (code_point_text("".join(digits)) if digits else None)
        if self._digits is None:
            return False, None
        nibble = HEX_KEYS.get(keycode)
        if nibble is None:
            self._digits = None
            return False, None
        if is_down and not is_repeat:
            self._digits.append(format(nibble, "x"))
            if len(self._digits) > MAX_DIGITS:
                self._digits = None
        return True, None


class _QuartzApi:
    """The pyobjc Quartz calls the tap needs, imported late (macOS only)."""

    def __init__(self) -> None:
        import Quartz  # noqa: PLC0415 - pyobjc exists only on macOS
        self.q = Quartz

    def create_tap(self, callback):
        q = self.q
        mask = q.CGEventMaskBit(q.kCGEventKeyDown) | q.CGEventMaskBit(q.kCGEventKeyUp)
        return q.CGEventTapCreate(q.kCGSessionEventTap, q.kCGHeadInsertEventTap,
                                  q.kCGEventTapOptionDefault, mask, callback, None)

    def run(self, tap) -> object:
        """Add the tap to this thread's run loop and run it. Returns when stopped."""
        q = self.q
        source = q.CFMachPortCreateRunLoopSource(None, tap, 0)
        loop = q.CFRunLoopGetCurrent()
        q.CFRunLoopAddSource(loop, source, q.kCFRunLoopCommonModes)
        q.CGEventTapEnable(tap, True)
        return loop

    def run_loop(self) -> None:
        self.q.CFRunLoopRun()

    def stop(self, loop) -> None:
        self.q.CFRunLoopStop(loop)

    def re_enable(self, tap) -> None:
        self.q.CGEventTapEnable(tap, True)

    def is_disable_event(self, type_) -> bool:
        q = self.q
        return type_ in (q.kCGEventTapDisabledByTimeout, q.kCGEventTapDisabledByUserInput)

    def key_event(self, event):
        """``(keycode, is_down, is_repeat)`` of a keyboard event."""
        q = self.q
        keycode = q.CGEventGetIntegerValueField(event, q.kCGKeyboardEventKeycode)
        repeat = q.CGEventGetIntegerValueField(event, q.kCGKeyboardEventAutorepeat)
        return int(keycode), q.CGEventGetType(event) == q.kCGEventKeyDown, bool(repeat)

    def post_text(self, proxy, text: str) -> None:
        """Post ``text`` as one key down and up, after this tap."""
        q = self.q
        units = len(text.encode("utf-16-le")) // 2
        for down in (True, False):
            ev = q.CGEventCreateKeyboardEvent(None, 0, down)
            q.CGEventSetFlags(ev, 0)
            q.CGEventKeyboardSetUnicodeString(ev, units, text)
            q.CGEventTapPostEvent(proxy, ev)


class MacComposeTap:
    """The keyboard event tap, on its own thread with its own run loop."""

    def __init__(self, api=None, log: logging.Logger | None = None) -> None:
        self._api = api
        self.log = log or logging.getLogger(__name__)
        self._decoder = ComposeDecoder()
        self._tap = None
        self._loop = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self.typed = 0   # characters posted, for the log; never the characters

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and self._tap is not None

    def start(self, timeout: float = 0.5) -> bool:
        """Start the tap once, and wait up to ``timeout`` seconds for it.

        False when it cannot run (no pyobjc, no Accessibility grant); the caller
        then keeps the plain Mac mode. A later call tries again, so a grant given
        while the host runs takes effect at the next connect."""
        with self._lock:
            if self.running:
                return True
            if self._thread is not None and self._thread.is_alive():
                pass   # still starting: wait below
            else:
                self._start_thread_locked()
                if self._thread is None:
                    return False
        self._ready.wait(timeout)
        return self.running

    def _start_thread_locked(self) -> None:
        """Start the tap thread. Leaves ``_thread`` None when pyobjc is missing."""
        self._thread = None
        if self._api is None:
            try:
                self._api = _QuartzApi()
            except Exception as exc:  # noqa: BLE001 - no pyobjc: stay on Mac mode
                self.log.info("MacCompose is off: pyobjc Quartz is not available (%s).", exc)
                return
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="poly-mac-compose",
                                        daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            tap = self._api.create_tap(self._on_event)
            if tap is None:
                self.log.info("MacCompose is off: macOS refused the keyboard event tap. "
                              "Allow PolyKybd Host under System Settings → Privacy & "
                              "Security → Accessibility.")
                return
            self._tap = tap
            self._loop = self._api.run(tap)
            self.log.info("MacCompose keyboard event tap is running.")
        except Exception:  # noqa: BLE001 - never take the core down
            self.log.warning("MacCompose event tap failed to start", exc_info=True)
            self._tap = None
            return
        finally:
            self._ready.set()
        try:
            self._api.run_loop()
        finally:
            self._tap = None

    def stop(self) -> None:
        loop = self._loop
        if loop is not None and self._api is not None:
            try:
                self._api.stop(loop)
            except Exception:  # noqa: BLE001
                self.log.debug("MacCompose run loop stop failed", exc_info=True)

    def _on_event(self, proxy, type_, event, _refcon=None):
        """The tap callback. Returns the event to pass it on, None to drop it.

        ⚠️ It never raises: an exception in a tap callback is printed by pyobjc
        and the event is lost. And it stays fast: macOS disables a tap whose
        callback is slow, and then re-enables it here on the disable event."""
        try:
            if self._api.is_disable_event(type_):
                self.log.info("MacCompose event tap was disabled by macOS; re-enabling.")
                self._api.re_enable(self._tap)
                return event
            keycode, is_down, is_repeat = self._api.key_event(event)
            swallow, text = self._decoder.feed(keycode, is_down, is_repeat)
            if text:
                self._api.post_text(proxy, text)
                self.typed += 1
            return None if swallow else event
        except Exception:  # noqa: BLE001
            self.log.debug("MacCompose event callback failed", exc_info=True)
            return event
