#!/usr/bin/env python3
"""Read the keyboard's QMK HID console (a hid-listen equivalent).

WHY THIS EXISTS — the host cannot show you this output during a flash.
A flash (firmware or font-pack) is ONE long job on the HID worker, and
`HidWorker._run()` only runs due periodics *between* jobs — so the 250 ms console
read cannot run for the whole flash. QMK drops console output that nobody drains,
so anything the firmware prints between BEGIN and the post-apply reconnect is
lost — including the FW-2 verdict, which is printed exactly there:

    FW_UP: image signature OK
    FW_UP: image signature INVALID
    FW_UP: image UNSIGNED (no signature supplied)

Run this in a second terminal *before* starting the flash to capture it. The
verdict is printed at COMMIT, i.e. before APPLY reboots the board, so it lands
while the device is still attached.

    .venv/bin/python tools/poly_console.py             # Linux/macOS
    .venv\\Scripts\\python.exe tools\\poly_console.py    # Windows

Needs only `hid`, which polyhost already depends on — no QMK CLI. (`qmk console`
refuses to run on Windows outside an MSYS2 MinGW64 shell, which is the other
reason this file exists.)
"""
import argparse
import ctypes
import pathlib
import platform
import sys
import time

# PolyTasten PolyKybd. Console interface usage page/id come from the firmware's
# split72/config.h (CONSOLE_ENABLE); the raw-HID interface is a different one,
# so this reader coexists with a running PolyKybdHost.
DEFAULT_VID, DEFAULT_PID = 0x2021, 0x2007
CONSOLE_USAGE_PAGE, CONSOLE_USAGE = 0xFF31, 0x0074

REPORT_LEN = 32
READ_TIMEOUT_MS = 250
RETRY_DELAY_S = 0.5


def _preload_win_hidapi() -> None:
    """Windows: load the repo's bundled hidapi.dll before `import hid`.

    The `hid` package resolves its native library by LEAF NAME
    (``LoadLibrary("hidapi.dll")``), and nothing installs that DLL onto the
    default search path — the repo ships it instead, and every path into the
    device goes through ``polyhost/device/hid_helper.py``, which pre-loads it at
    import time. This tool deliberately does NOT import polyhost, so it used to
    fail on Windows on every machine with "Unable to load any of the following
    libraries: ... hidapi.dll" while the app itself worked fine.

    Pre-loading by absolute path is enough HERE because Windows LoadLibrary
    returns the already-loaded module when the leaf name matches. (That trick
    does not work on macOS — see the dyld note in hid_helper._import_hid.)

    Best-effort: a system-wide hidapi is equally fine, so a missing bundled DLL
    is not an error — let `import hid` produce its own message.
    """
    if platform.system() != "Windows":
        return
    dll = (pathlib.Path(__file__).resolve().parent.parent
           / "polyhost" / "device" / "win-hidapi-0-15" / "hidapi.dll")
    if dll.is_file():
        try:
            ctypes.CDLL(str(dll))
        except OSError:
            pass


def find_console(hid, vid: int, pid: int):
    """Path of the console HID interface, or None if the keyboard isn't up."""
    for info in hid.enumerate(vid, pid):
        if (info.get("usage_page") == CONSOLE_USAGE_PAGE
                and info.get("usage") == CONSOLE_USAGE):
            return info["path"]
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vid", type=lambda s: int(s, 0), default=DEFAULT_VID)
    ap.add_argument("--pid", type=lambda s: int(s, 0), default=DEFAULT_PID)
    args = ap.parse_args()

    # Imported after parse_args so --help works without the dependency present.
    _preload_win_hidapi()
    import hid

    print(f"Waiting for the console interface of {args.vid:#06x}:{args.pid:#06x}… "
          "(Ctrl+C to stop)", flush=True)
    dev = None
    buf = ""
    while True:
        try:
            if dev is None:
                path = find_console(hid, args.vid, args.pid)
                if path is None:
                    time.sleep(RETRY_DELAY_S)
                    continue
                dev = hid.Device(path=path)
                print("--- console attached ---", flush=True)

            data = dev.read(REPORT_LEN, timeout=READ_TIMEOUT_MS)
            if not data:
                continue

            # ⚠️ A read returns a report-sized FRAGMENT, not a line: QMK sends
            # whatever fitted in one report, and a split can land mid-word. So
            # buffer and only emit on '\n' — printing each chunk verbatim
            # truncates long lines and drops continuations (the same trap
            # documented for polykybd-ctnd's perf_runner console handling).
            buf += bytes(data).split(b"\x00", 1)[0].decode("utf-8", "replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                print(line.rstrip("\r"), flush=True)

        except KeyboardInterrupt:
            if buf:
                print(buf, flush=True)   # don't swallow a trailing partial line
            return 0
        except Exception as exc:
            # Expected during a flash: APPLY reboots the keyboard and the handle
            # dies. Re-attach rather than exit, so one invocation spans the whole
            # update and catches the post-reboot banner too.
            if dev is not None:
                try:
                    dev.close()
                except Exception:
                    pass
                dev = None
                print(f"--- console detached ({exc}) — waiting… ---", flush=True)
            time.sleep(RETRY_DELAY_S)


if __name__ == "__main__":
    sys.exit(main())
