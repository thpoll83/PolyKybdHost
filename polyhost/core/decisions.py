"""Pure (Qt-free) decision logic for the reconnect state machine.

Moved verbatim from ``polyhost/gui/worker_bridge.py`` as part of the
headless-core plan (H1): the core must be importable without PyQt5, and
these functions are consumed by :class:`polyhost.core.poly_core.PolyCore`.
``polyhost.gui.worker_bridge`` re-exports them for compatibility.
"""


def decide_probe_publish(connected_now, last_applied_connected, fail_streak,
                         threshold=3):
    """Debounce for the reconnect probe. Returns (publish, new_streak).

    The keyboard goes deaf for hundreds of ms after a large overlay transfer
    (it is syncing the images to the slave half over UART), so a single failed
    probe right after a send must NOT flap the connection state — doing so
    resets the MRU cache and forces a full overlay resend, which keeps the
    keyboard busy and makes the next probe fail too: a self-sustaining
    wipe-and-resend oscillation. Only after ``threshold`` consecutive failures
    is a disconnect published. Successful probes always publish and clear the
    streak; an already-disconnected device keeps publishing (cheap no-op
    applies, matching the old 1 s "Reconnect failed" cadence).
    """
    if connected_now:
        return True, 0
    streak = fail_streak + 1
    if last_applied_connected and streak < threshold:
        return False, streak
    return True, streak


def decide_reconnect_apply(snapshot, host_protocol, host_version, ignore_version,
                           min_supported=2, newer_fw_policy=None):
    """Pure decision tree for the reconnect compatibility check.

    The host connects across a **range** of firmware protocols and gates
    individual features by their minimum protocol (see
    ``polyhost.device.poly_kybd.FEATURE_MIN_PROTOCOL``), instead of refusing the
    whole connection on any protocol mismatch. A device is connected when its
    protocol is at least ``min_supported`` (the floor below which the host can't
    even enumerate languages); an exact match is the fully-supported case, a
    lower protocol connects with a "some features need a firmware update" hint,
    and a higher protocol (newer firmware than the host) is governed by
    ``newer_fw_policy`` — a session choice the user makes in a dialog:
    ``"ignore"`` connects fully (host uses the commands/formats it knows — see the
    overlay encode-branch), ``"safe"`` connects in a restricted **safe mode** (only
    firmware-update + debugging), and ``None`` (undecided) defaults to safe mode and
    flags ``newer_fw_pending`` so the UI prompts.

    Takes a worker-produced ``snapshot`` dict (no device/UI access) plus the
    host's expected protocol/version, the ``--ignore-version`` flag, the
    ``min_supported`` protocol floor, and the ``newer_fw_policy`` session choice.

    Returns a dict describing the UI decision:
        connected (bool)        — final connected state
        compatible (bool)       — whether the post-connect work should run
        icon (str|None)         — status icon filename, or None to leave as-is
        text (str|None)         — status action text, or None to leave as-is
        do_post_connect (bool)  — run add_supported_lang / resend / etc.
        safe_mode (bool)        — connected but operationally restricted (newer fw)
        newer_fw_pending (bool) — newer fw and no policy chosen yet -> prompt

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
        "safe_mode": False,
        "newer_fw_pending": False,
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
        if kb_proto < min_supported:
            # Too old for the host to speak to at all (can't enumerate languages).
            out["icon"] = "sync_disabled.svg"
            out["text"] = (
                f"Firmware too old (P{kb_proto}); host needs P{min_supported}+. "
                f"Please update the keyboard firmware.")
            connected = False
        else:
            # Within the supported range -> connect and feature-gate individually.
            compatible = True
            base = f"PolyKybd {name} {hw_version} (FW {kb_version}, P{kb_proto})"
            if kb_proto == host_protocol:
                out["icon"] = "sync.svg"
                out["text"] = base
            elif kb_proto < host_protocol:
                out["icon"] = "sync_problem.svg"
                out["text"] = base + " — some features need a firmware update"
            else:  # kb_proto > host_protocol — newer firmware than the host.
                out["icon"] = "sync_problem.svg"
                if newer_fw_policy == "ignore":
                    # User chose to connect fully; the host sends its newest-known
                    # command formats (see the overlay encode-branch).
                    out["text"] = base + " — update the host app for full support"
                else:
                    # "safe" or undecided (None) -> restricted safe mode. Stays
                    # connected (so the probe doesn't churn) but compatible=False,
                    # so no operational post-connect work runs.
                    compatible = False
                    out["safe_mode"] = True
                    out["newer_fw_pending"] = newer_fw_policy is None
                    out["text"] = base + " — safe mode (update the host app)"
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
        # --ignore-version is an explicit "connect fully" override; it wins over the
        # newer-firmware safe default too.
        out["safe_mode"] = False
        out["newer_fw_pending"] = False
        out["icon"] = "sync_problem.svg"
        ver = kb_version or "?"
        nm = name or "PolyKybd"
        out["text"] = f"{nm} FW {ver} — version check bypassed (--ignore-version)"
        out["ignore_bypass_msg"] = msg

    out["connected"] = connected
    out["compatible"] = compatible
    out["do_post_connect"] = compatible
    return out
