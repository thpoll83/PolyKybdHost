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
