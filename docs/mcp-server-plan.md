# MCP server for AI assistants: plan

**Status:** designed, not built (2026-11-27). The entry in
[`FUTURE_WORK.md`](FUTURE_WORK.md) says why it waits.

## Goal

Let an AI assistant (Claude, ChatGPT, Gemini, Cursor, Codex and others) read and
change the keyboard's state when the user asks in plain language: "switch the
keyboard to Greek", "put mute on the outer left thumb key", "make keys for my
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

## Identifying a key

The split72 has no F-row and no printed legends, and the firmware addresses a key by
matrix row and column, which means nothing to the user or the assistant. So every
tool that takes a key resolves a key reference, and two tools describe the board.

- **Every key has a name from its place on the PCB: `L:X.Y` or `R:X.Y`.** `L` is
  the left half and `R` the right half. `X` counts the columns from the outer edge
  towards the middle, and `Y` the rows from the top, both from 1. Examples: Esc is
  `L:1.1`, Tab below it `L:1.2`, and the AI key `R:1.1`.
- **`X` and `Y` come from the switch positions in the KiCad boards**
  (`PolyKybd/poly_kybd/poly_kybd_split72_left.kicad_pcb` and `_right`, footprints
  `SW_K_<n>`), not from the KLE file, because the PCB is the authority for key
  positions ([`layout-editor.md`](layout-editor.md)). `X` is the column nearest
  to the switch (the outer column, then 1.25U to the next, then 1U, 19.05 mm),
  for the rotated thumb keys too. `Y` counts the keys of that column from the top,
  starting at the row nearest to the column's top key: row 1 for columns 1 to 7,
  row 3 for column 8, whose top key is the expansion-port key. So the outer thumb
  pair is `8.4` and `8.5`, not the rows their centres are nearest to.
- **Checked on the current boards (2026-11-27):** the 36 switches of each half get
  36 different names, and both halves give the same set of names, so `L:X.Y` and
  `R:X.Y` are always the same place on each side. The KLE file has 37 keys per
  half; the extra one is `L:8.3` / `R:8.3`, the key over the expansion port, which
  has no `SW_K` switch footprint and no display. The grid, with each key's matrix
  `row,col` (the two halves drawn as they sit on the desk):

  ```
         Left half (X from the left edge)             Right half (X from the right edge)
    Y\X     1    2    3    4    5    6    7    8   |    8    7    6    5    4    3    2    1
      1   0,0  0,1  0,2  0,3  0,4  0,5  0,6    .   |    .  5,1  5,2  5,3  5,4  5,5  5,6  5,7
      2   1,0  1,1  1,2  1,3  1,4  1,5  1,6    .   |    .  6,1  6,2  6,3  6,4  6,5  6,6  6,7
      3   2,0  2,1  2,2  2,3  2,4  2,5  2,6  3,7   |  8,0  7,1  7,2  7,3  7,4  7,5  7,6  7,7
      4   3,0  3,1  3,2  3,3  3,4  3,5  3,6  4,7   |  9,0  8,1  8,2  8,3  8,4  8,5  8,6  8,7
      5   4,0  4,1  4,2  4,3    .  4,4  4,5  4,6   |  9,1  9,2  9,3    .  9,4  9,5  9,6  9,7
  ```

  The cells with `.` have no key. The thumb keys are `6.5`, `7.4`, `7.5`, `8.4`
  and `8.5` on each half.

  ![Split72 key names and aliases, drawn at the PCB switch positions](images/split72-key-names.svg)
- **Aliases count across the middle.** `X` may go on past 8 into the other half,
  so a key can be named from either side: `L:X.Y` with `X` from 9 to 16 is
  `R:(17 - X).Y`, and `R:X.Y` with `X` from 9 to 16 is `L:(17 - X).Y`. For example
  `L:9.4` is `R:8.4` and `L:10.4` is `R:7.4`. An alias of a place with no key (for
  example `L:12.5`, which would be `R:5.5`) is an error. Tools accept aliases and
  always return the canonical name, the one from the key's own half.
- **The names are a frozen table**, generated once from the boards and shipped
  (for example `res/key_positions.yaml`, name → matrix `row,col`), not computed at
  runtime, so a later board revision or KLE correction does not rename a key. A
  test compares the table with the KLE file's `row,col` labels.
- **`list_keys(layer=0)`** returns the 74 keys with, for each key: its name
  (`L:1.1`), the matrix `row` and `col` the control methods use, `thumb`,
  `has_display` (false for the two keys over the expansion ports), and the
  `keycode` on the requested layer and `base` on layer 0, as names.
- **`show_layout(layer)`** returns the grid above with each key's keycode in its
  cell instead of the matrix position, like the drawings in the firmware's
  `keymap.c`. An assistant reads positions ("the two keys left of the space bar")
  more reliably from a drawing than from a list.
- **A key reference** in a write tool is one of `"L:1.1"` (or an alias such as
  `"L:9.4"`),
  `{"base": "KC_Q"}` (the key that sends Q on layer 0) or
  `{"row": 2, "col": 3}`. A `base` reference that matches no key, or more than
  one, returns an error that lists the candidates. The server never guesses a key.
- ⚠️ **A keycode is not the legend the user sees.** With a German layout `KC_Y`
  shows Z. The legend for each language is in the firmware's table, which the host
  does not have, so "the key with the Z" resolves only through the assistant
  asking the user, or through a new query (see *Open questions*).
- **Only the split72 has a KLE file.** Until the split42 has one, the key tools
  return an error when `get_status` names a split42.

## Version 1: tools over existing methods

No new HID command, so no protocol version increase. Every tool uses existing
control methods only.

| Tool | Control method | Kind |
|---|---|---|
| `get_status` | `status.get` | read |
| `list_languages` | `lang.list` | read |
| `get_keymap(layer)` | `keymap.layer_count`, `keymap.buffer` | read, keycodes as names |
| `list_app_overlays` | the overlay mapping file | read, application names only |
| `set_language(lang)` | `lang.set` | write |
| `set_brightness(value \| "default")` | `brightness.set`, `brightness.daylight_refresh` | write |
| `set_idle_style(style)` | `idle.style.set` | write |
| `set_glyph_script(script)` | `glyph.script.set` | write |
| `list_keys(layer)`, `show_layout(layer)` | `keymap.buffer` and the KLE file | read |
| `set_key(layer, key, keycode)` | `keymap.buffer`, then `keymap.set` | write, stored in EEPROM |
| `set_overlays(enabled)` | `overlay.enable`, `overlay.disable` | write |

- **`set_key` returns the previous keycode**, so the assistant can undo the change.
  `keymap.set` reports only whether the write worked, so the tool reads the key's
  current keycode with `keymap.buffer` right before it writes, and returns that
  value as `previous`. If another client (the layout editor, `polyctl`) changes the
  same key between the read and the write, `previous` is the value the tool read,
  not the one it overwrote; the result says so. The keyboard stores a keymap edit
  in EEPROM at once, so the change survives a restart.
- **`set_brightness("default")` clears a manual brightness** and returns to the
  mode the user configured, as the tray's *Back to automatic* row does
  (`brightness.daylight_refresh`): daylight-dependent brightness when the host
  setting `brightness_set_daylight_dependent` is on, otherwise the keyboard's own
  stored level (`AUTO_OFF`). It cannot switch the daylight mode on: that is a
  setting, and `settings.set` is not exposed. The tool says which mode it
  returned to.
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
- **A key-identification test**: the frozen table has 74 different names, every
  `row,col` of the KLE file exactly once, and the same set of names on both halves;
  every alias resolves to the same key as its canonical name, and an alias of an
  empty place is an error; a `base` reference to a keycode that is on two keys returns an error, not one of
  them.
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
6. **The names for the split42.** Its boards give the same scheme; it needs its
   own KLE file and its own frozen table before the key tools support it.
7. **The legend a key shows in the current language.** The host can read it only
   through a new HID query (version-gated, a firmware change). Without it the
   assistant works with keycodes and asks the user when the language matters.
