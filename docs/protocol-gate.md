# Protocol, versions and the connect gate

Moved out of `CLAUDE.md` 2026-09-14. Verbatim.

### Protocol, versions and the connect gate

- **Version handling is RANGE-connect + per-feature gating (not exact-match).** The
  reconnect gate (`polyhost/core/decisions.py` `decide_reconnect_apply`) connects to any
  firmware whose protocol is **≥ `MIN_SUPPORTED_PROTOCOL`** (= 2, the packed-lang-list
  floor — below it the host can't even enumerate languages, so it refuses with *"Firmware
  too old… please update the keyboard firmware"*). Within range it connects regardless of
  match: `== __protocol__` is the fully-supported case (`sync.svg`), a **lower** device
  protocol connects with *"— some features need a firmware update"* (`sync_problem.svg`),
  and a **higher** one (newer firmware than the host) **prompts** — see the newer-firmware
  note below. Each
  feature is then gated individually by **`FEATURE_MIN_PROTOCOL`** (`device/poly_kybd.py`)
  via the pure `protocol_supports(protocol, feature)` + `PolyKybd.supports()/capabilities()`;
  the GUI (`host.py` `self.supports()`, fed by the `capabilities` dict on `status_changed`/
  `status.get`) disables the Idle-Style / Glyph-Script submenus a keyboard is too old for,
  the CLI's `set_*` still returns the device-layer "too old" error, and `polyctl status`
  lists supported/unsupported features. This replaced the old exact-match gate that greyed
  out the **whole** menu on any mismatch (which had "been forgotten twice", leaving current
  keyboards rejected).

- **Every new device-facing command MUST be version-gated — no exceptions.** When you add a
  HID command that the firmware only understands from protocol **N**: add a
  `FEATURE_MIN_PROTOCOL` entry (`device/poly_kybd.py`); guard the `PolyKybd` setter with
  `self.supports("<feature>")` (return the "firmware too old" error when unsupported) and the
  getter likewise; gate the GUI menu in `host.py` `managed_connection_status` via
  `self.supports(...)`; surface it in `polyctl`; and bump `__protocol__` + the firmware
  `PROTOCOL_VERSION` to **N** in the same change. If the command *changes an existing
  command's wire format*, ALSO add an encode-branch on `self.protocol_version` (see the
  plain-overlay upload below). An **ungated** command silently connects then NACKs at
  runtime on an older keyboard instead of cleanly disabling — the exact failure the
  range-connect model exists to prevent, and the kind of gate that "has been forgotten
  twice". The capability tests in `tests/device/poly_kybd_capabilities_test.py` are the
  pattern to extend.

- **Wire-format-divergent commands are ENCODED for the device's protocol, not blocked.**
  The only core command whose wire format ever changed is the **plain-overlay upload**
  (P11 packed the modifier+segment into one header byte). `send_overlay_for_keycode`
  (`device/poly_kybd.py`) branches on `self.protocol_version`:
  `>= OVERLAY_PACKED_HEADER_MIN_PROTOCOL (11)` sends the packed 4-byte header, below it the
  pre-v11 5-byte `[id, cmd, keycode, modifier, segment]` form — so overlays work on an older
  keyboard too. Compressed/ROI headers never changed. For a device **newer** than the host
  (only reachable via the "ignore" newer-firmware choice) we send our newest-known (packed)
  form and accept that a *future* breaking change to an existing command is unknown to us.
  If you add another wire-format-breaking change to an existing command, add a
  `FEATURE_MIN_PROTOCOL` entry + an encode-branch here; a *new* command just needs a
  `supports()` gate.

- **Newer firmware than the host PROMPTS the user (session policy, default safe).** When
  `kb_proto > __protocol__`, blindly trusting a newer firmware for wire-format-sensitive
  commands is risky, so instead of silently connecting the host asks (dialog
  `polyhost/gui/newer_firmware_dialog.py`, three choices): **Safe mode** (connect but
  restrict to the stable set — firmware-update + Debugging; the default and the
  dismiss/close outcome), **Check for updates** (run the host-app update check via the
  `_on_update_clicked` idiom with `force=True`; install if a matching release is found, else
  fall back to safe), or **Connect anyway** (full connect, newest-known formats). The choice
  is a **session-only** core policy `PolyCore._newer_fw_policy` (like `ignore_version`; keyed
  to the protocol it was chosen for so a re-flash re-asks) set via
  `set_newer_firmware_policy(choice)` → `M_SET_NEWER_FW_POLICY` (RemoteCore mirror) →
  drops `last_applied_connected` so the next probe re-applies. Safe mode is
  `decide_reconnect_apply`'s newer branch: `connected=True` (so the probe doesn't churn) but
  `compatible=False`/`safe_mode=True`, `tick_window_tracking` skips overlay/OS traffic while
  `safe_mode`, and the status carries `safe_mode` + `newer_fw_pending` (with capabilities
  reported all-False, so feature menus grey out). The GUI drives the dialog off that status
  seam in **both** in-process (`_apply_reconnect_result`) and `--connect` client
  (`_render_remote_status`) paths — `_maybe_prompt_newer_firmware`, once per protocol per
  session. `--ignore-version` still forces a full connect (wins over the safe default). A
  headless daemon with no GUI defaults to safe; drive it with `polyctl newer-policy
  [ignore|safe]`.

- **Still bump `__protocol__` (`polyhost/_version.py`) in lockstep with the firmware
  PROTOCOL_VERSION.** It now defines the host's *newest-known* protocol (the fully-supported
  "match" and the newest wire format the host emits), **not** a hard connect gate. Rule of
  thumb unchanged: when you add a firmware-protocol feature threshold (e.g.
  `IDLE_STYLE_MIN_PROTOCOL`, `GLYPH_SCRIPT_MIN_PROTOCOL`, `OVERLAY_PACKED_HEADER_MIN_PROTOCOL`),
  the firmware protocol advanced to **N**, so set `__protocol__` to **N** and add the feature
  to `FEATURE_MIN_PROTOCOL` in the same change. Forgetting it now only downgrades the status
  to "update the host app" and disables that one feature (the keyboard still connects), rather
  than rejecting the keyboard outright.

- **Firmware update survives protocol mismatches**: `PolyHost.device_present` tracks "a device answers protocol-independent queries (GET_ID/GET_LANG)" separately from `connected` (protocol/version compatible). The flash/apply/bootloader actions and the release-update flow gate on `_fw_actions_allowed()` (present, not paused) — NOT on `connected` — so a keyboard on a mismatched protocol can always be updated (`CommandsSubMenu.update_enabled` re-enables exactly those items when the rest of the menu is greyed out). The HID flash protocol (`hid_fw_up`) is dispatched independently of `PROTOCOL_VERSION` in the firmware. Don't re-gate any firmware-update path on `self.connected`.

- **When the BOARD changes something the host caches, the answer is a counter on a
  reply the host ALREADY polls — not a new poll, and not a push.** The reconnect probe
  sends GET_ID + GET_LANG every second (`RECONNECT_CYCLE_MSEC`), so the firmware's
  `['G'][u16 state_generation]` block in the GET_ID reply reaches the host within ~1 s
  at zero additional reports; the host re-reads whatever view is open when the value
  moves. Worst case is a few seconds, not one — the probe skips inside
  `OVERLAY_PROBE_COOLDOWN_S` and `decide_probe_publish` debounces three strikes — which
  is irrelevant for a UI refresh. Full rationale, including why the console and an
  unsolicited raw report both lose, is in `qmk_firmware/CLAUDE.md` § *Telling the host
  something changed ON THE BOARD*.
  - ⚠️ **`parse_id_version_block` finds the font-pack block POSITIONALLY** — it requires
    `'V'` at exactly `nul + 1` (`device/hid_fontpack.py`) — so anything the firmware
    adds to the GET_ID reply has to go AFTER it. Prepending would make every deployed
    host read "no bundles on the device" and re-flash all eight bundles on every
    connect. Parse tag-led blocks in order; never assume a fixed offset for the second
    one.
  - ⚠️ **The raw channel is strictly request/response, and `send_and_read_validate`'s
    drain depends on it.** Its comment carries the invariant — *"Since protocol v3 the
    firmware sends no unsolicited replies, so a stale reply here means one thing only"*
    — so an unsolicited report from the keyboard is discarded by the next probe, and
    making it work means framing plus routing in exactly the code path that stale-reply
    bugs live in. That invariant is a design decision, not an accident: v3 made
    `SEND_OVERLAY_MAPPING` silent to REDUCE escaped ACKs.

- **Single-key keymap write**: the firmware supports `ID_DYNAMIC_KEYMAP_SET_KEYCODE` (0x05) — payload is `[layer, row, col, keycode_hi, keycode_lo]`. No need to write a full layer; `PolyKybd.set_dynamic_keycode()` wraps this.

- **`hid_reconnect_retries` is clamped to ≥1 in `PolyKybd.connect()`** (`max(1, …)`, `device/poly_kybd.py`): `connect()` runs on every ~1 s reconnect probe, and with the setting at 0 the `range(retries)` GET_ID loop was skipped entirely, so it blindly re-enumerated the HID interface every probe — `Re-enumerating HID after 0 failed attempts…` log spam plus handle churn that can clip in-flight overlay transfers. **Nothing in the codebase writes this key** (grep-verified) — a 0/negative value is a hand-edit or stale config, not a code path; default is 5 (`settings.py`). Don't remove the clamp.

