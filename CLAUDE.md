# CLAUDE.md — PolyKybdHost

This file provides guidance to Claude Code (claude.ai/code) when working in the **PolyKybdHost** repo (the Python host software).

For cross-repo context (how this repo relates to `qmk_firmware/` and `AdafruitGFX/`), see [`../CLAUDE.md`](../CLAUDE.md).

## Code review conventions (all PolyKybd repos)

- **Docstring coverage: ignore CodeRabbit's "Docstring Coverage … threshold 80%" pre-merge check.** That 80% target is a CodeRabbit default, **not** a project policy — the check is non-blocking and we deliberately do not chase it. Do **not** add docstrings to existing functions just to satisfy it (out-of-scope churn). Document new code where a docstring genuinely helps a reader, and no more.

## Branching (all PolyKybd repos)

- **Give every branch a name that hints at its content.** When creating a branch, append a short, descriptive slug describing the change (e.g. `claude/fix-firmware-update-menu-daemon-mode`, not just the auto-generated `claude/<random-scientist>-<id>`). The random scientist/id suffix from Claude Code on the web is auto-assigned server-side and can't always be overridden mid-session, but whenever a branch name is chosen by us, make it self-explanatory so the branch list reads as a changelog.
- **Always start new work on a FRESH branch cut from the updated default branch — never keep committing to a branch whose PR has already merged.** Once a PR is merged, that branch is done: `git fetch origin <default>` (and for the next piece of work `git checkout -b claude/<new-slug> origin/<default>`). Cherry-pick only the still-unmerged commits onto the fresh branch if needed. This keeps each PR a clean, focused diff against the current default (`main` for host/rig, `PolyKybd` for the firmware) and avoids a new PR accidentally re-including already-merged commits.

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
- `polyhost/__main__.py` → `polyhost/main_app.py` — CLI parsing, selects which class to start. **Daemon-by-default (H4b)**: when the `daemon_mode` setting is on (**default True** as of H4b-2) or `--daemon` is passed, a plain GUI launch runs the core in a separate `--headless` daemon and attaches this GUI to it as a `--connect` client — spawning the daemon (detached) if none is running, falling back to in-process if it can't come up. `--no-daemon` (or the setting) forces legacy in-process startup (use it for development, so code edits run in the same process as the GUI). Settings `load()` uses `setdefault`, so flipping the default is non-disruptive — existing configs keep their persisted value (use the settings dialog's "Daemon → Mode" toggle or `polyctl settings set daemon_mode true` to adopt it). The decision/spawn logic is Qt-free in `polyhost/server/daemon_launch.py` (`decide_startup_mode`/`spawn_headless_daemon`/`wait_until_live`); **host.py and the autostart `.bat`/`.vbs` chain are untouched** (autostart launches the GUI, which reads the setting and brings the daemon up). The GUI-spawned daemon runs with the internal `--no-autostart` so it never disturbs the GUI's autostart entry.
- `polyhost/core/poly_core.py` — `PolyCore`: the **Qt-free operational core** (headless-core plan H1). Owns the device stack (`PolyKybd`, `DeviceManager`, `HidWorker` + periodics), the reconnect probe + `apply_reconnect` decision/state, overlay send/cmd jobs, the window-tracking tick (`tick_window_tracking`), overlay mapping, `Sunlight`, MRU persistence and the sleep listener. Communicates results **only** through observer callbacks — `subscribe(cb)` / `emit(name, payload)` with JSON-serializable payloads (names/contracts in `polyhost/core/events.py`). Must stay importable without PyQt5 and without a display (pywinctl is lazy-imported; window tracking degrades to off). Guarded by `tests/core/import_guard_test.py`.
- `polyhost/core/decisions.py` — Qt-free `decide_probe_publish` / `decide_reconnect_apply` (re-exported from `gui/worker_bridge.py` for compatibility).
- `polyhost/host.py` — `PolyHost(QApplication)`: Normal-mode **Qt client**. Owns `PolyCore`, the tray icon, menus and dialogs; subscribes to core events and marshals them onto the Qt main thread via `WorkerBridge.job_done` (the event names match `_on_job_done`'s dispatch). Connection state (`connected`/`device_present`/`paused`/`last_applied_connected`/`kb_sw_version`/`mapping`) are **properties over the core** — the core is the single source of truth. The active-window QTimer stays on the main thread (pywinctl/macOS constraint) and just calls `core.tick_window_tracking()`.
- `polyhost/server/` — **control socket** (headless-core H2). `protocol.py`: stdlib `multiprocessing.connection` transport (UDS / Windows named pipe + authkey), UTF-8 JSON framing, JSON-RPC message shapes, the `hello` version gate, platformdirs endpoint+authkey (0600), and the canonical `M_*` method-name constants. `control_server.py`: `ControlServer` — accept loop + per-connection reader threads, a method registry dispatching to `PolyCore` (core `(ok,payload)` failures → JSON-RPC `ERR_DEVICE`), and core-event fan-out to subscribed clients. `instance.py`: the socket doubles as the single-instance lock. `PolyHost` embeds a `ControlServer` (M1); the CLI/headless server reuse it. `window_report_server.py`/`window_report_client.py` (H4d): a **separate, opt-in** `AF_INET` listener (`WindowReportServer`, port `WINDOW_REPORT_PORT=50163`) that serves **only** `window.report` — same `hello`+authkey gating, but a **separate authkey** (`window_report_authkey_path()`) and **no `PolyCore` reference** (only an injected `report_window` callback), so the network surface can never reach device control/flash/bootloader. `HeadlessHost` starts it only when `window_report_network_enabled` is set (default False); the forwarder pushes to it with `--report-rpc`. The legacy plaintext TCP relay (port 50162) is untouched and still the default.
- `polyhost/cli/polyctl.py` — **`polyctl`** console-script (stdlib-only, never imports Qt): `status`, `lang list|set`, `brightness`, `idle`, **`idle-style [pulse|jitter]`** (get/set the idle anti-burn-in style over HID cmd 28 — `M_IDLE_STYLE_GET/SET` → `PolyCore.get/set_idle_style` → `PolyKybd`, firmware v4+), `overlay …`, `keymap …`, `commands`, `fw version`, **`fw flash <bin> [--apply]`**, `pause|resume`, `mru save`, `settings get|set`, **`update check|install`**, **`window report`**, `watch`, `shutdown`. Long ops (`fw flash`, `update install`) subscribe to events and stream progress to a terminal event — `RpcClient` exposes `subscribe_events()`/`events()` (the latter ends on `EOFError`/`OSError`); `watch()` builds on them. Talks the `protocol.py` wire format to the control socket.
- `polyhost/headless.py` — **`--headless`** (M2, H3): `HeadlessHost` runs `PolyCore` + `ControlServer` + the core-owned window tick with **zero Qt import** in the process (`main_app` imports Qt/`PolyHost` lazily, only in the GUI branch — guarded by `tests/headless/headless_entry_test.py` and the import guard). The core auto-applies its own reconnect snapshots headless (`PolyCore(apply_reconnect_in_core=True)`). On a `polyctl update install`, the core only applies+emits; `HeadlessHost` re-execs (or hands off to the Windows relay) on `update_finished_ok`/`update_relay_needed`. Drive it with `polyctl`. Two headless gotchas fixed the hard way: the core-owned window-tick thread must **`pythoncom.CoInitialize()` on Windows** (pywinctl uses COM; a fresh thread without it fails every poll with "Invalid syntax"); and `poly_core` imports `polyhost.util.log_util` so `Logger.debug_detailed` (used by the device code) exists in the headless process too (the GUI got it via `host.py`). The daemon writes `daemon_log.txt`; `main_app` maps `--debug 2` → `DEBUG_DETAILED` for headless too (mirroring the GUI), so the daemon's `debug_detailed` lines — e.g. window-report receipts (`report_window` / `receive_from_forwarder`, level 8) — are only visible at `--debug 2`, not `--debug 1` (DEBUG=10). The tray GUI's log viewer adds a **"Daemon Log"** tab when `daemon_log.txt` exists (so daemon-mode reconnect/overlay/window activity is visible from the GUI side).
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
- **Active-window backend selection** (in both `active_window.py` and `forwarder.py`): `XDG_CURRENT_DESKTOP == "KDE"` → `kde_win_reporter` (KWin script → journal); else `XDG_SESSION_TYPE == "wayland"` → `gnome_wayland_reporter`; else → `pywinctl` (X11). `gnome_wayland_reporter.py` is **⚠️ UNTESTED on hardware** — pywinctl can't see native Wayland windows, so it queries our own purpose-built, **read-only** *PolyKybd Window Reporter* GNOME Shell extension (`org.polykybd.WindowReporter`, repo `thpoll83/gnome-wayland-winreader`) over `gdbus` via a single `GetFocusedWindow()` call (the extension exposes no window-modifying methods, unlike the general *Window Calls* extension it replaces); **without the extension it falls back to pywinctl (X11/XWayland)** — so X11-backed apps (Chrome, VS Code, JetBrains, …) under XWayland are still tracked, native Wayland windows are not — and warns **once** (instead of pywinctl's silent Wayland failure). The fallback imports pywinctl **lazily + guarded** (it can `sys.exit()` with no X server), so the module still loads with zero pywinctl/Qt at import (headless-safe). The fallback is only consulted when the extension is *unavailable* — an extension that's up but reports "no focused window" returns None directly (so a stale XWayland window can't mask it). The **X11 path is unaffected** (it never enters the Wayland branch); only the output parsing + fallback routing are unit-tested. Full GNOME-Wayland coverage still needs the extension or an Xorg login session.

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

- **Bump `__protocol__` (`polyhost/_version.py`) in lockstep with the firmware PROTOCOL_VERSION** — the reconnect gate (`polyhost/core/decisions.py`) connects **only on an exact match** (`kb_proto == host_protocol`); any mismatch shows *"Protocol mismatch, please update"* and refuses to connect, so the keyboard never reaches the features that bump motivated. **This has been forgotten twice** (host stayed at P3 while firmware features advanced to P4 *idle-style* and P5 *brightness host-auto*, leaving current keyboards rejected). Rule of thumb: whenever you add a firmware-protocol feature threshold (e.g. `IDLE_STYLE_MIN_PROTOCOL`, `_BRIGHTNESS_FLAGS_PROTOCOL` — the `>= N` runtime feature gates), the firmware protocol has advanced to **N**, so `__protocol__` must be set to **N** in the same change. The feature `>= N` gates are layered checks *on top of* the exact-match connect gate — they only ever fire once `__protocol__` already equals the device's protocol.
- **Font-pack bundles (protocol 6+)**: the external-flash font pack ships as **N
  per-family bundles** (`polyhost/res/fontpack/<id>.plyf` + `bundles.json`), not one
  blob. `query_id()` parses the per-bundle `content_version` block the firmware
  appends to the `GET_ID` reply (binary, **after** the string's NUL — parsed from the
  RAW bytes before `.decode()`) into `keeb.fontpack_bundle_versions`. On a fresh
  connect, `PolyCore._fontpack_autocheck_job` flashes only the bundles the device is
  missing/behind on (`hid_fontpack.decide_stale_bundles` vs `bundles.json`), each to
  its slot via `flash_fontpack(..., bundle_id=)`. The guard is
  **`_fontpack_flash_in_progress`** (re-entrancy only — cleared on completion), so a
  physical reconnect after a wipe re-checks; do **NOT** reintroduce a once-per-process
  guard (that broke re-flash after wipe). `polyctl fontpack status|sync|flash <id>|wipe [id]`
  is the manual path; the tray surfaces flash progress (`_on_fontpack_progress/done`).
  Firmware-side architecture (slots, layout header, GET_ID block) is in the qmk repo's
  CLAUDE.md "Font pack" section.
- **Font-pack inspect/extend tools** (`polyhost/gui/fontpack_inspector_dialog.py` +
  `fontpack_extend_dialog.py`, Qt-free logic in `polyhost/services/fontpack_*` +
  `fontgen*`): a tray-launchable / standalone window to view every bundle glyph as
  the keycap draws it and to build/splice new glyphs from a TTF/OTF (pure-Python
  `fontconvert` parity). The inspector honours **front-to-back precedence** (the
  firmware renders each codepoint from the lowest-global-index font that has it):
  a duplicate that loses is shown **dim grey** ("overridden by …"), and a slot
  empty in this font but drawn by another pack font is shown **cyan** ("drawn by
  …"), so shadowed/duplicate glyphs aren't mistaken for missing. The inspector's
  **"Peek empty (from source)"** toggle
  renders the *empty* slots from their source font (via `fontpack_extend.peek_source_glyph`
  + the shipped render settings, needs the source font downloaded) as **amber
  previews** — candidates you can then double-click to edit/take; they are not in
  the pack. The extend dialog's **Source fonts** browser (always under the
  preview; click a font to use it, downloading first if needed) downloads/assigns
  the Noto source fonts via `polyhost/services/font_downloader.py`, which reads the
  catalog from **`polyhost/res/fonts/noto-fonts.yaml`**. ⚠️ That YAML is the **single
  source of truth shared byte-identically** with the firmware's
  `qmk_firmware/keyboards/polykybd/fonts/noto-fonts.yaml` (which `dl-fonts.sh` reads)
  — keep both in sync (`cmp`). The host stores a *flat* cache keyed on
  `basename(dest)`; the firmware honours the nested `dest` path.
  When you **edit** a glyph, the dialog pre-fills the render controls (size,
  dither, normalize/invert/edge/outline, render size, yAdvance, …) from
  **`polyhost/res/fontpack/fontpack_render_settings.json`** — a `global ALL_FONTS
  index → fonts.yaml options` map emitted by the firmware's `generate_fonts.py`
  (`RENDER_SETTINGS`) and shipped here. The `.plyf` carries only rendered bitmaps,
  not the fontconvert options, so this manifest is the only way to recover "the
  settings this glyph was built with". Each record also carries `source_file` (the
  basename of the source TTF, matching `noto-fonts.yaml`), so the edit dialog
  **auto-fills the source font from the download cache** when it's present (else it
  names the file and points at "Download Noto…"/Browse) — the TTF itself isn't
  bundled. Keep it in sync with the firmware copy
  (`base/fonts/generated/fontpack_render_settings.json`).
- **Linux HID permissions**: `polyhost/device/99-hid.rules` must be installed as a udev rule for non-root HID access.
- **Venv**: always use `PolyKybdHost/.venv/bin/python` — system `python3` lacks numpy, PyQt5, and other runtime deps. **In a fresh remote/web container the `.venv` does not exist yet** — create it and install the test deps: `python3 -m venv .venv && .venv/bin/pip install numpy pyserial hid platformdirs pyyaml pillow`, plus the hidapi **system** libs `sudo apt-get install -y libhidapi-hidraw0 libhidapi-libusb0` (the `hid` module raises `ImportError: Unable to load any of the following libraries:libhidapi-*` without them). That set is enough to run the device/unit tests (`tests.device.*`); GUI tests additionally need an X server (see below).
- **`hid_reconnect_retries` is clamped to ≥1 in `PolyKybd.connect()`** (`max(1, …)`, `device/poly_kybd.py`): `connect()` runs on every ~1 s reconnect probe, and with the setting at 0 the `range(retries)` GET_ID loop was skipped entirely, so it blindly re-enumerated the HID interface every probe — `Re-enumerating HID after 0 failed attempts…` log spam plus handle churn that can clip in-flight overlay transfers. **Nothing in the codebase writes this key** (grep-verified) — a 0/negative value is a hand-edit or stale config, not a code path; default is 5 (`settings.py`). Don't remove the clamp.
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

