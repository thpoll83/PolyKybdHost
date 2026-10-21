"""Import the image libraries on a background thread at start.

The first overlay switch after a start decodes the app's template PNGs, and
`ImageConverter.open()` imports numpy and Pillow on first use. Nothing the
daemon imports before that loads either, so the first switch paid for both
imports: a field log (2026-10-21) showed 1166 ms of host time before the first
report of the first switch after an update, and 1.0 s between the decodes of
the first and the second template. Importing both here, while the keyboard
connects and the font packs are checked, moves that cost off the switch.

A switch that starts before the imports finish waits on Python's import lock
for the rest of them, which is never slower than importing them itself.
Qt-free: the daemon runs it, and `PolyCore` must not pull in Qt.
"""
import importlib
import logging
import threading
import time

# The modules the overlay path loads on first use, in the order it loads them.
MODULES = ("numpy", "PIL.Image", "PIL.PngImagePlugin")


def _run(log: logging.Logger, modules) -> None:
    times = []
    t_all = time.perf_counter()
    for name in modules:
        t0 = time.perf_counter()
        try:
            importlib.import_module(name)
        except Exception as e:  # noqa: BLE001 -- the decode reports its own error later
            log.warning("Preload of %s failed: %s", name, e)
            return
        times.append("%s %.0f ms" % (name, (time.perf_counter() - t0) * 1000.0))
    log.info("Preloaded the image libraries in %.0f ms (%s).",
             (time.perf_counter() - t_all) * 1000.0, ", ".join(times))


def start(log: logging.Logger | None = None, modules=MODULES) -> threading.Thread:
    """Start the preload thread and return it. Never raises."""
    log = log or logging.getLogger("PolyHost")
    thread = threading.Thread(target=_run, args=(log, tuple(modules)),
                              name="poly-preload", daemon=True)
    thread.start()
    return thread
