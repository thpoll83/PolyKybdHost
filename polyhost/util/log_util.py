import logging
import sys

DEBUG_DETAILED = 8  # Custom level below DEBUG (10)

logging.addLevelName(DEBUG_DETAILED, "DEBUG_DETAILED")


def _debug_detailed(self, message, *args, **kwargs):
    if self.isEnabledFor(DEBUG_DETAILED):
        self._log(DEBUG_DETAILED, message, args, **kwargs)


logging.Logger.debug_detailed = _debug_detailed


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


def make_stream_handler(fmt: str) -> logging.StreamHandler:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(ColorFormatter(fmt) if sys.stdout.isatty() else logging.Formatter(fmt))
    return handler
