# H4 — GUI as a socket client (design)

Builds on H1–H3 (`docs/headless-core-plan.md`). Goal: the Qt tray GUI can run
as a **pure client** of a core that lives in another process, reached over the
existing control socket — no in-process `PolyCore`. Approved approach: **H4a
first, behind a flag, with the in-process GUI staying the default** (zero
regression), then daemon-by-default (H4b) and forwarder-as-client (H4c).

## The seam (from the host.py reconnaissance)

`PolyHost` touches the core in four ways:

1. **Plain state** — `connected`, `device_present`, `paused`,
   `last_applied_connected`, `kb_sw_version`, `mapping`. All derivable from the
   `status_changed` event + `status.get()`. *Easy.*
2. **Core methods already on the wire** — language, brightness, idle, overlay
   enable/disable/reset/send, keymap layer-count/default/buffer/set, fw.version,
   pause, mru.save, commands.execute, settings get/set, fw.flash, update.*.
   *Reuse as-is.*
3. **Core methods not yet on the wire** — `subscribe` (event seam),
   `tick_window_tracking` (stays main-thread-local), `apply_reconnect`
   (client renders from the `reconnect`/`status_changed` events instead),
   `load/save_overlay_mapping`, `shutdown` (= `host.shutdown`).
4. **Sub-object reach-through** — the hard part (see below).

## Architecture

```
PolyHost (Qt client)  ──RPC/events──>  ControlServer ── PolyCore (+worker, devices)
        │                                   (in a daemon, or another GUI's embedded server)
        └─ RemoteCore: implements the subset of the PolyCore API host.py calls,
           backed by RpcClient; an event-subscription thread feeds pushed
           notifications into WorkerBridge.job_done (same names as today).
```

`--connect[=<endpoint>]` selects client mode; **default stays in-process**
(`PolyHost` owns `PolyCore` + `ControlServer` exactly as today).

## Hard edges & proposed handling

- **Raw HID / firmware flash** (`cmd_menu` reaches `keeb.hid`; `HidFwUpDialog`).
  HID is device-local. In client mode the GUI must **not** open the HID device;
  route flashing through the already-wired `fw.flash` RPC + the `fw_flash_*`
  event stream (a small Qt progress dialog driven by events, replacing the
  QThread-on-local-HID dialog). *New work, but bounded.*
- **Layout editor** (`worker.run_sync` for keymap reads). Synchronous worker
  calls can't cross the socket as-is. Options: (a) make the `keymap.*` RPC calls
  blocking client-side (they already return `(ok,payload)`), driving the dialog
  off RPC responses; (b) keep the editor disabled in client mode for the first
  slice. *Proposed: (a), but as a later H4a slice.*
- **Device geometry** (`device_settings.MATRIX_ROWS/COLUMNS` in the layout
  dialog). Add a `device.info` RPC returning the static model (name, hw, matrix
  size, features) so the client can render without a local `DeviceSettings`.
- **Updater events** — the GUI's in-process updater emits in-process objects;
  the core's `check_update`/`install_update` already emit JSON. In client mode
  the GUI uses the core's update path (RPC) and renders the JSON events.
- **device_mgr inspection** (MRU inspector, mock dump) — debug-only; gate behind
  "local core only" or add read RPCs later. Not on the H4a critical path.

## New RPC methods H4a will add
`device.info`, `overlay.mapping_load`, `overlay.mapping_save`,
`overlay.data_get` (current overlay for manual resend), `activate_bootloader`,
`set_handedness`, `settings.list` (bulk get for the settings dialog).

## Slices (each independently testable, in-process default unchanged)

- **H4a-1** — `RemoteCore` adapter + `--connect` flag + event-subscription
  bridge; cover the *easy* surface (state, language, brightness, idle, overlay
  enable/disable/send, pause, mru, settings, fw.version, status). Tray icon +
  status + language menu + overlay activity work as a remote client. Layout
  editor and flash temporarily disabled in client mode.
- **H4a-2** — `device.info` + `settings.list`; enable the settings dialog and
  the layout editor over RPC.
- **H4a-3** — firmware flash from the client via `fw.flash` + an event-driven
  progress dialog; `activate_bootloader`/`set_handedness`.
- **H4b** — daemon-by-default: autostart launches the headless daemon, the GUI
  attaches. Revisits autostart **without touching** the Windows `.bat`/`.vbs`
  wrapper chain (only what it launches).
- **H4c** — forwarder as a control-socket client: the active-window report
  unifies onto the socket (`window.report`), retiring/【thinning the TCP relay.

## Test strategy
RemoteCore unit tests against a fake RpcClient (method mapping + event→bridge
translation); an end-to-end test that starts a real headless core + connects a
RemoteCore and drives status/language/overlay; the Qt-free import guard stays
green (RemoteCore must not be needed headless, but must itself be importable).

## Status (2026-06-14) — H4a-1 DONE
- **RemoteCore** — `polyhost/client/remote_core.py`, tested end-to-end against a
  real `ControlServer` (`tests/client/remote_core_test.py`): two-connection
  model, status caching, method round-trip, the (ok,payload) contract, event
  fan-out + cache refresh, synthesize-disconnect on stream end.
- **`--connect` client mode** — `main_app.py` adds `--connect[=ENDPOINT]`
  (skips autostart + the single-instance lock; it attaches to the existing
  core). `PolyHost(client_mode=, endpoint=)` builds a RemoteCore instead of a
  PolyCore, renders from `status_changed` (no `apply_reconnect` on RemoteCore),
  does the **client-side** OS-language switch, and guards every device-coupled
  menu (cmd menu / layout / settings / release-firmware / MRU debug) — those
  stay in-process for now. Quitting the client leaves the daemon running.
- **Co-located firmware flash** — a "Flash firmware .bin…" action picks a local
  path and calls `flash_firmware(path, apply=True)` over RPC, with an
  event-driven progress dialog on `fw_flash_*`/`fw_apply_*`. Works when GUI +
  daemon share a filesystem.
- **GUI harness** — `tests/gui/host_client_test.py`: each `PolyHost`
  construction runs in its own subprocess (Qt singleton + pynput-needs-X), Qt
  forced to `offscreen`, input helper mocked. Covers default-mode construction
  (regression guard) and client-mode connect/render/quit. Skipped unless
  `DISPLAY` is set — run `xvfb-run -a … -m unittest …` to exercise. Installing
  `x11-xserver-utils` (xrandr) lets the in-process path construct under xvfb too.
- `polyctl.RpcClient.events()` now ends on `OSError` as well as `EOFError`.

## Status (2026-06-14) — H4a-2a: settings dialog over RPC
- `settings.list` RPC (`PolyCore.settings_list` / `RemoteCore.settings_list`);
  the settings dialog now opens in client mode, reads the daemon's settings
  over RPC, and pushes changed keys back via `settings.set`.
- Hardware-found H4a-1 follow-ups also fixed: client-mode update check no longer
  reached `self.keeb`; the keyboard-firmware *check* is skipped in client mode
  (no `firmware_update_action` there); language changes route through
  `core.set_language`; headless window tracking `CoInitialize`s on Windows; the
  core installs `Logger.debug_detailed` so headless overlay sends work.

## Status (2026-06-14) — H4a-2b: layout editor over RPC
`KbLayoutDialog` now takes `core` instead of `keeb`+`worker` and drives all
keymap I/O through `core.keymap_layer_count/buffer/default_layer/set` — which
return an identical `(ok, payload)` in BOTH modes (PolyCore via `worker.run_sync`,
RemoteCore via RPC). So "Configure Keymap" works for an in-process or a
`--connect` GUI with no dialog-internal mode branching. Matrix geometry comes
from `DeviceSettings` (static, available locally), so no `device.info` was
needed. Validated by the GUI harness (opens the editor in client mode over the
socket) + an offscreen construction smoke.

### Deferred to later H4a slices
- Keyboard-firmware *release* download+flash from a truly remote GUI (needs a
  daemon-side `fw.update` RPC; co-located local-bin flash works today).
- The advanced device-command submenu (`CommandsSubMenu`) over RPC.

## Status (2026-06-14) — H4b-1: daemon-by-default (opt-in, mechanism in place)
**host.py and the Windows autostart `.bat`/`.vbs` chain are deliberately
untouched** — all the new logic is Qt-free and lives in `main_app.py` +
`polyhost/server/daemon_launch.py`, and it reuses the H4a `--connect` client
path. Opt-in via the new **`daemon_mode` setting (default False)**, overridable
per launch with `--daemon` / `--no-daemon`. When off, startup is byte-for-byte
the legacy behavior (zero regression).

- `daemon_launch.decide_startup_mode(outcome, daemon_mode)` — **pure** decision
  over a `probe_existing()` outcome: daemon_mode off ⇒ legacy (LIVE→defer,
  STALE→in-process); on ⇒ LIVE→**attach as client**, STALE→**spawn daemon +
  attach**, INCOMPATIBLE/AUTH→defer (never fight over the HID device).
- `daemon_launch.spawn_headless_daemon()` — launches `python -m polyhost
  --headless --no-autostart` **detached** (`DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP`
  on Windows, `start_new_session` on POSIX, stdio → DEVNULL) so the daemon
  outlives the GUI. The GUI spawns it as a child of its **own venv-activated
  process**, so it inherits PATH — sidestepping the autostart PATH landmine.
- `daemon_launch.wait_until_live()` — polls the endpoint until the spawned
  daemon answers `hello`; on timeout the GUI terminates the child and **falls
  back to in-process** (never two device owners).
- `main_app.py`: for a plain GUI launch only, reads `daemon_mode` (or
  `--daemon/--no-daemon`), runs the decision, and flips `client_mode`/`endpoint`
  accordingly. A daemon-mode GUI **still registers autostart** (it brings the
  daemon up on login); the spawned daemon runs with the new internal
  `--no-autostart` so it never touches the GUI's autostart entry.
- Tested: `tests/server/daemon_launch_test.py` (decision table, detached-spawn
  flags via a mocked Popen, polled wait). The Qt-free import guard stays green.

### Validated on a real desktop (Windows, 2026-06-14)
- Spawn→attach end-to-end, daemon survival across GUI restart, the separate
  `daemon_log.txt` / `polykybd_console.txt`, and the connect-time keyboard
  overlay reset (the headless MRU-parity fix). macOS/Linux still rely on the
  same individually-exercised pieces + the in-process fallback.

## Status (2026-06-14) — H4b-2: daemon-by-default is now the default
`daemon_mode` defaults to **True** (`polyhost/settings.py`). A plain
`python -m polyhost` now spawns/attaches a headless daemon; `--no-daemon` (or
the setting) opts out. Non-disruptive: settings `load()` uses `setdefault`, so
existing configs keep their persisted value — adopt it via the settings dialog
("Daemon → Mode", auto-generated from the settings dict) or
`polyctl settings set daemon_mode true`. **No autostart change**: autostart still
launches the GUI, which reads the setting and brings the daemon up, so the
Windows `.bat`/`.vbs` chain is untouched. `decide_startup_mode` already returns
IN_PROCESS for `daemon_mode` off and CLIENT/SPAWN_CLIENT for on, so only the
default value changed.

### Deferred to later H4b slices
- Optionally moving autostart to launch the daemon directly (vs. the GUI
  spawning it) — only after confirming the venv/PATH story holds for a cold
  scheduler launch (the documented `.bat` wrapper concern). Not needed for
  daemon-by-default; the GUI-spawns-daemon path already delivers it.
- macOS/Linux end-to-end validation of the spawn→attach flow.

## Status (2026-06-14) — H4c-1: window.report RPC (safe subset)
The active-window report now has a control-socket entry point: a `window.report`
RPC (`M_WINDOW_REPORT`) → `PolyCore.report_window(handle, name, title)` →
`RemoteHandler.report_window`, which writes the **same `connections` store the
cross-machine TCP relay feeds**, so the existing remote matching (`remote_changed`
/ `try_to_match_window_remote`) picks it up unchanged. `polyctl window report
--name … [--handle …] [--title …]` drives it; the GUI/CLI can now inject a window
report into the daemon's remote tracking over the local socket. No device I/O
(it just stores the report; the next window tick applies it).

**Deliberately the safe subset** (per the scoping decision): the cross-machine
TCP wire and `receive_from_forwarder` are **untouched** (the field forwarder
keeps working as-is), and the matcher is **not** deduped yet.

### Deferred to a follow-up (H4c-2, "the advanced version")
- Kill the duplicate matcher: `RemoteHandler.try_to_match_window_remote` is a
  near-copy of `OverlayHandler.try_to_match_window`. Extract one shared matcher
  both paths use.
- Route `receive_from_forwarder` through `report_window` so the TCP relay is a
  thin transport over the unified entry point (no bespoke dict stash).
- Cross-machine validation (needs two machines + hardware).

## Host integration — concrete plan & a hard CONSTRAINT
**Constraint discovered: `polyhost/host.py` cannot be imported or run in the
dev/CI container** — `pynput` (imported at host.py top) requires an X server;
the Qt `xcb` plugin is missing system libs; constructing `PolyHost` under
`xvfb-run` aborts. There is also **no automated coverage** of `PolyHost`. So
every host.py change (its `__init__` runs in the *default* in-process path too)
must be validated on a real desktop — blind edits risk the working tray app.

The `--connect` client-mode wiring (next slice) needs, in `host.py`:
1. `PolyHost.__init__(..., client_mode=False, endpoint=None)`; in client mode
   build `self.core = RemoteCore.connect(...)` and **do not** alias
   `self.keeb/worker/device_mgr` (they don't exist on RemoteCore) — guard every
   consumer.
2. A **client-mode status renderer**: RemoteCore has no `apply_reconnect`, so the
   GUI must render from the `status_changed` event (text/icon/connected/lang)
   instead of calling `core.apply_reconnect(snapshot)`.
3. **Client-side OS-language switch**: the daemon doesn't change the *client*
   machine's OS language; the GUI must still call `helper.set_language` when
   `status_changed.lang` changes.
4. Guard the device-coupled menus in client mode: `CommandsSubMenu` (takes
   `keeb`), the layout editor (`worker.run_sync` + `device_settings`),
   `send_shortcuts` (`device_mgr.all_entries`), debug menus; skip
   `worker.start()`, the embedded `ControlServer`, and the active-window timer
   (the daemon owns window tracking).
5. `quit_app` already does `core.shutdown()` — RemoteCore.shutdown() closes the
   client sockets only, leaving the daemon running. Good as-is.

## OPEN DECISION — flashing firmware from a remote GUI
`fw.flash` takes a **server-side path** — the `.bin` must live on the *daemon's*
machine. So:
- **Co-located GUI + daemon (the H4b target):** a "Flash a .bin…" action that
  picks a local path and calls `core.flash_firmware(path, apply)` works directly
  (same filesystem), with an event-driven progress dialog on `fw_flash_*`.
- **Truly remote GUI:** the release auto-download writes the `.bin` on the
  *client*, which the daemon can't read. That needs either daemon-side
  download+flash (a new `fw.update` RPC) or byte upload over the socket — a
  design choice, not a wire-up. Deferred until chosen.

## Future work — forwarder transport unification (H4c-2 / H4d)

Status today (H4c-1, shipped): the cross-machine forwarder still uses the
**bespoke TCP relay** — `polyhost/handler/remote_window.py` `receive_from_forwarder`
listens on TCP **port 50162** and `PolyForwarder.send_to_host` sends plaintext
`"{handle};{name};{title}"`. H4c-1 only added a *local* control-socket entry
point: the `window.report` RPC → `PolyCore.report_window` → `RemoteHandler.report_window`,
which writes the **same `connections` store** the TCP relay feeds, so the existing
remote matcher picks it up unchanged.

### H4c-2 — dedupe the matcher, route the TCP receiver through `report_window`
- `RemoteHandler.try_to_match_window_remote` is a near-copy of
  `OverlayHandler.try_to_match_window` (two matchers to keep in sync). Extract one
  shared matcher both call.
- Make `receive_from_forwarder` call `core.report_window(...)` (via a callback)
  instead of stashing into the `connections` dict directly, so the TCP relay
  becomes a thin transport over the single unified entry point.
- Keeps the TCP wire; cross-machine behavior unchanged. Needs two machines to
  validate.

### H4d — networked control endpoint (retire the bespoke TCP relay)
Make the forwarder a **real control-protocol client over the network** that calls
the `window.report` RPC, instead of the plaintext TCP relay. The protocol layer
already supports this: `multiprocessing.connection` works with an `AF_INET`
address plus the existing HMAC authkey + `hello` version gate. One transport and
one matcher for local *and* remote.

**Pros**
- Single protocol/code path (control socket) for local + remote; deletes the
  bespoke relay + plaintext wire.
- Authenticated + version-gated, vs today's relay which accepts unauthenticated
  plaintext from anyone who can reach port 50162.

**Cons / must-solve-first**
- **Security surface.** The control socket exposes *device control* — brightness,
  language, **firmware flash**, bootloader. Binding the *full* registry to the
  network gates all of it behind only the authkey. Do **not** simply bind the
  existing endpoint to `AF_INET`.
- **Key distribution.** The authkey is per-machine (0600 in the config dir); the
  forwarder needs the daemon's key shared across machines.
- Both machines must be updated together (the wire changes).

**Recommended first slice (safe):** a **dedicated, window-report-only network
listener** — a separate `AF_INET` endpoint whose method registry contains *only*
`window.report` (not the full control registry), with its own authkey, leaving
the bootloader/flash/etc. surface on the local-only endpoint. That delivers the
authenticated unified report path without exposing the device-control surface to
the network. Then `PolyForwarder.send_to_host` is replaced by an RPC client call,
and the legacy `receive_from_forwarder`/port-50162 relay can be retired (or kept
one release for compatibility).
