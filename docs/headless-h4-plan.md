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
