import logging
import pathlib
import threading
import platform
import os
import time
from contextlib import contextmanager
from typing import Any

log = logging.getLogger('PolyHost')
if platform.system() == 'Windows':
    import ctypes
    ctypes.CDLL(os.path.dirname(os.path.realpath(__file__)) + '\\win-hidapi-0-15\\hidapi.dll')


def _import_hid():
    """Import the `hid` package, working around macOS not finding a
    Homebrew-installed libhidapi.

    `hid` loads the native library by *leaf* name
    (``ctypes.cdll.LoadLibrary("libhidapi.dylib")``), but recent macOS / Python
    framework builds don't search Homebrew's lib dirs (``/usr/local/lib`` on
    Intel, ``/opt/homebrew/lib`` on Apple Silicon) by default, so a
    brew-installed hidapi is invisible and the import fails. ``find_library``
    *does* resolve the absolute path, so on a first-attempt failure we patch the
    leaf-name load to use that path and retry. Pre-loading the dylib by absolute
    path does NOT work — dyld won't match an already-loaded image for a leaf name
    it can't otherwise find (verified on macOS Ventura + python.org 3.14). Runs in
    every process that touches the device (GUI and headless daemon alike)."""
    try:
        import hid
        return hid
    except ImportError:
        if platform.system() != 'Darwin':
            print(_HIDAPI_MISSING_HELP)
            raise

    import ctypes
    import ctypes.util
    import glob
    import importlib

    path = ctypes.util.find_library("hidapi")
    if not path:
        for d in ("/opt/homebrew/lib", "/opt/homebrew/opt/hidapi/lib",
                  "/usr/local/lib", "/usr/local/opt/hidapi/lib"):
            hits = sorted(glob.glob(os.path.join(d, "libhidapi*.dylib")))
            if hits:
                path = hits[0]
                break

    if path:
        loader = ctypes.cdll
        original = loader.LoadLibrary

        def _redirect(name):
            # hid tries several leaf names; send any libhidapi* request to the
            # resolved absolute path so the leaf-name search can't miss it.
            if name and os.path.basename(name).startswith("libhidapi"):
                name = path
            return original(name)

        loader.LoadLibrary = _redirect
        try:
            return importlib.import_module("hid")
        except ImportError:
            pass
        finally:
            loader.LoadLibrary = original

    # Nothing worked — print the install help and fail.
    print(_HIDAPI_MISSING_HELP)
    raise ImportError("Unable to load the hidapi native library "
                      "(is it installed? on macOS: brew install hidapi)")


_HIDAPI_MISSING_HELP = """Library hidapi missing. Please Install:

    Arch Linux
    ==========
    Binary distributions are available in the community repository.

    Enable the community repository in /etc/pacman.conf
    [community]
    Include = /etc/pacman.d/mirrorlist
    Install hidapi
    pacman -Sy hidapi
  
    CentOS/RHEL
    ===========
    Binary distributions are available through EPEL.

    yum install hidapi

    Fedora
    ======
    Binary distributions are available.

    dnf install hidapi

    Ubuntu/Debian
    =============
    Binary distributions are available.

    apt install libhidapi-hidraw0
    or

    apt install libhidapi-libusb0

    Others
    ======
    Binary distributions may be available in your package repositories.
    If not, you can build from source as described in the libusb/hidapi README.

    Windows
    =======
    Installation procedure for Windows is described in the libusb/hidapi README.

    Binary distributions are provided by libusb/hidapi

    OSX
    ===
    There are currently no official binary distributions for Mac,
    so you must build hidapi yourself.

    Installation instructions are described in the libusb/hidapi README.

    You can also use brew:

    brew install hidapi

    FreeBSD
    =======
    Binary distributions are available.

    pkg install -g 'py3*-hid'
    """

hid = _import_hid()

PERMISSION_MSG = f"""It looks like you do not have permission to access the device.
Please run the following commands, then reconnect the device and restart the application:

sudo cp {os.path.join(pathlib.Path(__file__).parent.resolve(), "99-hid.rules")} /etc/udev/rules.d
sudo udevadm control --reload-rules
sudo udevadm trigger
"""

class IoStats:
    """Count, total, maximum and median of a set of call durations. The
    sample list is capped (``MAX_SAMPLES``); the count, total and maximum keep
    counting past it, the median is then of the first samples."""

    MAX_SAMPLES = 4096

    def __init__(self):
        self.count = 0
        self.total_s = 0.0
        self.max_s = 0.0
        self._samples = []

    def add(self, dt: float) -> None:
        self.count += 1
        self.total_s += dt
        if dt > self.max_s:
            self.max_s = dt
        if len(self._samples) < self.MAX_SAMPLES:
            self._samples.append(dt)

    @property
    def median_s(self) -> float:
        if not self._samples:
            return 0.0
        ordered = sorted(self._samples)
        n = len(ordered)
        mid = n // 2
        return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0


class IoMeter(IoStats):
    """Timing of the device calls made while a HidHelper has it attached
    (``HidHelper.measure()``): every call, and the same calls split by kind.

    One sample per call to a write or read primitive, exceptions included.
    ``write`` holds the write-only calls (in an overlay switch: the image
    reports and the mapping reports): a write returns when the keyboard has
    taken the report into its receive queue, so it is the bus until the queue
    is full, and the firmware's pace per report after that. ``reply`` holds
    the calls that wait for an answer (in an overlay switch: the icon fill
    reports, cmd 42, and prepare/enable): their time includes the keyboard
    doing the work the command asks for, which a faster link does not shorten.
    """

    KINDS = ("write", "reply")

    def __init__(self):
        super().__init__()
        self.first_at = None    # perf_counter() at the start of the first call
        self.write = IoStats()
        self.reply = IoStats()

    def record(self, t0: float, t1: float, kind: str = "reply") -> None:
        dt = t1 - t0
        if self.first_at is None:
            self.first_at = t0
        self.add(dt)
        getattr(self, kind if kind in self.KINDS else "reply").add(dt)


class HidHelper:
    # The meter the device calls below report into, or None. A class
    # attribute, because tests build helpers with __new__ and never run
    # __init__. Attach one with measure(); detach with stop_measuring().
    meter: IoMeter | None = None

    def __del__(self):
        if hasattr(self, 'interface') and self.interface:
            self.interface.close()

    # The two USB touch points. MockHidHelper overrides both, so it runs the
    # real constructor and opens the emulator as its raw interface.
    def _enumerate(self, vid):
        return hid.enumerate(vid, 0)

    def _open(self, info):
        return hid.Device(path=info['path'])

    def _open_raw(self, info):
        """Open the raw interface and remember its path: wait_for_reboot waits
        for THIS device to leave the bus, not for every PolyKybd on it."""
        dev = self._open(info)
        self.interface_path = info.get('path')
        return dev

    def __init__(self, settings):
        self.settings = settings
        self.lock = threading.Lock()

        device_interfaces = [i for i in self._enumerate(self.settings.VID)
                             if i['product_id'] in self.settings.KNOWN_PIDS]
        raw_hid_interfaces = [i for i in device_interfaces if i['usage_page'] == self.settings.HID_RAW_USAGE_PAGE and i['usage'] == self.settings.HID_RAW_USAGE]

        if len(raw_hid_interfaces) != 0:
            try:
                self.interface = self._open_raw(raw_hid_interfaces[0])
            except hid.HIDException as e:
                print(PERMISSION_MSG)
                raise e
                
        else:
            self.interface = None

        console_hid_interfaces = [j for j in device_interfaces if j['usage_page'] == self.settings.HID_CONSOLE_USAGE_PAGE and j['usage'] == self.settings.HID_CONSOLE_USAGE]
                                                                    
        if len(console_hid_interfaces) != 0:
            try:
                self.remote_console = self._open(console_hid_interfaces[0])
            except hid.HIDException as e:
                print(PERMISSION_MSG)
                raise e
                
        else:
            self.remote_console = None

    def get_console_output(self):
        if self.remote_console is None:
            return bytearray()
        return self.remote_console.read(self.settings.HID_CONSOLE_REPORT_SIZE, timeout=0)

    def console_acquired(self):
        return self.remote_console is not None

    def reopen_console(self) -> bool:
        """(Re-)open only the console interface.

        After a firmware apply the device re-enumerates; the reconnect path
        rebuilds the whole HidHelper, but in the come-back-up race the console
        interface can be missing from that enumeration while raw HID already
        works — remote_console then silently stayed None until a replug
        (field 2026-07-05: "no console log after flashing/apply"). Returns
        True when a console handle is open afterwards."""
        if self.remote_console is not None:
            try:
                self.remote_console.close()
            except Exception as e:
                log.debug("Closing the stale console handle failed: %s", e)
            self.remote_console = None
        # One guard around the whole enumerate+open sequence: hid.enumerate
        # itself can raise on USB churn/permission errors, and this runs from
        # the background self-heal path where an escaped exception is noise.
        try:
            device_interfaces = [i for i in hid.enumerate(self.settings.VID, 0)
                                  if i['product_id'] in self.settings.KNOWN_PIDS]
            console_hid_interfaces = [j for j in device_interfaces
                                      if j['usage_page'] == self.settings.HID_CONSOLE_USAGE_PAGE
                                      and j['usage'] == self.settings.HID_CONSOLE_USAGE]
            if console_hid_interfaces:
                self.remote_console = self._open(console_hid_interfaces[0])
        except Exception as e:
            log.debug("Console reopen failed (enumerate/open): %s", e)
            self.remote_console = None
        return self.remote_console is not None

    def interface_acquired(self):
        return self.interface is not None

    def measure(self) -> IoMeter:
        """Attach a fresh IoMeter; every device call until stop_measuring()
        reports into it. Returns the meter."""
        self.meter = IoMeter()
        return self.meter

    def stop_measuring(self) -> None:
        self.meter = None

    @contextmanager
    def _timed(self, kind: str):
        """Time one device call into the attached meter, if any, as ``kind``
        ("write" for a write that reads nothing back, "reply" for a call that
        waits for an answer). Wraps the call, not the lock wait: the worker
        thread is the only caller, so the lock is never contended and the two
        are the same."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            meter = self.meter
            if meter is not None:
                meter.record(t0, time.perf_counter(), kind)

    def __send(self, data: bytearray) -> tuple[bool, Any]:
        """ Write a data report without reading the response"""

        if self.interface is None:
            return False, "No Interface"

        request_data = [0x00] * (self.settings.HID_REPORT_SIZE + 1) # First byte is Report ID
        request_data[1:len(data) + 1] = data
        request_report = bytes(request_data)

        try:
            with self._timed("write"), self.lock:
                result = self.interface.write(request_report)
        except Exception as e:
            return False, f"Exception: {e}"

        return True, result

    def send(self, data: bytearray, timeout: int = 30) -> tuple[bool, Any]:
        """ Write a data report and read the response, the result of the response will be ignored"""

        if self.interface is None:
            return False, "No Interface"

        request_data = [0x00] * (self.settings.HID_REPORT_SIZE + 1) # First byte is Report ID
        request_data[1:len(data) + 1] = data
        request_report = bytes(request_data)

        try:
            with self._timed("reply"), self.lock:
                result = self.interface.write(request_report)
                self.interface.read(self.settings.HID_REPORT_SIZE, timeout=timeout)
        except Exception as e:
            return False, f"Exception: {e}"

        return True, result

    def send_multiple(self, data: bytearray) -> tuple[bool, Any]:
        """ Write one report of a multi-report burst without reading a response.

        Sequencing across reports is guaranteed by the single worker thread that
        owns the device, so no lock is held across reports — the internal lock is
        a per-call guard only (released on exception by construction).
        """
        if self.interface is None:
            return False, "No Interface"

        request_data = [0x00] * (self.settings.HID_REPORT_SIZE + 1) # First byte is Report ID
        request_data[1:len(data) + 1] = data
        request_report = bytes(request_data)

        try:
            with self._timed("write"), self.lock:
                result = self.interface.write(request_report)
        except Exception as e:
            return False, f"Exception: {e}"

        return True, result

    def read(self, timeout: int) -> tuple[bool, bytearray]:
        if self.interface is None:
            return False, bytearray("No Interface", 'utf-8')

        try:
            with self._timed("reply"), self.lock:
                response_report = self.interface.read(self.settings.HID_REPORT_SIZE, timeout=timeout)
        except Exception as e:
            return False, bytearray(f"Exception: {e}", 'utf-8')

        return True, response_report

    # Default read timeout: 100 ms. Windows delivers HID input reports on a
    # ~16 ms timer tick, so sub-30 ms timeouts are unreliable there; all HID
    # I/O runs on the worker thread, so a generous wait costs nothing.
    def send_and_read_validate(self, data: bytearray, timeout: int = 100, expected_prefix: bytearray | None = None) -> tuple[bool, bytearray]:
        if expected_prefix is None:
            expected_prefix = data[:2]
        if self.interface is None:
            return False, bytearray("No Interface", 'utf-8')

        try:
            with self._timed("reply"), self.lock:
                request_data = [0x00] * (self.settings.HID_REPORT_SIZE + 1)  # First byte is Report ID
                request_data[1:len(data) + 1] = data
                request_report = bytes(request_data)

                self.interface.write(request_report)

                # Drain stale buffered replies until we find the expected prefix or
                # the buffer runs dry. Since protocol v3 the firmware sends no
                # unsolicited replies, so a stale reply here means one thing only:
                # a previous command's response arrived after the host's read timed
                # out (e.g. GET_ID answered late while the keyboard was busy syncing
                # the slave half). This is a safety net for that race, not a normal
                # code path.
                # The first read and the read right after the buffer ran dry use
                # the full caller timeout (the real reply may still be in flight);
                # in-between reads use timeout=0 (non-blocking) to consume
                # already-queued stale replies without extra latency. Only one
                # full-timeout re-wait is granted after the buffer first runs dry,
                # but stale replies returned by that re-wait keep the drain going
                # instead of being misreported as the response.
                _MAX_DRAIN = 16
                response_report = bytearray()
                waited_after_drain = False
                for _i in range(_MAX_DRAIN):
                    t = timeout if _i == 0 else 0
                    response_report = self.interface.read(self.settings.HID_REPORT_SIZE, timeout=t)
                    if not response_report:
                        if _i == 0 or waited_after_drain:
                            break
                        # Buffer exhausted after draining stale replies;
                        # wait once more for the actual response.
                        waited_after_drain = True
                        response_report = self.interface.read(self.settings.HID_REPORT_SIZE, timeout=timeout)
                        if not response_report:
                            break
                    if response_report.startswith(expected_prefix):
                        return True, response_report
                    # Stale reply — keep draining
        except Exception as e:
            return False, bytearray(f"Exception: {e}", 'utf-8')

        return response_report.startswith(expected_prefix), response_report

    def close_interface(self):
        """Close the raw-HID interface without attempting to reopen it.

        Call this before returning from a failed OTA sequence so that pending
        overlapped I/O operations (Windows) are cancelled and the polling loop
        can re-enumerate cleanly on the next cycle.
        """
        with self.lock:
            if self.interface:
                try:
                    self.interface.close()
                except Exception:
                    pass
                self.interface = None

    def drain_replies(self, max_msgs: int = 16, timeout_ms: int = 20) -> int:
        """Discard any buffered HID replies; return the number discarded.

        Call this before starting a new command sequence to prevent stale
        responses from previous commands (e.g. polling loop timeouts that
        arrived late) from being mistaken for the new command's reply.
        """
        if self.interface is None:
            return 0
        drained = 0
        with self.lock:
            for _ in range(max_msgs):
                try:
                    r = self.interface.read(self.settings.HID_REPORT_SIZE, timeout=timeout_ms)
                    if not r:
                        break
                    drained += 1
                except Exception:
                    break
        return drained

    def wait_for_reconnect(self, timeout_s: int = 60) -> bool:
        """Close the current interface and poll until the device reappears.

        Called after OTA_BEGIN when flash_range_erase() on the RP2040 disables
        all interrupts (including USB) for up to ~30 s.  Returns True once the
        raw-HID interface is open again, False if timeout_s elapses first.
        """
        with self.lock:
            if self.interface:
                try:
                    self.interface.close()
                except Exception:
                    pass
                self.interface = None

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            interfaces = [i for i in hid.enumerate(self.settings.VID, 0)
                          if i['product_id'] in self.settings.KNOWN_PIDS]
            raw = [i for i in interfaces
                   if i['usage_page'] == self.settings.HID_RAW_USAGE_PAGE
                   and i['usage'] == self.settings.HID_RAW_USAGE]
            if raw:
                try:
                    with self.lock:
                        self.interface = self._open_raw(raw[0])
                    return True
                except Exception:
                    pass
            time.sleep(0.5)
        return False

    REBOOT_RECONNECTED = "reconnected"
    REBOOT_NEVER_LEFT = "never-left"
    REBOOT_NO_RETURN = "no-return"

    def _raw_interfaces(self):
        """The raw PolyKybd interfaces on the bus now. Raises: hid.enumerate
        fails on USB churn, which a reboot is."""
        return [i for i in self._enumerate(self.settings.VID)
                if i['product_id'] in self.settings.KNOWN_PIDS
                and i['usage_page'] == self.settings.HID_RAW_USAGE_PAGE
                and i['usage'] == self.settings.HID_RAW_USAGE]

    def other_raw_paths(self) -> set:
        """The paths of the raw PolyKybd interfaces on the bus that are not the
        open one. ``wait_for_reboot`` skips them in its return phase; take the
        snapshot BEFORE the command that reboots the keyboard, or a keyboard
        that rebooted and came back under a new path while that command's
        reply was awaited counts as a bystander and is never reopened. Empty
        when nothing is open or the enumeration fails (no exclusion then)."""
        if not self.interface:
            return set()
        try:
            return {i.get('path') for i in self._raw_interfaces()} - {getattr(self, "interface_path", None)}
        except Exception as e:  # noqa: BLE001 — see _raw_interfaces; no snapshot means no exclusion
            log.debug("Enumeration failed before the reboot wait: %s", e)
            return set()

    def wait_for_reboot(self, timeout_s: int = 30, gone_timeout_s: int = 10,
                        poll_s: float = 0.1, clock=time.monotonic, sleep=time.sleep,
                        others=None) -> str:
        """Wait for the device to LEAVE the bus and come back, then re-open it.

        ``wait_for_reconnect`` re-opens the first raw interface it finds, and
        right after FW_UP_APPLY that is still the OLD device: the keyboard
        acknowledges, then takes hundreds of milliseconds to tear USB down. On
        2026-10-19 the apply dialog reported "reconnected" 80 ms after sending
        APPLY, 3.5 minutes before the keyboard actually came back, and an
        overlay send then ran into the dying handle. So this waits in two
        phases: gone (no raw interface enumerated, up to ``gone_timeout_s``),
        then back (``timeout_s``).

        Returns REBOOT_RECONNECTED with the interface open, REBOOT_NEVER_LEFT
        when the device stayed enumerated for ``gone_timeout_s`` (the apply did
        not reboot it), or REBOOT_NO_RETURN when it left and did not come back.
        A device already absent at the first look counts as gone.

        ``others`` is the :meth:`other_raw_paths` snapshot the caller took before
        sending the command that reboots the keyboard; None takes it now, which
        is right only when the keyboard cannot have come back yet.
        """
        # The device that was open, by path: the gone phase waits for THAT one.
        # A second PolyKybd on the bus (not a supported setup, but possible) would
        # otherwise keep the list non-empty while the flashed one reboots.
        gone_path = getattr(self, "interface_path", None) if self.interface else None

        def raw_interfaces():
            # An enumeration error is "unknown", not "absent": the gone phase
            # keeps waiting and the return phase retries, so a churn error before
            # the old device left cannot end the wait and let the old device be
            # reopened.
            return self._raw_interfaces()

        # The other raw interfaces on the bus are not the flashed keyboard, so
        # the return phase must not open one of them: once the flashed one has
        # left, they are all the enumeration lists. The returning device may
        # come back under another path, so it is matched by exclusion, not by
        # gone_path.
        bystanders = set(others) if others is not None else self.other_raw_paths()
        with self.lock:
            if self.interface:
                try:
                    self.interface.close()
                except Exception:  # noqa: BLE001 — a handle to a device that is rebooting; nothing to do with the error
                    pass
                self.interface = None

        def still_there():
            try:
                raw = raw_interfaces()
            except Exception as e:  # noqa: BLE001 — see raw_interfaces
                log.debug("Enumeration failed during the reboot wait: %s", e)
                return True
            if gone_path is None:
                return bool(raw)
            return any(i.get('path') == gone_path for i in raw)

        deadline = clock() + gone_timeout_s
        while still_there():
            if clock() >= deadline:
                return self.REBOOT_NEVER_LEFT
            sleep(poll_s)

        deadline = clock() + timeout_s
        while clock() < deadline:
            try:
                raw = raw_interfaces()
            except Exception as e:  # noqa: BLE001 — see raw_interfaces
                log.debug("Enumeration failed during the reboot wait: %s", e)
                raw = []
            raw = [i for i in raw if i.get('path') not in bystanders]
            if raw:
                try:
                    with self.lock:
                        self.interface = self._open_raw(raw[0])
                    return self.REBOOT_RECONNECTED
                except Exception:
                    pass
            sleep(0.5)
        return self.REBOOT_NO_RETURN

    def send_and_read(self, data: bytearray, timeout: int) -> tuple[bool, bytearray]:
        if self.interface is None:
            return False, bytearray("No Interface", 'utf-8')

        request_data = [0x00] * (self.settings.HID_REPORT_SIZE + 1) # First byte is Report ID
        request_data[1:len(data) + 1] = data
        request_report = bytes(request_data)

        try:
            with self._timed("reply"), self.lock:
                self.interface.write(request_report)
                response_report = self.interface.read(self.settings.HID_REPORT_SIZE, timeout=timeout)
        except Exception as e:
            return False, bytearray(f"Exception: {e}", 'utf-8')

        return True, response_report


class DisconnectedHid(HidHelper):
    """What ``PolyKybd.hid`` holds after an open FAILED: a helper with no device.

    It used to be None, and roughly sixty call sites dereference ``keeb.hid``
    without a check. A job queued before the reconnect probe noticed the
    keyboard was gone then raised ``AttributeError: 'NoneType' object has no
    attribute 'send_and_read_validate'`` -- every time the device vanished
    while the firmware rebooted after a flash (field, 2026-10-01). This one
    finds nothing to open, so every call takes HidHelper's own
    ``interface is None`` branch and answers "No Interface", the same answer a
    device with no raw interface gives."""

    def _enumerate(self, vid):
        return []

    def reopen_console(self) -> bool:
        return False

    def wait_for_reconnect(self, timeout_s: int = 60) -> bool:
        return False

    def wait_for_reboot(self, timeout_s: int = 30, gone_timeout_s: int = 10, **_kw) -> str:
        return HidHelper.REBOOT_NO_RETURN

    def other_raw_paths(self) -> set:
        return set()

