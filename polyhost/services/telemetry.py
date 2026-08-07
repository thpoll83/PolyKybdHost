"""Anonymous usage census for PolyHost.

One small JSON POST per install per day, so we can answer questions that
nothing else can: which host version is actually running in the field, which
firmware is on the keyboards it talks to, and whether updates/flashes are
succeeding out there. It is deliberately NOT an observability SDK — see
``docs/telemetry.md`` for why the OpenTelemetry side lives on the server.

Design rules, in rough order of how badly they bite if broken:

- **Allow-list, never a state dump.** :func:`build_payload` names every field it
  emits and copies nothing else. The host sees active window titles, app names
  and (with daylight brightness on) an approximate location; none of that may
  ever reach here, and the only way to keep that true as ``get_status()`` grows
  is for this module to pull named keys rather than filter a dict.
- **A dead endpoint is a no-op.** Short timeout, no retry storm, every failure
  swallowed. Telemetry that can break the app is worse than no telemetry.
- **The throttle is persisted**, for the same reason the update check's is: an
  in-memory throttle re-fires on every restart, so a user who restarts often
  would ping far more than daily.
- **Qt-free and import-light** — this runs inside ``PolyCore``, which must stay
  importable headless.

The payload carries no timestamp: the server stamps arrival, so there is one
less client-supplied field to trust and clock skew cannot bucket a ping into
the wrong day.
"""
import json
import logging
import math
import platform
import sys
import threading
import time
import uuid
from pathlib import Path

import platformdirs
import requests

from polyhost._version import __protocol__, __version__

log = logging.getLogger(__name__)

#: Payload format version. Bump when a field changes meaning or is removed —
#: the server keeps parsing old hosts, which live in the field for months.
PAYLOAD_SCHEMA = 1

#: Wait between pings. Deliberately a day: this is a census, not monitoring.
SEND_INTERVAL_S = 24 * 60 * 60
#: How often the reporter thread wakes to check whether a ping is due. Cheap —
#: it is a clock comparison, not a request.
TICK_S = 60.0
HTTP_TIMEOUT = 5

USER_AGENT = f"PolyKybdHost/{__version__}"

#: Persisted throttle state, beside the updater's ETag cache.
_STATE_FILE = Path(platformdirs.user_cache_dir("PolyKybdHost")) / "telemetry.json"

#: Event counters, reset after each successful ping. Anything not named here is
#: silently dropped by :meth:`TelemetryReporter.note`, so a future caller cannot
#: invent a counter (and therefore cannot leak one) without editing this tuple.
COUNTER_KEYS = (
    "sessions",           # process starts
    "connects",           # fresh keyboard connects
    "reconnect_flaps",    # connected -> disconnected transitions
    "fw_flashes",         # firmware images flashed
    "fontpack_flashes",   # font-pack bundles flashed
    "update_installs",    # host self-updates applied
)

#: Every key the payload may contain, at the top level. The test suite asserts
#: :func:`build_payload` never emits anything outside this set — that assertion
#: is the actual privacy guarantee, so keep it in sync deliberately.
PAYLOAD_KEYS = frozenset({
    "schema", "install_id", "host_version", "host_protocol",
    "os", "os_release", "arch", "python", "mode", "device", "counters",
})

#: Same, for the nested device block.
DEVICE_KEYS = frozenset({
    "present", "connected", "name", "fw_version", "protocol",
    "hw_version", "fontpack",
})


def new_install_id() -> str:
    """A random, non-identifying install id.

    Deliberately ``uuid4`` and nothing else: no MAC address, no hostname, no
    disk serial, nothing derived from the machine. It exists only so a ping can
    be counted once per install per day, and the user can wipe it by deleting
    the key from ``settings.yaml``.
    """
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Pure decision + payload construction (unit-tested; no I/O)
# ---------------------------------------------------------------------------

def decide_should_send(enabled, endpoint, now, last_sent,
                       interval_s=SEND_INTERVAL_S) -> bool:
    """Is a ping due?

    ``last_sent`` in the future (a clock that moved backwards, or a corrupt
    cache) is treated as "due now" rather than blocking pings until the clock
    catches up — the opposite choice can silence an install for years.
    """
    if not enabled or not endpoint:
        return False
    try:
        last = float(last_sent)
    except (TypeError, ValueError):
        return True
    if not math.isfinite(last) or last <= 0 or last > now:
        return True
    return (now - last) >= interval_s


def _short_python() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _os_release() -> str:
    """Coarse OS release ("11", "14.4", "6.8") — never the full uname string,
    which on Linux carries the build host and kernel config flavour."""
    try:
        rel = platform.release() or ""
    except Exception:
        return ""
    # Keep at most two dotted components: "6.8.0-41-generic" -> "6.8".
    parts = rel.replace("-", ".").split(".")
    return ".".join(p for p in parts[:2] if p.isdigit())


def build_payload(install_id, mode, status=None, fontpack=None, counters=None) -> dict:
    """Build the ping body from named fields only.

    ``status`` is a ``PolyCore.get_status()`` snapshot (cache-only, no device
    I/O, so this is safe from any thread). Every value is copied by name and
    coerced, so a new key appearing in ``get_status()`` can never ride along.
    """
    status = status or {}
    payload = {
        "schema": PAYLOAD_SCHEMA,
        "install_id": str(install_id),
        "host_version": __version__,
        "host_protocol": __protocol__,
        "os": platform.system() or "",
        "os_release": _os_release(),
        "arch": platform.machine() or "",
        "python": _short_python(),
        "mode": str(mode or ""),
        "device": {
            "present": bool(status.get("device_present")),
            "connected": bool(status.get("connected")),
            "name": _text(status.get("name")),
            "fw_version": _text(status.get("fw_version")),
            "protocol": _int_or_none(status.get("protocol")),
            "hw_version": _text(status.get("hw_version")),
            "fontpack": {str(k): _int_or_none(v)
                         for k, v in (fontpack or {}).items()},
        },
        "counters": {k: int(counters.get(k, 0)) for k in COUNTER_KEYS} if counters
                    else {k: 0 for k in COUNTER_KEYS},
    }
    return payload


def _text(value) -> str:
    return "" if value is None else str(value)


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Persisted throttle
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    try:
        data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(data) -> None:
    """Write the throttle state atomically.

    A plain write truncates in place, so a crash — or the RPC thread's forced
    send racing the reporter thread — can leave a half-written file. `_load_state`
    recovers from that by returning `{}`, which reads as "never sent" and lets an
    extra ping through. Write-then-replace closes the window."""
    tmp = None
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STATE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(_STATE_FILE)
    except OSError as e:
        log.debug("Could not save telemetry state: %s", e)
        if tmp is not None:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass


def get_last_sent() -> float:
    try:
        ts = float(_load_state().get("last_sent", 0.0))
    except (TypeError, ValueError):
        return 0.0
    return ts if math.isfinite(ts) and ts >= 0 else 0.0


def set_last_sent(ts, result="") -> None:
    state = _load_state()
    state["last_sent"] = float(ts)
    state["last_result"] = str(result)[:200]
    _save_state(state)


def get_last_result() -> str:
    return str(_load_state().get("last_result", ""))


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def _post(endpoint, payload, timeout=HTTP_TIMEOUT):
    """POST the payload. Returns (ok, message). Never raises."""
    try:
        resp = requests.post(
            endpoint, json=payload, timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"})
        if 200 <= resp.status_code < 300:
            return True, f"HTTP {resp.status_code}"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:  # network down, DNS, TLS, proxy — all a no-op
        return False, f"{type(e).__name__}: {e}"


class TelemetryReporter:
    """Owns the ping cadence on its own daemon thread.

    Not on the HID worker: a stalled POST there would block device I/O behind
    it. The thread only ever reads cached state through ``snapshot_fn``, so it
    does no device I/O of its own.
    """

    def __init__(self, log_, install_id, snapshot_fn, enabled_fn, endpoint_fn,
                 mode="in-process", post_fn=_post, clock=time.time,
                 interval_s=SEND_INTERVAL_S, tick_s=TICK_S):
        self.log = log_
        self.install_id = install_id
        self._snapshot_fn = snapshot_fn
        self._enabled_fn = enabled_fn
        self._endpoint_fn = endpoint_fn
        self.mode = mode
        self._post = post_fn
        self._clock = clock
        self._interval_s = interval_s
        self._tick_s = tick_s

        self._counters = {k: 0 for k in COUNTER_KEYS}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    # -- counters ---------------------------------------------------------
    def note(self, key, n=1):
        """Increment a counter. Unknown keys are ignored, by design."""
        if key not in COUNTER_KEYS:
            return
        with self._lock:
            self._counters[key] += int(n)

    def _take_counters(self):
        with self._lock:
            taken = dict(self._counters)
            self._counters = {k: 0 for k in COUNTER_KEYS}
        return taken

    def _restore_counters(self, taken):
        """Put counters back after a failed send, so nothing is lost to a
        network blip — the next ping carries them."""
        with self._lock:
            for k, v in taken.items():
                if k in self._counters:
                    self._counters[k] += v

    # -- lifecycle --------------------------------------------------------
    def start(self):
        if self._thread is not None:
            return
        # stop() sets the event and never clears it, so without this a start()
        # after a stop() would spawn a thread that returns at its first wait()
        # and report nothing, silently. Same clear-then-start shape as
        # PolyCore.start_window_tracking.
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="telemetry", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _loop(self):
        while not self._stop.is_set():
            # Wait first: never ping in the first seconds of startup, when the
            # keyboard may not have been probed yet and the snapshot would say
            # "no device" for an install that has one.
            if self._stop.wait(self._tick_s):
                return
            try:
                self.maybe_send()
            except Exception:
                self.log.debug("Telemetry tick failed", exc_info=True)

    # -- sending ----------------------------------------------------------
    def maybe_send(self, force=False):
        """Send if due (or ``force``). Returns (sent, message)."""
        endpoint = self._endpoint_fn() or ""
        enabled = bool(self._enabled_fn())
        now = self._clock()
        if not force and not decide_should_send(
                enabled, endpoint, now, get_last_sent(), self._interval_s):
            return False, "not due"
        if not enabled:
            return False, "disabled"
        if not endpoint:
            return False, "no endpoint"

        snapshot, fontpack = {}, {}
        try:
            snapshot, fontpack = self._snapshot_fn()
        except Exception:
            self.log.debug("Telemetry snapshot failed", exc_info=True)

        taken = self._take_counters()
        payload = build_payload(self.install_id, self.mode, snapshot,
                                fontpack, taken)
        ok, msg = self._post(endpoint, payload)
        if ok:
            set_last_sent(now, msg)
            self.log.debug("Telemetry ping sent (%s)", msg)
        else:
            self._restore_counters(taken)
            # Record the attempt so a permanently unreachable endpoint is not
            # retried every tick, only every interval.
            set_last_sent(now, msg)
            self.log.debug("Telemetry ping failed (%s)", msg)
        return ok, msg

    def status(self):
        """Plain dict for `polyctl telemetry status` / the RPC."""
        with self._lock:
            pending = dict(self._counters)
        last = get_last_sent()
        return {
            "enabled": bool(self._enabled_fn()),
            "endpoint": self._endpoint_fn() or "",
            "install_id": self.install_id,
            "mode": self.mode,
            "schema": PAYLOAD_SCHEMA,
            "interval_s": self._interval_s,
            "last_sent": last,
            "last_result": get_last_result(),
            "next_due_in_s": max(0.0, (last + self._interval_s) - self._clock())
                             if last else 0.0,
            "pending_counters": pending,
        }

    def preview(self):
        """The exact payload that would be sent right now — so a user can read
        it before deciding whether to leave telemetry on."""
        snapshot, fontpack = {}, {}
        try:
            snapshot, fontpack = self._snapshot_fn()
        except Exception:
            # Same log as maybe_send: an empty device block in the preview
            # should leave a trace saying why.
            self.log.debug("Telemetry snapshot failed", exc_info=True)
        with self._lock:
            pending = dict(self._counters)
        return build_payload(self.install_id, self.mode, snapshot, fontpack, pending)
