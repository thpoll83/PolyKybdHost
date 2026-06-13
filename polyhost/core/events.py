"""Core → client event names and payload contracts (headless-core plan §2.3).

Events are emitted by :class:`polyhost.core.poly_core.PolyCore` through its
observer callbacks as ``(name, payload)`` with **JSON-serializable payloads**
(plain dicts/tuples/strings) so the in-process observer (Qt GUI via
``WorkerBridge``) and the future socket transport (H2) carry identical data.

Callbacks fire on core/worker threads — clients marshal to their own loop.
The Qt client forwards every event verbatim into ``WorkerBridge.job_done``,
which is why these names intentionally match the existing
``PolyHost._on_job_done`` dispatch.
"""

# Reconnect probe snapshot (dict, see PolyCore._reconnect_probe) — the GUI
# applies the decision tree and updates menus; headless clients may ignore it
# in favour of STATUS_CHANGED.
RECONNECT = "reconnect"

# Semantic connection state after a probe is applied (JSON dict:
# {connected, device_present, paused, state_changed, text, icon, lang}).
STATUS_CHANGED = "status_changed"

# Overlay send queued ({"state": "thinking"}); cleared by OVERLAY completion.
OVERLAY_ACTIVITY = "overlay_activity"

# (serial_bytes, console_text) read from the keyboard (250 ms cadence).
CONSOLE = "console"

# Overlay send finished (payload: job result or exception) — settles the
# tray "thinking" state.
OVERLAY = "overlay"

# str message — transient warning for the user (tray balloon/CLI line).
OVERLAY_WARNING = "overlay_warning"

# (lang, ok, msg) — result of a change-language job.
CHANGE_KEEB_LANGUAGE = "change_keeb_language"

# (title, msg, result) — generic device command result for logging/UI.
CMD_RESULT = "cmd_result"

# Firmware flash (PolyCore.flash_firmware → `polyctl fw flash`). JSON payloads.
FW_FLASH_PROGRESS = "fw_flash_progress"  # {"pct": int (-1 = indeterminate), "msg": str}
FW_FLASH_DONE = "fw_flash_done"          # {"ok": bool, "msg": str}
FW_APPLY_PROGRESS = "fw_apply_progress"  # {"pct": int, "msg": str}
FW_APPLY_DONE = "fw_apply_done"          # {"ok": bool, "msg": str}

# Updater events. NOTE: two producers with DIFFERENT payload shapes:
#   * The Qt GUI's in-process installer (host.py) emits the original in-process
#     objects (ReleaseInfo / FwUpReleaseInfo / str / (pct, msg)).
#   * PolyCore.check_update / install_update (headless / `polyctl update …`)
#     emit JSON-shaped dicts: update_progress {"pct","msg"},
#     update_finished_ok {"version"}, update_relay_needed {"relay_path"},
#     update_failed {"msg"}. These cross the socket, so they must stay JSON.
# The two paths don't mix today (the GUI drives its own installer, never
# core.install_update); H4 unifies them.
UPDATE_AVAILABLE = "update_available"
FW_UP_AVAILABLE = "fw_up_available"
UPDATE_HOST_NO_UPDATE = "update_host_no_update"
UPDATE_FW_NO_UPDATE = "update_fw_no_update"
UPDATE_CHECK_ERROR = "update_check_error"
UPDATE_PROGRESS = "update_progress"
UPDATE_FINISHED_OK = "update_finished_ok"
UPDATE_RELAY_NEEDED = "update_relay_needed"
UPDATE_FAILED = "update_failed"
FW_DOWNLOAD_PROGRESS = "fw_download_progress"
FW_DOWNLOAD_DONE = "fw_download_done"
