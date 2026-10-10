# CLAUDE.md: PolyKybdHost (host app)

PyQt5 tray app that tracks the active window and drives the PolyKybd keyboard over raw
HID: overlays, keymap, language, firmware and font-pack updates.

**Rules for all PolyKybd repos** (review, branching, mirrored files, releases, web
session limits) are in `../polykybd-claude/CLAUDE.md`, with the shared skills. If that
repo is not attached, ask the user to attach `thpoll83/polykybd-claude`. This file holds
only host rules. Each section names the doc with the full detail and history; read it
before changing that subsystem. `.claude/rules/*.md` add warnings when you Read a
matching file. Work deliberately not done, and why:
[`docs/FUTURE_WORK.md`](docs/FUTURE_WORK.md). Read it before designing something it
already weighed.

## Commands

```bash
python -m polyhost                 # standard; --dev [0|1|2] developer mode + log level
python -m polyhost --host <IP>     # forwarder mode (also --host-file <file>)
python -m polyhost --portable      # no autostart registration
pip install -e .
xvfb-run -a .venv/bin/python scripts/run_tests.py              # whole suite: use the RUNNER
.venv/bin/python -m unittest tests.device.cmd_composer_test    # one module
```

- **Always use `.venv/bin/python`.** System `python3` lacks numpy, PyQt5 and more.
  Setup, the apt packages `hid` needs, and `xvfb`: [`docs/dev-environment.md`](docs/dev-environment.md).
- ⚠️ **Never run the whole suite with `unittest discover -s ./tests`.** It puts
  `tests/` first on `sys.path`, `tests/tools/` shadows the repo's `tools/`, and you get
  ~26 failures and errors that do not exist.
- ⚠️ **A missing dependency deletes tests silently.** A module that fails to import
  adds one error and zero tests. Install the deps and read the `Ran N` line.
- ⚠️ **Baseline in place, not in a `/tmp` worktree**, which skips every test gated on
  `../qmk_firmware`.

**Normal mode** owns the keyboard and tracks the local window. **Forwarder mode** runs on
another machine with no keyboard and relays its focused window over TCP to the normal
instance, so one keyboard serves several computers.

## Architecture

File map, `PolyCore`, the control socket and its servers, `polyctl`, headless mode,
`RemoteCore`, the device layer, platform input and window handlers:
[`docs/architecture.md`](docs/architecture.md). Read it before adding a module or a
control-socket method.

- ⚠️ **`PolyCore.__init__` opens the keyboard.** Anything deciding whether this process
  should be the host runs before the core is built. `instance.claim_instance()` is that
  gate: an OS file lock, taken in `main_app`.
- **`PolyCore` stays Qt-free** and talks only through observer callbacks with
  JSON-serializable payloads (guarded by `tests/core/import_guard_test.py`).
- **A new device-coupled GUI surface must work in client mode over RPC.** Client mode is
  the default under daemon-by-default.
- ⚠️ **Six pieces of plumbing are shared because copies drifted**: `MpcListenerServer`,
  `UpdateProgressController`, `gui/theme.apply_theme`, `util/observable.Observable`,
  `util/filelock`, `PolyCore._flash_resource`. Use them. Extracting one drops the inline
  comments that passed review, so re-run the checks on the extracted copy.
- ⚠️ **A bug in one listener server: grep the other two** (`control_server`,
  `window_report_server`, `browser_report_server`) before designing a fix.
- ⚠️ **The network `WindowReportServer` serves one method and holds no `PolyCore`.**
  That separation is the security boundary.

## Threading (HID worker)

The Qt main thread does no device I/O after startup. `HidWorker` owns the device and runs
the periodics (reconnect probe 1 s, crash autocheck 1 s, console 250 ms, daylight
brightness 10 min). [`docs/hid-worker-refactor.md`](docs/hid-worker-refactor.md).

- **No synchronous language enumeration at startup.** The first probe must see
  False→True and run the full fresh-connect flow.
- **The probe is debounced (3 strikes).** The keyboard goes deaf for hundreds of ms after
  a large overlay transfer, and one failed probe would start a wipe-and-resend loop.
- ⚠️ **Nothing the firmware prints during a flash reaches the host.** Use
  `tools/poly_console.py` in a second terminal. A timestamp gap spanning the flash is
  expected.
- **`FW_UP_COMMIT` has four status bytes**: `.` accepted, `?` waiting for the physical
  ACCEPT/REJECT (re-poll), `S` not validly signed, `!` CRC mismatch. Don't collapse them.
  The host may cancel the prompt, never accept it.
- **`polyctl fw version` is a live query (cmd 0x43)** and fails loudly mid-flash.
- **No blocking the main thread with network I/O either.**
- ⚠️ **A modal opened from a bridge handler dispatches the other queued bridge events.**
  Route every dialog a bridge event can open through one serializer (#257).
- ⚠️ **A COM object never crosses a thread; every thread that calls COM initializes it.**
  A violation kills the headless daemon with a native access violation and no log line
  (twice, tell: `0x80010108` dumps in `crash_log.txt`).
  `polyhost/services/shortcut_source/uia.py` is the pattern.

## Protocol and the connect gate

The host connects to any firmware with protocol ≥ `MIN_SUPPORTED_PROTOCOL` (2), then
gates each feature with `FEATURE_MIN_PROTOCOL` (`device/poly_kybd.py`). `__protocol__`
(`polyhost/_version.py`) is the newest protocol the host knows, 23 today, in lockstep
with firmware `PROTOCOL_VERSION`. [`docs/protocol-gate.md`](docs/protocol-gate.md).

- ⚠️ **Every new device command must be version-gated**: the `FEATURE_MIN_PROTOCOL`
  entry, `self.supports()` in both accessors, the GUI menu gate, `polyctl`, and the
  protocol bump on both sides. An ungated command NACKs at runtime on older firmware.
  `tests/device/protocol_gate_sweep_test.py` and `tests/core/core_protocol_sweep_test.py`
  enforce it: a new `Cmd` needs `CMD_MIN_PROTOCOL` in `device/mock_firmware.py`, a new
  `PolyKybd` method a `CALLS` entry. The `add-gated-hid-command` skill does the whole job.
- **Firmware update ignores the protocol gate.** Flash actions gate on
  `_fw_actions_allowed()`, never on `self.connected`.
- ⚠️ **`parse_id_version_block` finds the font-pack `V` block positionally**, so the
  firmware appends anything new after it.
- ⚠️ **The raw channel is strictly request/response**, and the stale-reply drain relies
  on it.
- ⚠️ **`expect(Cmd.X)` also matches a NACK.** On a closed range, read the verdict at
  `reply[2]` before reporting success. `set_idle_timeout` does; `set_glyph_size`,
  `set_idle_style` and `set_glyph_script` don't yet.

## Font pack, icon library and overlays

N per-family bundles in `polyhost/res/fontpack/`, flashed per slot on connect.
[`docs/fontpack.md`](docs/fontpack.md); inspect/extend dialogs:
[`docs/fontpack-tools.md`](docs/fontpack-tools.md).

- ⚠️ **A bundle can report a failed flash and still read up to date** (FONTPACK writes in
  place). The core remembers failures and re-flashes regardless of version. One bundle's
  failure must not abort the pass.
- ⚠️ **GET_ID's version block shows the master's slots only.** Say `slave-unconfirmed`.
- ⚠️ **`install_doompack` sends executable code.** The `.plyx` is signed (FW-9, fixed);
  `.whx` and `.plyf` are not. The `.sig` handling in `hid_fw_up` covers the firmware
  image only.
- **Bundle 8 is the overlay icon library** (`icons.plyi`, cmd 42, v20), built by
  `scripts/build_icon_library.py`, ids frozen in `res/fontpack/icon_ids.yaml`. ⚠️ Rebuild
  it in batches, never per overlay change (maintainer's rule): each rebuild re-flashes
  every keyboard. An icon enters the library only if more than one app uses it.
- ⚠️ **One switch shows at most 600 distinct images** (`OVERLAY_POOL_CAPACITY` =
  firmware `NUM_OVERLAY_SLOTS`). It counts images, not keys. Past 600 the extra keys stay
  blank with a warning.
- ⚠️ **The MRU claim pass and the send loop must agree on which image a key ends up
  showing.** Change one, change the other, and run `tests/device/mru_claim_test.py`.

## Device features

Glyph script (cmd 30), legend size (cmd 34), macros (36–38), idle timeout (40): each is
a `PolyKybd` accessor behind a gate, a `PolyCore` method, an `M_*` control method, the
`RemoteCore` mirror, a `polyctl` subcommand and a gated tray submenu.
[`docs/device-features.md`](docs/device-features.md).

- ⚠️ **`GlyphScript` is an open range and `GlyphSize` a closed one, on purpose.** Never
  make them consistent; `tests/device/poly_kybd_capabilities_test.py` pins it.
- **Label the idle timeout from the SECONDS in the reply** (`IdleTimeout.label_for()`),
  so an older host still names a preset newer firmware added.
- **Macros are read-modify-write of the whole buffer**, and the label meter is in
  pixels, not characters.

## Layout editor

Key geometry, the case plate, preview modes and their data:
[`docs/layout-editor.md`](docs/layout-editor.md). Read it before touching
`gui/layout_dialog/` or the export scripts.

- **Key geometry comes from the KLE** (`polyhost/res/polykybd-split72.json`), not QMK's
  `layouts` grid. The plate is the case SVG, not `Edge.Cuts`.
- ⚠️ **"Why is this preview wrong?" → run `python tools/preview_doctor.py` first.** Three
  reports were one stale clone.

## Tray, settings and the forwarder

Menus, theme, brightness rows, WinCompose install, unicode-mode watcher:
[`docs/tray-ui.md`](docs/tray-ui.md). Icons: [`docs/icons.md`](docs/icons.md). ⚠️ The
per-application ESC mark has a rule of **no per-application configuration**:
[`docs/generic-icons-plan.md`](docs/generic-icons-plan.md).

- **The tray app and the forwarder are translated into 20 languages**
  ([`docs/i18n.md`](docs/i18n.md)). Every string a user reads in `gui/`, `host.py` or
  `forwarder.py` goes through `_()`, `_f()` or `_nf()` from `polyhost.i18n`;
  `tests/i18n_test.py` fails on an unmarked literal handed to a Qt text call. After
  changing one, run `python scripts/i18n_strings.py update`. Logs, `polyctl` output and
  the core's messages stay English on purpose. ⚠️ A function that calls `_()` must not
  also assign `_` (`ok, _ = f()`): Python makes `_` local and the call raises
  `UnboundLocalError`.
- **Developer mode adds a submenu and rearranges nothing.** It is a persisted setting,
  separate from log verbosity.
- ⚠️ **`managed_connection_status` disables every top-level action first.** Re-enable a
  new group parent there.
- ⚠️ **A tray balloon reaches nobody on macOS** (no bundle id). Never make a balloon the
  only carrier of anything; `_balloons_reach_user()` is the gate. `IconStateManager` owns
  the tooltip; use `set_base_tooltip`.
- **Settings side effects go through one hook, `PolyCore.note_settings_changed()`.**
- ⚠️ **`PolySettings.save()` merges per key against the file, under a cross-process
  lock, and never raises.** Daemon and tray both save, so a whole-file rewrite reverts the
  other. It returns whether it wrote; check it before telling the user a change was
  saved.
- ⚠️ **The forwarder is a second tray app on a different machine.** A feature added to
  `host.py` is absent there until wired separately. Its settings are an allow-list
  (`FORWARDER_SETTING_KEYS`). Put process-wide Qt identity in `main_app`.
- ⚠️ **A wrong icon name fails silently** (`tests/gui/icon_assets_test.py` guards it).
- ⚠️ **Check whether a platform path ever did its job before muting it** (macOS language
  switching never once switched an input source).
- **Input helpers**: `LangComp(platform)` requires its argument, and
  `get_current_language` and `set_language` answer in one namespace. Details in
  `docs/architecture.md` → *Platform input abstraction*.

## Updates, autostart and the daemon

[`docs/autostart.md`](docs/autostart.md).

- ⚠️ **Two locks, two files**: `claim_instance()` guards the control endpoint (daemon),
  `claim_gui()` the tray icon. `claim_gui()` waits ~3 s because the post-update relaunch
  starts the replacement before this process exits.
- ⚠️ **Registering autostart must never start the app** (macOS `RunAtLoad` once started
  a second copy that locked the device for 50 minutes).
- **The daemon applies a GUI self-update, not the client**, and the GUI waits for the
  endpoint to go down and back up before relaunching.
- ⚠️ **Every relaunch goes through `spawn_detached()`**, with `pythonw.exe` on Windows.
- **Launchers live in the platformdirs config dir, not the checkout.** The Windows task
  is named `PolyHost`.
- **`updater.preflight()` runs before the download**, for the tray, daemon and `polyctl`.

## When something is reported broken

Logs, crash reporting, the problem report and forwarding's silent failures:
[`docs/diagnostics.md`](docs/diagnostics.md); telemetry:
[`docs/telemetry-internals.md`](docs/telemetry-internals.md). Reading a log bundle is the
`triage-log-bundle` skill.

- ⚠️ **A new log file reaches nobody unless `LOG_SOURCES` lists it**, and its lines need
  a timestamp prefix `slice_lines` can read.
- ⚠️ **Never rotate, delete or `os.replace` `crash_log.txt`.** `faulthandler` holds its
  descriptor. Clear it by truncation.
- ⚠️ **`polyctl logs` must work with no host running.**
- ⚠️ **The problem scan matches a curated `CONSOLE_PATTERNS` list, never keywords.** A new
  firmware failure message needs an entry.
- ⚠️ **"The tray icon is gone" is not "the app crashed".** The daemon may still own the
  device. Check the process list in pairs.
- ⚠️ **The telemetry payload is an allow-list at both ends** (`build_payload()`). There
  is no in-app consent step, so keep the one INFO line printed at every start.

## Platform and testing traps

Test recipes, fixture traps and the deadlock post-mortem: [`docs/testing.md`](docs/testing.md);
the mock keyboard (`dev_mock_primary`): [`docs/mock-device.md`](docs/mock-device.md).
Tests are unittest, not pytest; GUI tests need `xvfb-run -a`.

- ⚠️ **A text-mode `open()` on a non-ASCII file we ship needs `encoding="utf-8"`.**
  Windows decodes with cp1252, and the lucky outcome is a crash; usually it is silent
  mojibake. Files the user owns keep the platform default. Re-run the AST sweep over the
  whole tree; three hits remain, all user-owned.
- ⚠️ **The suite cannot execute the platform input paths** (Win32, Carbon, pynput). A
  green board says nothing about them; budget a hardware round.
- ⚠️ **A `skipUnless` guard that checks less than the code needs can hang the suite** on
  a modal dialog. Derive the guard from the function the code calls.
- ⚠️ **A change to concurrent file access is not done when the tests pass.** Mutation-sweep
  it and race it with real processes.
- **Run the real entry point once before believing a mocked suite.**
- ⚠️ **Test methods appended after `if __name__ == "__main__":` never run.** Check the
  test count changed.
- ⚠️ **`patch.object(Class, "method")` does not reach a fixture that already bound it.**
- ⚠️ **A stale `.pyc` can survive a correct fix.** Clear `__pycache__` after restoring too.
- ⚠️ **`polyhost/forwarder.py` is untestable here** (pywinctl at import). Put logic worth
  testing in a Qt-free module.
- **Linux HID access needs the udev rule** `polyhost/device/99-hid.rules`.

## Releases

Host tag `vX.Y.Z`, version in `polyhost/_version.py`. Shared rules are in polykybd-claude;
mechanics and the `release-notes` branch: [`docs/releases.md`](docs/releases.md).

- ⚠️ **Here `release.yml`'s version check detects rather than prevents.** This workflow
  uploads nothing, and the release is public before the step runs. The tarball users
  install is `archive/refs/tags/<tag>.tar.gz`, so withdrawing a bad one is manual.
- ⚠️ **The bump lands through its own auto-merged PR, because `main` requires a PR.** It
  depends on "Allow GitHub Actions to create and approve pull requests" and on the `main`
  rule requiring nothing more than a PR.
