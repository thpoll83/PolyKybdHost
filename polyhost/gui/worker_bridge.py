"""Qt bridge between the HID worker thread and the GUI main thread.

The worker runs ``on_done`` callbacks on its own thread (see
``polyhost/device/hid_worker.py``); those callbacks must never touch Qt
objects directly. Instead they emit :class:`WorkerBridge.job_done`, a queued
signal that Qt delivers on the main thread, where the host dispatches on the
job name.

The reconnect decision logic is factored into :func:`decide_reconnect_apply`,
a pure (Qt-free) function so it can be unit-tested without a QApplication.
"""
from PyQt5.QtCore import QObject, pyqtSignal


class WorkerBridge(QObject):
    """Carries worker-thread ``on_done`` results onto the Qt main thread."""

    # (job name, result) — result is fn's return value or the raised exception.
    job_done = pyqtSignal(str, object)


def decide_reconnect_apply(snapshot, host_protocol, host_version, ignore_version):
    """Pure decision tree for the reconnect compatibility check.

    Mirrors the original ``PolyHost.reconnect`` logic byte-for-byte in
    behaviour. Takes a worker-produced ``snapshot`` dict (no device/UI access)
    plus the host's expected protocol/version and the ``--ignore-version`` flag.

    Returns a dict describing the UI decision:
        connected (bool)        — final connected state
        compatible (bool)       — whether the post-connect work should run
        icon (str|None)         — status icon filename, or None to leave as-is
        text (str|None)         — status action text, or None to leave as-is
        do_post_connect (bool)  — run add_supported_lang / resend / etc.

    ``snapshot`` keys consumed here:
        version_ok (bool)       — query_version_info result
        version_msg (str)       — query_version_info message
        kb_version (str|None)   — get_sw_version()
        kb_proto (int|None)     — get_protocol_version()
        name (str|None)         — get_name()
        hw_version (str|None)   — get_hw_version()
    """
    version_ok = snapshot["version_ok"]
    msg = snapshot["version_msg"]
    connected = version_ok
    if not connected and ignore_version:
        # FW version string could not be parsed — continue via --ignore-version.
        connected = True

    out = {
        "connected": connected,
        "compatible": False,
        "icon": None,
        "text": None,
        "do_post_connect": False,
    }
    if not connected:
        out["icon"] = "sync_disabled.svg"
        out["text"] = msg
        return out

    kb_version = snapshot["kb_version"]
    kb_proto = snapshot["kb_proto"]
    name = snapshot["name"]
    hw_version = snapshot["hw_version"]
    compatible = False

    if kb_proto is not None:
        if kb_proto == host_protocol:
            compatible = True
            out["icon"] = "sync.svg"
            out["text"] = f"PolyKybd {name} {hw_version} (FW {kb_version}, P{kb_proto})"
        else:
            out["icon"] = "sync_disabled.svg"
            out["text"] = (
                f"Protocol mismatch: host P{host_protocol}, firmware P{kb_proto}. "
                f"Please update.")
            connected = False
    else:
        expected = host_version
        if kb_version and kb_version.startswith(expected[:3]):
            compatible = True
            if kb_version != expected:
                out["icon"] = "sync_problem.svg"
                out["text"] = (
                    f"PolyKybd {name} {hw_version} ({kb_version}, please update firmware!)")
                out["version_warning"] = (expected, kb_version)
            else:
                out["icon"] = "sync.svg"
                out["text"] = f"PolyKybd {name} {hw_version} ({kb_version})"
        else:
            out["icon"] = "sync_disabled.svg"
            out["text"] = f"Incompatible version: {msg}, expected {expected}, got {kb_version}."
            connected = False

    if not compatible and ignore_version:
        compatible = True
        connected = True
        out["icon"] = "sync_problem.svg"
        ver = kb_version or "?"
        nm = name or "PolyKybd"
        out["text"] = f"{nm} FW {ver} — version check bypassed (--ignore-version)"
        out["ignore_bypass_msg"] = msg

    out["connected"] = connected
    out["compatible"] = compatible
    out["do_post_connect"] = compatible
    return out
