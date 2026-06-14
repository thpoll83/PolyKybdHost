# CLAUDE.md — PolyKybdHost

This file provides guidance to Claude Code (claude.ai/code) when working in the **PolyKybdHost** repo (the Python host software).

For cross-repo context (how this repo relates to `qmk_firmware/` and `AdafruitGFX/`), see [`../CLAUDE.md`](../CLAUDE.md).

## Commands

### Run the application
```bash
python -m polyhost                        # standard
python -m polyhost --debug 1              # basic debug logging
python -m polyhost --debug 2              # verbose debug logging
python -m polyhost --host <IP>            # forward to remote host
python -m polyhost --portable             # no autostart registration
```

### Run tests
```bash
# Use the project venv — system python3 is missing numpy and other deps
.venv/bin/python -m unittest discover -v -s ./tests -p "*_test.py"   # all tests
.venv/bin/python -m unittest tests.device.cmd_composer_test           # single module
```

### Install
```bash
pip install -e .
```

## Operating modes

**Normal mode** (default): PolyKybdHost runs on the machine the keyboard is physically connected to. It owns the HID device, tracks the active window, and pushes overlay/icon/keymap updates directly to the keyboard.

**Forwarder mode** (`--host <IP>` or `--host-file <file>`): runs on a *remote* machine that has no keyboard attached. `PolyForwarder` watches the active window on that machine and relays the window title/app info over TCP to the Normal-mode instance on the keyboard machine. This lets a single keyboard serve multiple computers — the keyboard always reflects what's focused on whichever machine the user is currently working on.

## Architecture

**PolyKybdHost** is a PyQt5 system-tray application that bridges the PolyKybd HID keyboard device to the host OS. It tracks the active window and sends overlay/keymap/language commands to the device over HID.

### Entry & top-level classes
- `polyhost/__main__.py` → `polyhost/main_app.py` — CLI parsing, selects which class to start
- `polyhost/core/poly_core.py` — `PolyCore`: the **Qt-free operational core** (headless-core plan H1). Owns the device stack (`PolyKybd`, `DeviceManager`, `HidWorker` + periodics), the reconnect probe + `apply_reconnect` decision/state, overlay send/cmd jobs, the window-tracking tick (`tick_window_tracking`), overlay mapping, `Sunlight`, MRU persistence and the sleep listener. Communicates results **only** through observer callbacks — `subscribe(cb)` / `emit(name, payload)` with JSON-serializable payloads (names/contracts in `polyhost/core/events.py`). Must stay importable without PyQt5 and without a display (pywinctl is lazy-imported; window tracking degrades to off). Guarded by `tests/core/import_guard_test.py`.
- `polyhost/core/decisions.py` — Qt-free `decide_probe_publish` / `decide_reconnect_apply` (re-exported from `gui/worker_bridge.py` for compatibility).
- `polyhost/host.py` — `PolyHost(QApplication)`: Normal-mode **Qt client**. Owns `PolyCore`, the tray icon, menus and dialogs; subscribes to core events and marshals them onto the Qt main thread via `WorkerBridge.job_done` (the event names match `_on_job_done`'s dispatch). Connection state (`connected`/`device_present`/`paused`/`last_applied_connected`/`kb_sw_version`/`mapping`) are **properties over the core** — the core is the single source of truth. The active-window QTimer stays on the main thread (pywinctl/macOS constraint) and just calls `core.tick_window_tracking()`.
- `polyhost/server/` — **control socket** (headless-core H2). `protocol.py`: stdlib `multiprocessing.connection` transport (UDS / Windows named pipe + authkey), UTF-8 JSON framing, JSON-RPC message shapes, the `hello` version gate, platformdirs endpoint+authkey (0600), and the canonical `M_*` method-name constants. `control_server.py`: `ControlServer` — accept loop + per-connection reader threads, a method registry dispatching to `PolyCore` (core `(ok,payload)` failures → JSON-RPC `ERR_DEVICE`), and core-event fan-out to subscribed clients. `instance.py`: the socket doubles as the single-instance lock. `PolyHost` embeds a `ControlServer` (M1); the CLI/headless server reuse it.
- `polyhost/cli/polyctl.py` — **`polyctl`** console-script (stdlib-only, never imports Qt): `status`, `lang list|set`, `brightness`, `idle`, `overlay …`, `keymap …`, `commands`, `fw version`, **`fw flash <bin> [--apply]`**, `pause|resume`, `mru save`, `settings get|set`, **`update check|install`**, `watch`, `shutdown`. Long ops (`fw flash`, `update install`) subscribe to events and stream progress to a terminal event — `RpcClient` exposes `subscribe_events()`/`events()` (the latter ends on `EOFError`/`OSError`); `watch()` builds on them. Talks the `protocol.py` wire format to the control socket.
- `polyhost/headless.py` — **`--headless`** (M2, H3): `HeadlessHost` runs `PolyCore` + `ControlServer` + the core-owned window tick with **zero Qt import** in the process (`main_app` imports Qt/`PolyHost` lazily, only in the GUI branch — guarded by `tests/headless/headless_entry_test.py` and the import guard). The core auto-applies its own reconnect snapshots headless (`PolyCore(apply_reconnect_in_core=True)`). On a `polyctl update install`, the core only applies+emits; `HeadlessHost` re-execs (or hands off to the Windows relay) on `update_finished_ok`/`update_relay_needed`. Drive it with `polyctl`. Two headless gotchas fixed the hard way: the core-owned window-tick thread must **`pythoncom.CoInitialize()` on Windows** (pywinctl uses COM; a fresh thread without it fails every poll with "Invalid syntax"); and `poly_core` imports `polyhost.util.log_util` so `Logger.debug_detailed` (used by the device code) exists in the headless process too (the GUI got it via `host.py`).
- `polyhost/client/remote_core.py` — **`RemoteCore`** (H4a): the GUI-as-socket-client adapter. `python -m polyhost --connect[=ENDPOINT]` runs the tray GUI as a pure client of a core in another process — `RemoteCore` mirrors the subset of the `PolyCore` API `host.py` consumes, over the control socket (two connections: one for request/response, one for the event subscription), and re-emits server events to the same `subscribe`/`emit` seam. State is cached from `status.get` + `status_changed`. `PolyHost(client_mode=, endpoint=)` builds it instead of a `PolyCore`, renders from `status_changed` (not `apply_reconnect`), does the **client-side** OS-language switch, and guards every device-coupled menu (cmd menu / layout editor / keyboard-firmware release / MRU debug); the settings dialog + a co-located "Flash firmware .bin…" (over the `fw.flash` RPC) work in client mode. Quitting the client closes its sockets only — the daemon keeps running.
- `polyhost/forwarder.py` — `PolyForwarder`: Forwarder mode; no device access, only TCP window reporting

### Device communication (`polyhost/device/`)
- `poly_kybd.py` — `PolyKybd`: primary device interface; HID communication, command dispatch, state management. Uses 64-byte HID reports (protocol v0.7.0+). Long-running ops (`send_overlays`, `send_overlays_mru`, `execute_commands`, `press_and_release_key`) take an optional `threading.Event` cancel token.
- `hid_worker.py` — `HidWorker`: dedicated device thread + coalescing job queue (pure Python, no Qt). **All HID I/O runs here after `PolyHost.__init__`** — see "Threading model" below. Full contract in `docs/hid-worker-refactor.md`.
- `hid_helper.py` — device enumeration/access via `hid` (hidapi)
- `cmd_composer.py` / `command_ids.py` — command building and HID ID enums
- `bit_packing.py` — binary packing helpers for HID payloads
- `poly_kybd_mock.py` — drop-in mock device for running without hardware

### Platform input abstraction (`polyhost/input/`)
Abstract base `unicode_input.py` with per-platform implementations:
- `win_helper.py` — Windows (pynput)
- `macos_helper.py` — macOS (pynput)
- `linux_gnome_helper.py` — GNOME/X11 (pynput + X11)
- `linux_kde_helper.py` — KDE Plasma (D-Bus)

### Window/overlay handler (`polyhost/handler/`)
- `active_window.py` — `OverlayHandler`: active-window tracking, triggers keymap/language/overlay switches on the device based on which app is focused
- `remote_window.py` — TCP-based window title relay for multi-machine setups
- `kde_win_reporter.py` — KDE D-Bus integration for window events

### GUI (`polyhost/gui/`)
PyQt5 widgets: main window (`host.py`), settings dialog, command menu, log viewer, layout editor (`layout_dialog/`), tray icon state manager.

### Configuration (`polyhost/settings.py`)
YAML config persisted to XDG config dir via `platformdirs`. Covers unicode composition mode, brightness/daylight settings (solar calculations via `pvlib`/`geocoder`), HID rate limits, and debug flags.

### Services (`polyhost/services/`)
- `unicode_cache.py` — pre-computed unicode character mappings
- `sunlight_helper.py` — adaptive brightness via solar irradiance
- `add_to_startup.py` — OS autostart registration (see Key notes below)

## Threading model (HID worker)

Since the HID-worker refactor (`docs/hid-worker-refactor.md`), the Qt main thread does **no device I/O** after `PolyHost.__init__` (the one synchronous `connect()` at startup — which seeds `device_present` for firmware-action gating — is the only exception). There is deliberately **no synchronous language enumeration at startup**: `self.connected` can only be set by the reconnect decision tree (that's where the protocol/version gate lives), so the first worker probe always sees a False→True transition and runs the full fresh-connect flow (enumerate + menu build + unicode mode + cache reset). A startup enumerate just duplicated all of it within the first second (double menu build, field 2026-06-13) — don't re-add one.

- `HidWorker` (`polyhost/device/hid_worker.py`) owns the device. Periodic tasks on the worker: reconnect probe (1 s), console/serial reads (250 ms), daylight brightness incl. its network lookups (10 min).
- UI code enqueues jobs (`worker.submit`); overlay sends use `coalesce_key="overlay"` so rapid app switches supersede/cancel stale transfers instead of replaying them. Dialogs use `worker.run_sync` (short bounded block; raises `RuntimeError` while suspended). Firmware flash/apply wraps the dialog in `worker.exclusive()`; tray pause maps to `suspend()`/`resume()`, and `exclusive()` restores the prior suspend state on exit.
- `PolyCore` periodics/jobs publish results as core events (`emit(name, payload)`); the Qt client's observer (`PolyHost._on_core_event`) forwards them into `WorkerBridge.job_done` (`polyhost/gui/worker_bridge.py`), a queued Qt signal dispatched in `PolyHost._on_job_done`. **Worker-/core-side code must never touch Qt objects** — go through the event seam. `decide_reconnect_apply` lives in `polyhost/core/decisions.py` (re-exported from `worker_bridge`), unit-tested in `tests/gui/worker_bridge_test.py`.
- Reconnect is split three ways: `PolyCore._reconnect_probe` (worker, device I/O → plain snapshot dict; pops the firmware fresh-boot marker on every successful probe), `PolyCore.apply_reconnect` (operational half — state, decision tree, post-connect jobs, cache resets; emits `status_changed`; tested in `tests/core/poly_core_apply_test.py`), and `PolyHost._apply_reconnect_result` (Qt rendering: status entry, language menu, OS-language switch). `active_window_reporter` keeps the pywinctl poll on the main thread but delegates the switching decision to `PolyCore.tick_window_tracking`.
- **The probe is debounced** (`decide_probe_publish`, 3 strikes): the keyboard goes deaf for hundreds of ms after a large overlay transfer while it syncs images to the slave half over UART, so a single failed probe must NOT flap the connection state — that resets the MRU cache, wipes the overlays, and forces a resend that keeps the keyboard busy for the next probe (self-sustaining wipe-and-resend oscillation, seen in the field 2026-06-10). For the same reason the probe drains stale late replies first, never queries version/languages when the lang probe already failed (a stale GET_ID reply can fake a fresh connect), and `query_id`/`GET_LANG` use generous read timeouts (250/150 ms — fine on the worker, forbidden back when this ran on the UI thread).

## Key notes

- **Linux HID permissions**: `polyhost/device/99-hid.rules` must be installed as a udev rule for non-root HID access.
- **Venv**: always use `PolyKybdHost/.venv/bin/python` — system `python3` lacks numpy, PyQt5, and other runtime deps.
- **Test discovery**: test files follow `*_test.py` naming under `tests/` mirroring `polyhost/` structure. pytest is disabled in VS Code config; use `unittest`. New test packages require an `__init__.py`.
- **No CI**: no GitHub Actions workflows exist in this repo.
- **GUI tests need a display**: `tests/gui/host_client_test.py` constructs the real `PolyHost` (default + `--connect` client mode) in a subprocess (one `QApplication`/process; `pynput` needs X) with Qt forced to `offscreen`. They **skip unless `DISPLAY` is set** — run them under a virtual X server: `xvfb-run -a .venv/bin/python -m unittest tests.gui.host_client_test`. `host.py` can't even be *imported* without an X server (pynput at module load), so plain `unittest discover` skips them. Installing `x11-xserver-utils` (xrandr) lets the in-process path construct under xvfb too (pywinctl/pymonctl `sys.exit(1)` without it).
- **Single-key keymap write**: the firmware supports `ID_DYNAMIC_KEYMAP_SET_KEYCODE` (0x05) — payload is `[layer, row, col, keycode_hi, keycode_lo]`. No need to write a full layer; `PolyKybd.set_dynamic_keycode()` wraps this.
- **Firmware update survives protocol mismatches**: `PolyHost.device_present` tracks "a device answers protocol-independent queries (GET_ID/GET_LANG)" separately from `connected` (protocol/version compatible). The flash/apply/bootloader actions and the release-update flow gate on `_fw_actions_allowed()` (present, not paused) — NOT on `connected` — so a keyboard on a mismatched protocol can always be updated (`CommandsSubMenu.update_enabled` re-enables exactly those items when the rest of the menu is greyed out). The HID flash protocol (`hid_fw_up`) is dispatched independently of `PROTOCOL_VERSION` in the firmware. Don't re-gate any firmware-update path on `self.connected`.
- **Autostart** (`polyhost/services/add_to_startup.py`): `setup_autostart_for_app()` registers the app to start at login (called from `main_app.py` unless `--portable`).
  - **Windows**: prefers a per-user, **non-elevated logon scheduled task** (`RunLevel Limited` / `LogonType Interactive`, via PowerShell `Register-ScheduledTask`) — needs no admin/UAC and starts earlier than the Startup folder, which Explorer throttles. The task launches the **proven venv-activating `.bat` wrapper** (`create_windows_bat_wrapper`); do **not** swap this for a direct `pythonw -m polyhost` call — running the venv interpreter without activation drops the `Scripts` dir from `PATH` and the app dies silently (regressed once, see git history). The `.bat` is run **windowless** through `wscript.exe` + a hidden-launch `.vbs` (`create_windows_hidden_vbs`, window style 0) so no console flashes. Falls back to a Startup-folder shortcut if task creation is refused (locked-down Task Scheduler). Gotchas learned the hard way: `New-ScheduledTaskAction -Argument ''` is rejected — only pass `-Argument` when non-empty; and f-strings with backslashes in the expression part break on Python < 3.12.
  - **Linux**: `.desktop` autostart entry; **macOS**: `launchd` plist.
  - `get_autostart_status()` reports which mechanism is in place (printed at startup); `remove_autostart()` tears all of them down. `--portable` removes any existing entry rather than just skipping registration.
- **Layout dialog** (`polyhost/gui/layout_dialog/`): fully implemented — layer switching re-renders all key labels from the cached buffer; clicking a key then selecting from the browser writes immediately to the device via `set_dynamic_keycode()` and keeps the local buffer in sync. `RenderableKey` carries `matrix_index` for row/col derivation.

