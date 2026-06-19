import logging
import sys

DEBUG_DETAILED = 8  # Custom level below DEBUG (10)

logging.addLevelName(DEBUG_DETAILED, "DEBUG_DETAILED")


def _debug_detailed(self, message, *args, **kwargs):
    if self.isEnabledFor(DEBUG_DETAILED):
        self._log(DEBUG_DETAILED, message, args, **kwargs)


logging.Logger.debug_detailed = _debug_detailed


LEVEL_HEX_COLORS = {
    logging.ERROR:   "#ff5555",  # bright red
    logging.WARNING: "#ff8700",  # orange (xterm 208)
    logging.INFO:    "#22cc22",  # green, readable on light & dark
    logging.DEBUG:   "#00afaf",  # teal
    DEBUG_DETAILED:  "#5fd7af",  # aquamarine
}


class ColorFormatter(logging.Formatter):
    _COLORS = {
        logging.ERROR:   "\033[91m",        # bright red
        logging.WARNING: "\033[38;5;208m",  # orange
        logging.INFO:    "\033[92m",         # bright green
        logging.DEBUG:   "\033[36m",         # teal
        DEBUG_DETAILED:  "\033[38;5;86m",   # aquamarine
    }
    _RESET = "\033[0m"

    def format(self, record):
        color = self._COLORS.get(record.levelno, "")
        return f"{color}{super().format(record)}{self._RESET}" if color else super().format(record)


class MultiLineFormatter(logging.Formatter):
    """Prefix every continuation line of a multi-line record with the record's
    timestamp, so a batched keyboard-console flush reads like one line per
    console message. lines[0] already carries the fmt-applied prefix and must
    not be prefixed (or emitted) again, and no line may be dropped — the old
    implementation re-emitted the first line and swallowed the last one."""

    def format(self, record):
        message = super().format(record)
        lines = message.splitlines()
        if len(lines) <= 1:
            return message.strip("\n")
        timestamp = self.formatTime(record)
        return "\n".join([lines[0], *(f"[{timestamp}] {line}" for line in lines[1:])])


def make_stream_handler(fmt: str) -> logging.Handler:
    stream = sys.stdout
    if stream is None:
        # No console to write to. The Windows tray GUI and the GUI-spawned
        # daemon both run under pythonw.exe, where sys.stdout/stderr are None —
        # a StreamHandler would crash on `.isatty()` below, taking down
        # run_headless (daemon never binds its control socket) and
        # PolyHost.__init__ (the GUI never appears). Logging still reaches the
        # rotating file handlers; the console mirror is simply a no-op here.
        return logging.NullHandler()
    is_tty = bool(getattr(stream, "isatty", lambda: False)())
    handler = logging.StreamHandler(stream=stream)
    handler.setFormatter(ColorFormatter(fmt) if is_tty else logging.Formatter(fmt))
    return handler


class RepeatCollapseHandler(logging.Handler):
    """Wraps another handler and collapses repeating sequences of log records.

    After a sequence of up to `max_pattern_len` messages repeats at least once
    (two identical cycles emitted normally), further complete repetitions are
    suppressed. When the sequence changes a summary is emitted:
      "... (last N line(s) repeated X more time(s))"
    followed by any partially-completed cycle that was mid-suppression.
    """

    def __init__(self, inner: logging.Handler, max_pattern_len: int = 8):
        super().__init__()
        self.inner = inner
        self.max_pattern_len = max_pattern_len
        self._buf: list[str] = []          # recent message keys (text only, no timestamp)
        self._pattern: list[str] = []      # current detected repeating pattern
        self._partial: list[logging.LogRecord] = []  # suppressed records in current incomplete cycle
        self._pos: int = 0                 # position within the current cycle
        self._count: int = 0              # number of fully suppressed extra repetitions

    # ------------------------------------------------------------------ helpers

    def _detect_period(self) -> int:
        """Return smallest p such that the last 2p buffer entries form a repeating pattern."""
        n = len(self._buf)
        for p in range(1, min(self.max_pattern_len, n // 2) + 1):
            if self._buf[-p:] == self._buf[-2 * p:-p]:
                return p
        return 0

    def _make_summary(self, ref: logging.LogRecord) -> logging.LogRecord:
        return logging.LogRecord(
            name=ref.name,
            level=ref.levelno,
            pathname="",
            lineno=0,
            msg="  ... (last %d line(s) repeated %d more time(s))",
            args=(len(self._pattern), self._count),
            exc_info=None,
        )

    def _exit_pattern(self, ref: logging.LogRecord) -> None:
        """Leave suppression mode: emit summary then re-emit the partial cycle."""
        if self._count > 0:
            self.inner.emit(self._make_summary(ref))
        for r in self._partial:
            self.inner.emit(r)
            self._buf.append(r.getMessage())
        self._pattern = []
        self._partial = []
        self._pos = 0
        self._count = 0

    # ------------------------------------------------------------------ Handler API

    def emit(self, record: logging.LogRecord) -> None:
        self.acquire()
        try:
            key = record.getMessage()

            if self._pattern:
                if key == self._pattern[self._pos]:
                    self._partial.append(record)
                    self._pos += 1
                    if self._pos == len(self._pattern):
                        # Completed one more full cycle — discard partial, bump count
                        self._count += 1
                        self._pos = 0
                        self._partial = []
                    return  # suppressed

                # Pattern broken — flush and fall through to normal emit below
                self._exit_pattern(record)

            # Normal emit
            self.inner.emit(record)
            self._buf.append(key)

            # Keep buffer bounded
            max_buf = self.max_pattern_len * 2
            if len(self._buf) > max_buf:
                del self._buf[:-max_buf]

            # Check for a new repeating pattern
            p = self._detect_period()
            if p:
                self._pattern = list(self._buf[-p:])
                self._pos = 0
                self._count = 0
                self._partial = []
        finally:
            self.release()

    def close(self) -> None:
        self.acquire()
        try:
            if self._pattern and (self._count > 0 or self._partial):
                ref = (self._partial[0] if self._partial else
                       logging.LogRecord("PolyHost", logging.INFO, "", 0, "", (), None))
                self._exit_pattern(ref)
            self.inner.close()
        finally:
            self.release()
        super().close()


def make_collapse_handler(inner: logging.Handler, max_pattern_len: int = 8) -> RepeatCollapseHandler:
    """Wrap *inner* with repeat-collapse logic; returns the wrapper to pass to basicConfig."""
    return RepeatCollapseHandler(inner, max_pattern_len)
