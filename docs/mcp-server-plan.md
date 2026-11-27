# MCP server for AI assistants: plan

**Status:** designed, not built (2026-11-27). The entry in
[`FUTURE_WORK.md`](FUTURE_WORK.md) says why it waits.

## Goal

Let an AI assistant (Claude, ChatGPT, Gemini, Cursor, Codex and others) read and
change the keyboard's state when the user asks in plain language: "switch the
keyboard to Greek", "put the meeting controls on F1 to F4", "make keys for my
app". The assistant talks to a small MCP server (Model Context Protocol), and the
server talks to the host through the control socket that `polyctl` already uses.

A competing keyboard (Keysible 69, crowdfunding planned for February 2027)
advertises a built-in MCP server with tools such as `set_key_styled`,
`set_key_actions`, `add_key_dynamic`, `build_flow` and `push_to_device`. This plan
does not copy that tool set. It exposes what PolyKybd already does, through the
paths that already exist.

## This is not the agent keys

The agent keys ([`agent-keys-agent-setup.md`](agent-keys-agent-setup.md),
[`agent-registry-plan.md`](agent-registry-plan.md)) show the STATE of AI coding
agents on the number row. They use hooks, not MCP, because an MCP tool runs only
when the model calls it, so it cannot report "waiting for permission". That
reasoning stays valid, and this plan does not change the agent keys. The "MCP shim"
the registry plan lists for later is a different thing: an identity source for
agents without hooks.

This plan is the other direction: the assistant CONTROLS the keyboard, on the
user's request.

## What exists to build on

- **The control socket** (`polyhost/server/protocol.py`, `control_server.py`):
  local only (Unix socket or Windows named pipe), authkey file with mode 0600,
  JSON-RPC, a `hello` version gate. It runs in the daemon and in the in-process
  tray, so the server works in both modes.
- **`RpcClient`** in `polyhost/cli/polyctl.py`: connects with the local endpoint and
  authkey. The MCP server uses it, so it needs no new listener.
- **The `M_*` methods** that already call gated `PolyCore` methods. Each one already
  returns the "firmware too old" error on an older keyboard, so the server adds no
  protocol checks of its own.
- **`res/keycodes.h`** (mirrored from qmk): keycode names for the keymap tools.
- **The overlay pipeline** (`scripts/generate_app_overlays.py`, binding YAML files
  as in `res/overlay_sources/<app>/bindings.yaml`, the icon library in
  `res/fontpack/icon_ids.yaml`). Version 2 uses it.

## Version 1: tools over existing methods

No new HID command, so no protocol version increase. Every tool maps to one
existing control method.

| Tool | Control method | Kind |
|---|---|---|
| `get_status` | `status.get` | read |
| `list_languages` | `lang.list` | read |
| `get_keymap(layer)` | `keymap.layer_count`, `keymap.buffer` | read, keycodes as names |
| `list_app_overlays` | the overlay mapping file | read, application names only |
| `set_language(lang)` | `lang.set` | write |
| `set_brightness(value \| "auto")` | `brightness.set`, `brightness.daylight_refresh` | write |
| `set_idle_style(style)` | `idle.style.set` | write |
| `set_glyph_script(script)` | `glyph.script.set` | write |
| `set_key(layer, row, col, keycode)` | `keymap.set` | write, stored in EEPROM |
| `set_overlays(enabled)` | `overlay.enable`, `overlay.disable` | write |

- **`set_key` returns the previous keycode**, so the assistant can undo the change.
  The keyboard stores a keymap edit in EEPROM at once, so the change survives a
  restart.
- **`get_keymap` returns names** (`KC_A`, `MO(1)`), not numbers, because an
  assistant reads names correctly and numbers it does not.
- **Every write tool has the MCP annotation `destructiveHint` or `idempotentHint`,
  and every read tool `readOnlyHint`**, so the client asks the user before a write
  when it is set to do that.

### Not exposed, on purpose

These methods stay out of the server. The tool list is an allow-list, and a test
fixes it (see *Tests*).

| Methods | Why |
|---|---|
| `fw.flash`, `fw.apply_staged`, `fw.bootloader`, `fw.set_handedness` | can make the keyboard unusable; a firmware update stays a deliberate user action |
| `fontpack.flash`, `fontpack.sync`, `fontpack.wipe`, `doom.install`, `doom.install_pack` | write to flash; `doom.install_pack` sends executable code |
| `update.install`, `host.shutdown` | change or stop the host |
| `keymap.reset` | also erases every macro |
| `commands.execute` | raw command lines, including key injection |
| `settings.set` | some settings open network listeners (`window_report_network_enabled`, `dev_legacy_plaintext_relay`) or change telemetry |
| `overlay.mapping_send`, `overlay.reset_*` | low-level state the matcher owns |
| `window.report`, `agents.*`, `telemetry.*` | other features' inputs |

## Version 2: overlays from a description

The most useful request is "make keys for my app". It needs three new host pieces.

1. **A user overlay folder.** Overlays load only from `res/overlays/` or from a
   game's local copy (`get_overlay_path()` in `core/poly_core.py`). A new folder
   in the config directory (`user_overlays/`) holds overlays the user or the
   assistant made, and the resolver checks it after the game copy and before the
   shipped file. A name that exists in both places uses the user's file.
2. **`create_overlay(app, bindings)`.** The assistant passes the same binding
   format as `res/overlay_sources/<app>/bindings.yaml`: key, modifier, label or
   icon. The tool writes the binding file to `user_overlays/<app>/`, runs the
   generator in-process, and adds an entry to the user's
   `overlay-mapping.poly.yaml`. It changes only that entry and leaves the rest of
   the file as it is. Icons come from the icon library by id, or as text labels;
   the tool downloads nothing.
3. **`preview_overlay(app)`.** Returns the generated 72×40 cells as an MCP image,
   so the user sees the keys before the overlay is used.

This is per-application configuration that the user asked for. It does not change
the rule of [`generic-icons-plan.md`](generic-icons-plan.md): the automatic
shortcut harvest still uses no per-application configuration, and a user overlay is
used only for the app it names.

## Not planned: live values on keys

Keysible shows live data on keys (CPU temperature, stock prices, song lyrics). On
PolyKybd that means the host uploads a new image for a key every few seconds. One
72×40 image is about 30 bytes compressed and one HID report, so a few keys at
about 1 update per second would fit. It is left out of this plan because the
overlay send path, the 600-image pool (`OVERLAY_POOL_CAPACITY`) and the MRU claim
pass are built for whole-app switches, not for single keys that change all the
time. It needs its own plan, with a measurement on hardware.

## Process and transport

- **Started by the AI client over stdio**, the usual way for a local MCP server:
  `polyctl mcp`, or `python -m polyhost.mcp`. For Claude Code:
  `claude mcp add polykybd -- polyctl mcp`. The server opens no port.
- **It needs a running host** (daemon or tray). Without one, every tool returns
  "PolyKybdHost is not running", and the server still starts, so the client shows
  the tools.
- **`polyctl` stays stdlib-only.** The server lives in its own module, and
  `polyctl mcp` imports it only when called.

## Security

- **The trust boundary does not move.** The server uses the local authkey, so it
  can do only what `polyctl` can do for the same user, and less, because of the
  allow-list.
- **The new risk is prompt injection.** Text the assistant read elsewhere (a web
  page, a file, an issue) can make it call a tool the user did not ask for. The
  allow-list keeps the worst case small: a changed language, brightness or key,
  all reversible. No tool reaches the firmware, the flash or a network setting.
- **Results are an allow-list too**, built field by field like the telemetry
  payload (`build_payload()`), never by passing a status dict through. Window
  titles, URLs, agent session titles and file paths are never returned.
  `status.get` has none of them today, and the field list keeps it that way when it
  grows.
- **Record it in `polykybd-ctnd/docs/SECURITY_AUDIT.md`** as a new HOST entry
  before it ships.

## Tests

- **A frozen allow-list test**: the set of tools and the control methods they reach,
  compared with a fixed list, so adding a method to the server fails until the test
  is changed on purpose (the same pattern as the frozen `PAYLOAD_KEYS` test in
  `tests/services/telemetry_test.py`).
- **A test per excluded method**: calling it through the server is refused.
- **Tool tests against the mock keyboard** (`dev_mock_primary`) through a real
  `ControlServer`, as `tests/server/control_server_test.py` does.
- **A result-field test**: no tool result has a key outside its field list.
- **One run with a real MCP client** before merging, per the repo rule to run the
  real entry point once.

## Open questions

1. **The official `mcp` Python SDK or a small stdlib implementation.** The SDK
   follows the protocol as it changes and adds a dependency. The stdlib version
   (JSON-RPC over stdio, `initialize`, `tools/list`, `tools/call`) is about 200
   lines and has to follow protocol changes by hand.
2. **Whether `set_key` belongs in version 1.** It is reversible, but it writes
   EEPROM, and a wrong key can make the keyboard hard to use until the assistant
   or the user changes it back.
3. **A host setting to turn the server off** (`mcp_enabled`). The client config
   starts the server, so a setting only matters if the control server can tell an
   MCP client from `polyctl`, for example by a field in `hello`.
4. **Which clients to document**, and whether a `polyctl mcp install <client>`
   command writes their config files, as `polyctl agents hooks install` does for
   the agent hooks.
5. **The name of a user overlay that equals a shipped one.** The resolver order
   above uses the user's file; a warning in the log may be enough.
