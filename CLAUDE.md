# CLAUDE.md — PolyKybdHost

This file provides guidance to Claude Code (claude.ai/code) when working in the **PolyKybdHost** repo (the Python host software).

For cross-repo context (how this repo relates to `qmk_firmware/` and `AdafruitGFX/`), see [`../CLAUDE.md`](../CLAUDE.md).

## Code review conventions (all PolyKybd repos)

- **Docstring coverage: ignore CodeRabbit's "Docstring Coverage … threshold 80%" pre-merge check.** That 80% target is a CodeRabbit default, **not** a project policy — the check is non-blocking and we deliberately do not chase it. Do **not** add docstrings to existing functions just to satisfy it (out-of-scope churn). Document new code where a docstring genuinely helps a reader, and no more.

- **Verify an AI reviewer's finding against the code before acting on it — several
  arrive confidently wrong.** Of 7 CodeRabbit findings on one PR (2026-08-01), 3
  were false and **two were refuted by their own evidence**: a "PACK_VERSION 3
  needs a matching host change" (the host never parses the PlyX version — it
  checks magic + slot fit and defers the ABI/RAM contract to the firmware loader
  by design); a "the unpacker is not defined" whose own analysis script had
  returned 159 bytes of output, i.e. it reasoned without the code (the decoder
  was 90 lines above in the same file); and an `int8_t` "signed-overflow UB" that
  the StackOverflow answer it quoted explicitly contradicts (a sub-`int` operand
  promotes to `int`, so the narrowing back is *implementation-defined*, not UB —
  though a real non-termination hazard did lurk nearby, so the fix was taken for
  a different stated reason). **The rule is verify, not dismiss:** the same review
  round produced one genuinely valuable finding (a bulk repair loop running inline
  in `raw_hid_receive()`, worth seconds of blocked main loop) that was adopted.
  Reply to the false ones with the evidence so they are not re-raised.

- **A bot comment is not a review — check whether one actually ran before treating
  a PR as reviewed.** PR #127 (2026-08-01) collected four bot comments and **none
  was a review**: CodeRabbit was rate-limited across both pushes (a `> [!WARNING]
  Review limit reached … next review in 43 minutes` comment, re-queued and still
  unavailable at merge time), Sourcery had hit its weekly diff-character limit so
  it posted only its descriptive *Reviewer's Guide*, and Qodo only ever posts a
  *PR Summary* (and, since its subscription lapsed, only a *"reviews are paused
  because the subscription is no longer active"* notice — docs#48, 2026-08-17).
  All three render as long, confident-looking comments with
  walkthroughs and file tables, so the PR read as well-reviewed and merged with
  zero findings raised against it. Tells: CodeRabbit's rate-limit notice (and the
  "Reviews paused" one — see the same section in `qmk_firmware/CLAUDE.md`), and
  the absence of any *Actionable comments posted: N* line. When it matters, wait
  for the window or comment `@coderabbitai review`.
  - ⚠️ **Both of those tells failed on #156 (2026-08-11) — the only reliable check
    is whether the walkthrough describes the commit you are looking at.** Compare
    its file list against the head commit's: the walkthrough named 2 files while
    the head changed 4, and described the superseded change. Three ways it misleads:
    - **The rate-limit banner DISAPPEARS on a re-render.** Editing the PR body
      re-rendered the pre-merge-check block, and the `> [!WARNING] Review limit
      reached` notice vanished with it — leaving a clean-looking walkthrough plus
      "🚥 Pre-merge checks ✅ 5" over a commit nothing had read. A missing banner is
      not evidence a review ran.
    - **`@coderabbitai review` can answer WITHOUT a formal review.** The reply ran
      a real analysis chain (diffed the 4 files, read the callers, scripted its own
      cross-check) and returned *"I reviewed commit f14ae25 … no correctness,
      regression, or documentation issues"* — a genuine, verifiable read. But the
      same comment was then **edited in place** from *"Action performed: Review
      triggered"* to *"⚠️ Action not completed — Review rate limited"*, and the
      walkthrough stayed stale for good (an incremental system will not re-review
      a commit it has "seen"). So a substantive verdict and a missing formal review
      can coexist. Take the verdict, but don't expect the PR summary to describe
      the change — put the real description in the **PR body**, which you control.
    - **The FILE LIST is not enough on a single-file PR — compare what the
      walkthrough SAYS.** On docs#42 (same day) a follow-up commit touched the
      same one file the reviewed commit did, so the file-list check above passes
      while the review is still describing the superseded diff; only the absent
      mention of the new section gave it away. The mechanism: the walkthrough is
      **sticky** — it survives from the last *successful* review and is not
      refreshed by a rate-limited one, which replaces only the review-info block
      beneath it. Note the banner behaved *correctly* here (present, with the
      real `<old>..<new>` range), so the asymmetry is: **a banner that is present
      is trustworthy; a banner that is absent proves nothing.**
    - ✅ **There IS a cheap reliable tell after all: the Merge Risk block names the
      commit it covers** — *"Merge Risk: 🟡 Moderate · up to `351b8`"*.
      Read that sha instead of comparing walkthrough prose against the head
      commit. On docs#48 (2026-08-17) the summary re-rendered on **three**
      successive pushes, each time still scoped `up to 351b8` and still asserting
      the PR was "not merge-ready" over a concern two later commits had already
      fixed — while CodeRabbit's own chat reply confirmed the fix. Same sticky
      mechanism as above, but self-labelling: if that sha is not the head, the
      whole summary (risk verdict included) is describing an older commit. It is
      worth checking before believing any *later* re-render of a summary,
      including a scary one.
    - ⚠️ **The limit is per-developer across the ORG, so pushes to a trivial PR
      starve the one that needs review.** Docs pushes on #42 consumed the window
      #159 was waiting for. When two PRs are open and one is real code, stop
      pushing cosmetic commits to the other until the important one is reviewed.
    - ⚠️ **A THIRD no-review mode: CodeRabbit does not auto-review a repo with
      fewer than 10 stars at all** — *"Reviews should be triggered manually for
      repositories with fewer than 10 stars"*, rendered as a *"Review available on
      request"* box with a Trigger-review checkbox. This is permanent, not a
      transient limit, so it is easy to mistake for "no findings". It currently
      applies to **`polykybd-docs`** (docs#48, 2026-08-17); the fix is simply to
      comment `@coderabbitai review`. The same reply then states the quota
      outright — *"Your plan includes up to 1 review per rolling hour; 0 remain
      after this review"* — which is the number to plan around when a PR needs a
      re-review after a fix.
  - ⚠️ **A review that DID run, on the right commit, with an accurate walkthrough,
    can still have SKIPPED the file you care about — read the "Files skipped from
    review" list before trusting a clean verdict.** On qmk PR #198 (2026-08-11)
    CodeRabbit reported *"No actionable comments were generated 🎉"* against the
    right head, and its walkthrough had correctly refreshed (it dropped a claim the
    latest commit had deleted), so every tell above says *reviewed* — while the
    same comment listed `poly_keymap.c` under *"🚧 Files skipped from review as they
    are similar to previous changes"*. That file held **all** the new logic (a
    modifier latch, an ownership-gated release swallow, an inverted render path);
    the incremental heuristic judged it similar to its own earlier review of the
    same file, so the green verdict covered only a header, a tool script and a
    keymap. This is the complement of the stale-walkthrough traps above: there the
    walkthrough lies about *which commit*, here it is honest and the **coverage** is
    the gap. The fix is **`@coderabbitai full review`**, which re-reviews the whole
    diff regardless of incremental state — and it worked: the full pass read the
    file and confirmed the latch ownership and release-swallow gating specifically.
    ⚠️ Spend the slot deliberately, per the org-wide-limit note above: each
    `@coderabbitai review` consumes one **even when it is refused** ("⚠️ Action not
    completed / Review rate limited"), so retries starve the window they wait on. A
    **push** re-triggers a review without spending a request — on that PR the next
    commit is what finally got one to run after two requests had been eaten.

- **When two reviewers disagree about the same code, WRITE THE TEST — it
  adjudicates, and it is faster than arguing.** On PR #154 (2026-08-07) Sourcery
  asked for a regression test on a parser input shape while CodeRabbit claimed
  that shape silently returned an empty result. Writing the test settled it in
  seconds: CodeRabbit was right, and the docstring had been advertising a shape
  the code dropped. The general form is worth internalising — a "testing
  suggestion" from one reviewer is often the cheapest way to check a
  *correctness* claim from another, and unlike a code-reading argument it leaves
  a permanent guard behind. It also inverts nicely: a test that passes
  immediately is evidence the finding was wrong, which is exactly the evidence
  to paste in the reply.

- **A guard that ENUMERATES its siblings will go stale — delete it rather than
  add the missing term, and distrust a test that documents the workaround.**
  `find_matching_entry` (`handler/common.py`) split the window title only
  `if title and (has_starts_with or has_ends_with)`, while the *third* word-based
  matcher below it, `has_contains`, was never added to that list. So
  `titles-contains` could not match unless the entry happened to declare a
  sibling key it did not need — and the shipped browser entry's Miro / web-Outlook
  / Jira overlays, which route purely on `titles-contains`, **had never once
  rendered** since they were added (#156, 2026-08-11). Two things to carry over:
  - **The fix is to drop the gate** (`words = title.split() if title else []`),
    not to add `or has_contains`. Every branch under it already checks its own
    `has_*` flag, so the gate's only job was to restate them and stay in sync —
    exactly what it failed at, and one more term re-arms the same trap for
    whoever adds a fourth matcher.
  - ⚠️ **The test suite was green throughout, because the test encoded the
    workaround as the contract**: it built its fixture as
    `entry(sw={"x": {}}, contains={...})` with the comment *"has both starts_with
    and contains so the title is split into words"*. That dummy `titles-startswith`
    is the only reason it passed. A fixture carrying an unexplained extra key to
    make the feature under test work is a **bug report**, not setup — chase it.
- **Sourcery's `dangerous-subprocess-use-audit` (opengrep) fires on ANY
  non-literal argv and will hold the check red forever — resolve it with a
  `# nosemgrep` marker plus a written audit, not by contorting the code.** It is
  an *audit* rule: it asks a human to confirm where the argv came from, which is
  the whole remedy. A `subprocess.run(list, ...)` with the default
  `shell=False` has no shell to inject through, and the rule's suggested
  `shlex.quote` escapes for a **shell string** — applied to an argv element it
  just corrupts the value. ⚠️ **The marker only applies to the line IMMEDIATELY
  following it**, so putting it at the top of an explanatory comment block (where
  it reads best) silently does nothing and the check stays red — cost an extra
  push on #154. Record the reasoning above the block, the marker directly above
  the call. Leaving the check red instead is the worse option: an always-red
  check is one people learn to scroll past, and the next real finding rides in
  behind it.

## Branching (all PolyKybd repos)

- **Give every branch a name that hints at its content.** When creating a branch, append a short, descriptive slug describing the change (e.g. `claude/fix-firmware-update-menu-daemon-mode`, not just the auto-generated `claude/<random-scientist>-<id>`). The random scientist/id suffix from Claude Code on the web is auto-assigned server-side and can't always be overridden mid-session, but whenever a branch name is chosen by us, make it self-explanatory so the branch list reads as a changelog.
- **Always start new work on a FRESH branch cut from the updated default branch — never keep committing to a branch whose PR has already merged.** Once a PR is merged, that branch is done: `git fetch origin <default>` (and for the next piece of work `git checkout -b claude/<new-slug> origin/<default>`). Cherry-pick only the still-unmerged commits onto the fresh branch if needed. This keeps each PR a clean, focused diff against the current default (`main` for host/rig, `PolyKybd` for the firmware) and avoids a new PR accidentally re-including already-merged commits.

## Commands

### Run the application
```bash
python -m polyhost                        # standard
python -m polyhost --dev                  # developer mode + basic debug logging
python -m polyhost --dev 2                # developer mode + detailed debug logging
python -m polyhost --dev 0                # force developer mode off for this run
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
- `polyhost/server/` — **control socket** (headless-core H2). `protocol.py`: stdlib `multiprocessing.connection` transport (UDS / Windows named pipe + authkey), UTF-8 JSON framing, JSON-RPC message shapes, the `hello` version gate, platformdirs endpoint+authkey (0600), and the canonical `M_*` method-name constants. `control_server.py`: `ControlServer` — accept loop + per-connection reader threads, a method registry dispatching to `PolyCore` (core `(ok,payload)` failures → JSON-RPC `ERR_DEVICE`), and core-event fan-out to subscribed clients. `instance.py`: the socket doubles as the single-instance lock. `PolyHost` embeds a `ControlServer` (M1); the CLI/headless server reuse it. `window_report_server.py`/`window_report_client.py` (H4d): a **separate, opt-in** `AF_INET` listener (`WindowReportServer`, port `WINDOW_REPORT_PORT=50163`) that serves **only** `window.report` — same `hello`+authkey gating, but a **separate authkey** (`window_report_authkey_path()`) and **no `PolyCore` reference** (only an injected `report_window` callback), so the network surface can never reach device control/flash/bootloader. `HeadlessHost` starts it only when `window_report_network_enabled` is set (default False); the forwarder pushes to it with `--report-rpc`. The legacy plaintext TCP relay (port 50162, `remote_window.receive_from_forwarder`) is **unauthenticated and binds all interfaces**, so it is now **off by default** — `RemoteHandler.listen_to_forwarder()` only binds it when the `dev_legacy_plaintext_relay` setting opts in (threaded `PolyCore.settings_get` → `OverlayHandler` → `RemoteHandler`); with remote entries mapped but the relay disabled it warns **once** pointing to the authenticated path (suppressed when `window_report_network_enabled` is already on, since reports then arrive over RPC — both transports funnel through the same `RemoteHandler.report_window` → `remote_changed`/`_match_remote`, so remote-entry matching is transport-agnostic). The `dev_` prefix hides the setting in the settings dialog unless developer mode is on (`settings_dialog.py` skips `dev_*` keys when `developer_mode` is False). The `window.report` control-socket path (authkey-gated) supersedes it.
- `polyhost/cli/polyctl.py` — **`polyctl`** console-script (stdlib-only, never imports Qt): `status`, `lang list|set`, `brightness`, `idle`, **`idle-style [pulse|jitter]`** (get/set the idle anti-burn-in style over HID cmd 28 — `M_IDLE_STYLE_GET/SET` → `PolyCore.get/set_idle_style` → `PolyKybd`, firmware v4+), `overlay …`, `keymap …`, `commands`, `fw version`, **`fw flash <bin> [--apply]`**, `pause|resume`, `mru save`, `settings get|set`, **`update check|install`**, **`window report`**, `watch`, `shutdown`. Long ops (`fw flash`, `update install`) subscribe to events and stream progress to a terminal event — `RpcClient` exposes `subscribe_events()`/`events()` (the latter ends on `EOFError`/`OSError`); `watch()` builds on them. Talks the `protocol.py` wire format to the control socket.
- `polyhost/headless.py` — **`--headless`** (M2, H3): `HeadlessHost` runs `PolyCore` + `ControlServer` + the core-owned window tick with **zero Qt import** in the process (`main_app` imports Qt/`PolyHost` lazily, only in the GUI branch — guarded by `tests/headless/headless_entry_test.py` and the import guard). The core auto-applies its own reconnect snapshots headless (`PolyCore(apply_reconnect_in_core=True)`). On a `polyctl update install`, the core only applies+emits; `HeadlessHost` re-execs (or hands off to the Windows relay) on `update_finished_ok`/`update_relay_needed`. Drive it with `polyctl`. Two headless gotchas fixed the hard way: the core-owned window-tick thread must **`pythoncom.CoInitialize()` on Windows** (pywinctl uses COM; a fresh thread without it fails every poll with "Invalid syntax"); and `poly_core` imports `polyhost.util.log_util` so `Logger.debug_detailed` (used by the device code) exists in the headless process too (the GUI got it via `host.py`). The daemon writes `daemon_log.txt`; `main_app` maps `--dev 2` → `DEBUG_DETAILED` for headless too (mirroring the GUI), so the daemon's `debug_detailed` lines — e.g. window-report receipts (`report_window` / `receive_from_forwarder`, level 8) — are only visible at `--dev 2`, not `--dev 1` (DEBUG=10). The tray GUI's log viewer adds a **"Daemon Log"** tab when `daemon_log.txt` exists (so daemon-mode reconnect/overlay/window activity is visible from the GUI side).
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
- ⚠️ **Nothing the firmware prints during a flash is observable from the host** — and
  this is not a logging-level problem, so don't go hunting for a switch. `exclusive()`
  calls `suspend()`, which sets the cancel flag on **every** periodic including the
  250 ms console read, and QMK *drops* console output that no one drains. So the
  window from BEGIN to the post-apply reconnect is a blind spot in the host log,
  which is exactly where the FW-2 verdict lands: `FW_UP: image signature
  OK|INVALID|UNSIGNED`, printed at COMMIT. Two rounds were spent concluding "it
  printed nothing" from a log that structurally could not contain it (2026-08-04);
  the tell is a gap in the firmware console timestamps spanning the flash. Use
  **`tools/poly_console.py`** in a second terminal — it reads the console HID
  interface directly (separate from the raw-HID channel the flash uses, so they
  coexist) with only `hid`, and survives the reboot. `qmk console` is *not* a
  substitute on Windows: the QMK CLI refuses to run outside an MSYS2 MinGW64 shell.
- **`FW_UP_COMMIT` has FOUR status bytes** — `.` accepted, `?` awaiting the physical
  ACCEPT/REJECT on the keyboard, `S` refused because the image is not validly signed,
  `!` staged-CRC mismatch. `S` was split out (qmk, 2026-08-05) because the firmware's
  signature check sits *behind* the CRC result inside `fw_staging_finalize()`, so both
  refusals arrived as `!` and every consumer reported "CRC mismatch" for an image whose
  CRC was perfect — including the HIL rig, which sent a real investigation the wrong
  way. Don't collapse them back into one test.
  - **`?` means "re-poll me", not "failed".** Under `FW_REQUIRE_SIGNATURE` an unsigned
    image is not refused outright: the keyboard turns its keycaps into an A/ACCEPT ·
    R/REJECT dialog and waits up to 60 s for a keypress. `hid_fw_up.flash_firmware`
    re-sends COMMIT every second (`CONFIRM_POLL_TIMEOUT_S` 75, deliberately past the
    firmware's own window so the host never gives up first) until the byte changes.
    Staging state is untouched between polls, so re-running COMMIT is free — and the
    firmware skips re-bridging to the slave while a prompt is up, or each poll would
    re-erase the slave's 4 KB staging header sector.
  - ⚠️ **A host that predates `?` cannot flash an unsigned image at all** — it falls
    through to the generic failure branch and the progress dialog simply stops, still
    holding `worker.exclusive()`. Ship the host release before (or with) an enforcing
    firmware release: the firmware cannot detect an old host, so ordering and the
    "download the `.sig` too" wording in the notes are the only mitigations.
  - **`polyctl fw version` is a LIVE query (HID cmd 0x43) — it used to be a cache, and
    the cache lied.** `PolyCore.get_fw_version()` returned `keeb.get_sw_version()`, the
    string parsed at the last GET_ID. That is the one command whose whole purpose is
    "what is running right now", and it is asked exactly when a cache cannot answer:
    straight after a flash, while `worker.exclusive()` has the reconnect probe suspended
    so nothing re-probes. It reported the *pre-flash* version after an update had
    demonstrably installed — the keycaps were already drawing a prompt only the new
    firmware can render — and it was believed (field, 2026-08-05). It now does device
    I/O through `_device_call`, returns `(ok, {version, fw_size, fw_crc})`, and **fails
    loudly** ("suspended") mid-flash rather than handing back a stale string. Don't
    "optimise" it back to the cached value; the failure is the feature.
  - **The host may CANCEL the prompt but never accept it** — a COMMIT carrying `'x'`
    in `data[2]` withdraws it (`_abort_cleanup` sends that form). Cancelling can only
    ever deny, so it is safe over the very channel signing defends; accepting stays a
    keypress. Don't add a host-side "allow unsigned" checkbox.
- **The host is also silent when a firmware `.sig` is simply absent.** `hid_fw_up`
  reports "Sending image signature…" at 97% when it finds `<bin>.sig` beside the
  image, and reports a problem when the file exists but is unreadable or the wrong
  length — but says **nothing at all** in the common case where it isn't there. An
  unsigned flash is therefore indistinguishable from a signed one in the log, except
  by the *absence* of a line. That distinction stops being cosmetic the moment
  `FW_REQUIRE_SIGNATURE` is enabled on the firmware side.
- **The no-blocking-the-main-thread rule covers NETWORK I/O too, not just device
  I/O.** Every GitHub call the GUI makes runs on its own thread — `UpdateChecker`,
  `UpdateInstaller`, `FwUpDownloader`, `wincompose_install.InstallerDownloader` —
  and a menu handler must only start one and open a progress dialog, never call
  into `requests` itself. It is easy to miss because these calls *look* cheap next
  to a flash: `wincompose_install.find_installer()` is two requests (the
  latest-tag HEAD + the `expanded_assets` GET) at `HTTP_TIMEOUT` 5 s each, so
  inline in the click handler it froze the tray for ~10 s on an unreachable
  network (caught in review of its own PR, 2026-08). Where a thread needs to
  *resolve* something before its real work, give it a `None` input it resolves in
  `run()` (that downloader takes `info=None`) rather than resolving first on the
  caller's thread; report "nothing to do" through the finished callback with a
  sentinel (`NO_INSTALLER`) so the caller can branch without a second code path.
- `PolyCore` periodics/jobs publish results as core events (`emit(name, payload)`); the Qt client's observer (`PolyHost._on_core_event`) forwards them into `WorkerBridge.job_done` (`polyhost/gui/worker_bridge.py`), a queued Qt signal dispatched in `PolyHost._on_job_done`. **Worker-/core-side code must never touch Qt objects** — go through the event seam. `decide_reconnect_apply` lives in `polyhost/core/decisions.py` (re-exported from `worker_bridge`), unit-tested in `tests/gui/worker_bridge_test.py`.
- Reconnect is split three ways: `PolyCore._reconnect_probe` (worker, device I/O → plain snapshot dict; pops the firmware fresh-boot marker on every successful probe), `PolyCore.apply_reconnect` (operational half — state, decision tree, post-connect jobs, cache resets; emits `status_changed`; tested in `tests/core/poly_core_apply_test.py`), and `PolyHost._apply_reconnect_result` (Qt rendering: status entry, language menu, OS-language switch). `active_window_reporter` keeps the pywinctl poll on the main thread but delegates the switching decision to `PolyCore.tick_window_tracking`.
- **The probe is debounced** (`decide_probe_publish`, 3 strikes): the keyboard goes deaf for hundreds of ms after a large overlay transfer while it syncs images to the slave half over UART, so a single failed probe must NOT flap the connection state — that resets the MRU cache, wipes the overlays, and forces a resend that keeps the keyboard busy for the next probe (self-sustaining wipe-and-resend oscillation, seen in the field 2026-06-10). For the same reason the probe drains stale late replies first, never queries version/languages when the lang probe already failed (a stale GET_ID reply can fake a fresh connect), and `query_id`/`GET_LANG` use generous read timeouts (250/150 ms — fine on the worker, forbidden back when this ran on the UI thread).

## Key notes

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
- **GUI self-update must be applied by the DAEMON, not the client (daemon-by-default).**
  In daemon mode the tray GUI is a `--connect` client and a separate `--headless`
  daemon owns `PolyCore` — and therefore the **protocol gate** (its loaded
  `_version.__protocol__`). So the tray's "Check for updates → install" routes the
  install through the daemon over RPC (`RemoteCore.install_update` → `M_UPDATE_INSTALL`
  → `PolyCore.install_update`), letting the daemon overwrite the files and **re-exec
  itself** (`headless.py` `_on_update_event`). It must **not** run `UpdateInstaller`
  in the GUI process: that refreshed only the client while the daemon kept running the
  pre-update code, so the daemon stayed on the OLD `__protocol__` and its `FEATURE_MIN_PROTOCOL`
  table (historically it *rejected* the keyboard with *"Protocol mismatch, please update"*;
  under the range-connect model it instead keeps the keyboard on the old capability set —
  newer features disabled, status stuck on "update the host app") until manually restarted
  (field 2026-07). After the daemon re-execs, `PolyHost._on_update_done` (client mode)
  waits for the control endpoint to go **down → back LIVE** (`_await_daemon_restart_then_relaunch`)
  before relaunching the GUI — relaunching immediately would re-attach to the still-up
  **old** daemon (the bug) or race the re-exec and spawn a second daemon. The daemon's
  `update_*` **core events are dicts** (`{"pct","msg"}` / `{"relay_path"}` / `{"msg"}`)
  while the legacy in-GUI `UpdateInstaller` emits tuples/strings — `_on_job_done`
  normalizes both. The `polyctl update install` path already restarted the daemon
  correctly; only the tray menu path was broken.
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
  - ⚠️ **A bundle can report a FAILED flash and still read as UP TO DATE, so the version
    comparison alone must never decide what to re-flash.** The FONTPACK target writes **in
    place** at the slot, so the pack (header first, carrying `content_version`) is in flash
    as the chunks land; COMMIT only verifies the transport CRC and reloads. A flash whose
    COMMIT *acknowledgement* is lost therefore leaves a complete, CRC-valid slot — the
    firmware's `fontpack_bundle_version()` only answers for a slot that passed
    `fontpack_load()`'s full CRC32, so the next `GET_ID` advertises the new version and
    `decide_stale_bundles` says "nothing to do". Field 2026-08-17: `symbol` reported
    *"COMMIT failed — CRC mismatch or the font pack was rejected"*, was then **skipped on
    every later connect and on the manual sync**, and the glyphs were in fact fine all
    along. Two consequences that are easy to get wrong:
    - **The core remembers failures** (`_fontpack_failed`, slot → message) and re-flashes
      them regardless of version; `fontpack_bundle_status()` exposes `retry`/`last_error`
      per bundle plus a top-level `failed`, and the tray row relabels to *"Retry keyboard
      fonts (N failed)…"*. Without that the UI renders *"Keyboard fonts: up to date"*
      (disabled) over a bundle that never took — no route back from the GUI at all.
    - **A failed COMMIT is VERIFIED before being believed** (`_verify_flashed_bundle`):
      re-read `GET_ID` and, if the slot now advertises the shipped version, treat it as
      stored-with-a-caveat instead of re-sending tens of KB. ⚠️ The version block reflects
      the **master's** slots only, so it can never prove the *slave* got the bundle — on a
      `slave-unconfirmed` status say so in the note rather than claiming plain success.
      A `rejected` status is deliberately **not** verified (the keyboard told us it refused
      the data).
  - **One bundle's failure must not abort the pass.** `_fontpack_flash_bundles_job` flashes
    every target, collects the outcomes and emits **one** terminal event naming what landed
    and what failed. The old `return`-on-first-failure cost six perfectly good bundles a
    flash because `symbol` (slot 0, first in order) failed; they only got flashed minutes
    later because a firmware update happened to force a reconnect.
  - **`sync_fontpack(force=True)`** (`M_FONTPACK_SYNC {"force": true}`, `polyctl fontpack
    sync --force`, Developer → Font Pack → "Re-flash ALL bundles") re-sends every shipped
    bundle ignoring the comparison — the only recovery for a bundle the keyboard reports as
    current but renders wrong. Note the tray's "Update keyboard fonts" row and the menu's
    "Sync" both submit the *same* job as the on-connect auto-check, so before this existed
    pressing them could not re-flash such a bundle (the log line is identical either way,
    which is also why auto and manual runs are indistinguishable in `daemon_log.txt`).
  - **The COMMIT status is now three-valued** — `hid_fontpack.classify_commit_reply` maps
    the firmware's `.`/`R`/`L` (+ legacy `!` and no-reply) to `COMMIT_OK` /
    `COMMIT_REJECTED` / `COMMIT_NO_SLAVE` / `COMMIT_UNSPEC` / `COMMIT_NO_REPLY`, and
    `flash_fontpack`/`flash_doomwad`/`flash_doompack` return `(ok, msg, status)`. A
    non-`rejected` failure is **retried in place** (`_COMMIT_ATTEMPTS` 3) rather than
    re-streamed: re-running the firmware's finalize is free (the staged CRC and write
    cursor are untouched, and the slave's handler is idempotent), so a dropped bridge ACK
    on a busy split link — the observed failure, with `giveup=44` in that window — usually
    clears for the cost of one report. `rejected` is **not** retried; asking again cannot
    change what is in flash.
- **Font-pack inspect/extend tools** (`polyhost/gui/fontpack_inspector_dialog.py` +
  `fontpack_extend_dialog.py`, Qt-free logic in `polyhost/services/fontpack_*` +
  `fontgen*`): a standalone window to view every bundle glyph as
  the keycap draws it and to build/splice new glyphs from a TTF/OTF (pure-Python
  `fontconvert` parity). Launched from the tray's **Debugging** submenu (the
  "Inspect Font Packs…" entry), so it is **only shown when the app runs with
  developer mode** (`developer` in `host.py`) — it's a developer/power-user
  tool, hidden from the default menu. Unlike the other Debugging entries it works
  in both in-process and client mode (offline, no device needed). It loads the shipped bundles by default; **"Open .plyf…"**
  adds any saved/exported `.plyf` as a new tab (folded into the merged ALL_FONTS view
  + the Extend sources) so a file saved elsewhere can be re-inspected. ⚠️ **A `.plyf`
  carries no bundle name** — the PlyF header has only abi/`content_version`/font_count
  + per-font global ALL_FONTS index; the bundle id lives in `bundles.json`/the
  filename, so an opened tab is named after the file (`decode_pack` synthesises font
  names as `<filename_stem>#<gidx>`). The **View** selector offers four modes
  (`_BundleTab._mode`): **Glyph** (native size), **Keycap** (plain 72×40 white-on-
  black), and — matching the extend dialog — **Keycap OLED** (raw pixels) and
  **Keycap through cover** (diffused), both routed through `fontpack_render.glyph_cell`
  → `simulate_oled` (which returns an **RGB** cell; `_BundleTab._pm` keeps RGB via
  `_pil_to_pixmap` and only applies the semantic tints below to the plain 'L' modes).
  The grid shows **one cell per codepoint** (a
  deduped, continuous range) honouring **front-to-back precedence** (the firmware
  draws each cp from the lowest-global-index font with a glyph, `_BundleTab._stacks`):
  each cell renders the **winner** — **white** if this bundle draws it, **cyan** if
  it's borrowed from another bundle. When more than one font has the glyph, the
  losers are **overdrawn**: a "**stack**" marker (solid right+bottom border whose
  **depth = number of overdrawn glyphs**, `_stack_pixmap(depth=)`) flags it; hovering
  the bottom-right stack corner shows the overdrawn glyph **in the slot** (dim),
  **cycling** through them when there's more than one (`_hover`/`_cycle_advance`), and
  **double-click there edits the first overdrawn** while a double-click elsewhere edits
  the winner (`_edit_at`; `_on_edit`/`_bundle_of` target the clicked font's *own*
  bundle, which may be a different tab). Overlapping `fonts.yaml` ranges from the same
  source (e.g. a dedicated `_Light_` entry + broad `_EmjEffects_`/`_Emojis1_` all
  covering U+1F4A1) are why a cp can have 2+ overdraws. **Selecting a glyph highlights
  the whole range its font wins** (`_on_selection`, subtle tint), since the pack is
  organised in ranges. A glyph **edited
  this session** (the editor's OK committed it into the working copy) is re-rendered
  in-place from that working copy and bordered **green** (`MODIFIED_RGB`,
  `_BundleTab.apply_working`); "Save as… → Discard" reverts the tab to the loaded
  bundle. Edits **propagate across tabs**: `_commit_edit` rebuilds the merged
  ALL_FONTS view (`_rebuild_all_fonts`) and `_propagate` pushes it to every tab
  (`set_all_fonts`), so a cell in bundle B whose winner or overdrawn (stack) glyph
  lives in the edited bundle A re-renders from the new glyph — the visible
  tab rebuilds immediately, the rest lazily on next show. The inspector's
  **"Peek empty (from source)"** toggle
  renders the *empty* slots from their source font (via `fontpack_extend.peek_source_glyph`
  + the shipped render settings, needs the source font downloaded) as **amber
  previews** — candidates you can then double-click to edit/take; they are not in
  the pack. Peek **prefers a non-emoji (symbol/text) source over an emoji source**
  when the slot's own font isn't itself emoji (`_peek_candidates` style key), so a
  symbol codepoint that also exists in NotoEmoji/NotoColorEmoji previews from the
  clean symbol font (NotoSansSymbols) rather than the emoji glyph — even if the
  emoji font is lower-gidx / in-range / in-bundle. For an emoji slot the deferral is
  a no-op (the emoji source order stands). Peek also offers, as a **last-resort
  fallback, any downloaded catalog font that no bundle uses** (default render
  options, `_BundleTab._catalog` from `noto-fonts.yaml`) — so adding a font to the
  catalog (e.g. NotoSansMath) makes it usable in peek with **no code change**, even
  though it's in no pack. The extend dialog's **Source fonts** browser (always under the
  preview; click a font to use it, downloading first if needed) downloads/assigns
  the Noto source fonts via `polyhost/services/font_downloader.py`, which reads the
  catalog from **`polyhost/res/fonts/noto-fonts.yaml`**. ⚠️ That YAML is the **single
  source of truth shared byte-identically** with the firmware's
  `qmk_firmware/keyboards/polykybd/fonts/noto-fonts.yaml` (which `dl-fonts.sh` reads)
  — keep both in sync (`cmp`). The host stores a *flat* cache keyed on
  `basename(dest)`; the firmware honours the nested `dest` path.
  The extend dialog is a focused **glyph editor** (`FontPackExtendDialog`): it builds
  **one** glyph/font from a source + options and previews it, with just **OK / Cancel**
  — OK exposes the built glyph via `result_font`/`result_label`/`result_edit` (Cancel
  discards); it neither accumulates nor saves. Its preview shows each built keycap
  **next to the smooth, undithered glyph straight from the source font**
  (`fontpack_render.preview_sheet` → `reference_glyph_image`, always antialiased/colour
  regardless of the grayscale toggle), so you can compare the dithered keycap output
  against what the font actually draws while tuning. **Sequence-mode glyphs** (flags,
  matras) have a synthetic PUA pack codepoint the source font has no glyph for, so the
  reference is **HarfBuzz-shaped from the sequence** (`reference_sequence_image`,
  composites the shaped group) rather than looked up by codepoint — otherwise no
  reference showed beside a flag. **Scroll-wheel over the preview
  zooms** it (0.5×–7.0× in 0.5 steps; the render functions take a fractional `scale`,
  `fontpack_render._px` rounds to pixels). A **Preview** radio group (Normal · OLED ·
  Keycap, `_preview_style`) shows the keycap the way the physical per-key OLED renders
  it via `fontpack_render.simulate_oled` (Qt-free, NumPy/PIL) + `preview_sheet(style=)`
  (only the keycap is post-processed; the source reference + chrome stay natural):
  lit pixels are a **cool white** (`OLED_TINT` — a hint of blue; the strong cyan in
  photos is a camera artifact, not what the eye sees) on true black with a slightly
  bluer **bloom**. The two OLED styles are presets over `simulate_oled`'s knobs —
  **OLED** = the raw pixels (crisp square grid, jitter/diffusion off) and **Keycap** =
  as seen through the clear keycap cover (adds **per-pixel brightness jitter** — seeded
  so the lit area shimmers without flicker — a **staggered grid** and a **diffusion**
  blur that lets pixels bleed, modelling the cover's light-guide, not the panel; the
  blur amount is **spatially varied** by a smooth seeded mask — a lighter/heavier blur
  mixed per region so it isn't one uniform smear). A
  post-blur **brightness** gain lifts both styles (higher for Keycap, since the
  diffusion spreads/dims thin strokes);
  `preview_sheet(oled=)` runs **only the keycap** through it (the source-font reference
  + chrome stay natural for comparison) and returns RGB, so the preview pixmap path
  preserves colour (`_pil_to_pixmap`). **Flag keycaps** (the PUA 0xE000 band) are
  drawn on hardware through a **single-font array** (baseline adjustment 0), so the
  keycap render uses the **flag's own yAdvance** as the baseline reference
  (`fontpack_render.base_yadv_for`), NOT the `(yAdvance − IconsFont 40)` shift the
  in-pack g_all_fonts glyphs get — without this a tall flag (yAdvance 54) was shifted
  +14 px down and its bottom rows clipped off the 40 px keycap (the "flag preview cut
  off at the bottom" bug). Emoji (yAdvance 48, drawn via g_all_fonts) keep the shift,
  so the fix is gated to the flag band only. **Reset** restores the render options to
  the values the dialog opened with (`_snapshot` taken after prefill). **Auto update**
  (default on) re-renders on any control change (debounced). Layout niceties: each
  float control (gamma / contrast / exposure / sharpen / saturation) is a **fixed-width
  spin (0.1 step) with a slider beside it** (`_with_slider`, one notch = 0.1); range
  **first–last share one row**; the four flag checkboxes (grayscale/normalize/invert/
  edge) are a **2×2 grid**; the source-font browser's **"Download all" sits on top** of
  the list (clear of OK/Cancel).
  The **accumulate + save** side lives in the **inspector**, not the editor: the
  inspector owns per-bundle in-memory **working copies** (`_work`/`_pending` keyed by
  source index). Each editor OK calls `FontPackInspectorDialog._commit_edit` →
  `replace_glyph` (edit mode) or `splice_font` (whole-font add) into that bundle's
  working copy, appends a pending-edit description, and marks the tab with a "● "
  prefix. The toolbar's **"Save as…"** opens `FontPackSaveDialog` for the current
  bundle: metadata (abi / current content version / working fonts·glyphs·size), the
  **pending-edits list**, an editable **content_version** spin (default current+1 —
  **one bump for all accumulated edits**), and **Save .plyf… / Flash / Discard /
  Close** (`encode_pack(working_fonts, version)` is what's written/flashed; Discard
  drops that bundle's working copy). Flash is only offered when the inspector was
  given a `flash_cb`.
  When you **edit** a glyph, the editor pre-fills the render controls (size,
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
  **Sequence-mode glyphs** (the language-layer flags): a record with a `sequence`
  field is a HarfBuzz-shaped font (`-S`), so the editor switches to **sequence mode**
  and pre-fills the single group for the edited codepoint (group = `cp − font.first`,
  seq base set to `cp` so Build emits exactly that one glyph). The **flag font is NOT
  in fonts.yaml** (it's `pack_extra` from `gen-lang-fonts.sh`), so it has no record in
  `fontpack_render_settings.json`; its options + `seq_first` + the per-flag
  regional-indicator `sequence` live in **`polyhost/res/fontpack/lang_flags.json`**,
  which the editor uses as the record when the edited cp is in the flag range. ⚠️
  `lang_flags.json` is mirrored **byte-identically** with the firmware's
  `base/fonts/generated/lang_flags.json` (emitted by `gen-lang-fonts.sh`) — keep both
  in sync (`cmp`). Editing a flag needs **NotoColorEmoji** downloaded; if its cached
  file is truncated (a bad download) FreeType fails to open it — re-download. A CBDT
  **colour-bitmap font (NotoColorEmoji) renders whether or not grayscale is checked**:
  it has no outlines, so `fontgen._open_color_font` decodes it via fontTools for any
  source with bitmap strikes (`num_fixed_sizes>0`), not only in `-g` mode — otherwise
  a mono build hit FreeType's "unimplemented feature" on the PNG-based glyph.
  **Matra/combining-mark fonts** (Devanagari/Bengali/Telugu/Tamil/Thai/Vietnamese,
  PUA 0xE100+) are sequence-mode **and** use fontconvert `-C` composite (each group
  composites a mark onto the dotted circle U+25CC). The editor has a **Composite -C**
  checkbox (enabled in sequence mode); `_setup_sequence_edit` ticks it from the
  record's `composite` field (the `fontpack_render_settings.json` matra records now
  carry `composite: true` + `seq_first`, emitted by `generate_fonts.py` from the
  `-C`/`-F` extra_args), falling back to **inferring** it (every group starts with
  `25CC` → composite; regional-indicator flag groups don't) for older manifests.
  Host builds matras via fontgen's mono composite path.
- **Source-font download validation** (`font_downloader.py`): a download is rejected
  (`DownloadError`, no file cached) when it's short (Content-Length mismatch) or not a
  complete sfnt (`_validate_sfnt` checks the table directory fits the file) — this is
  the fix for a proxy-truncated NotoColorEmoji that FreeType then refused to open.
  `is_downloaded()` re-validates, so an already-cached corrupt file reads as missing
  and is re-fetched (overwritten); `download_font(force=True)` always re-downloads.
- **Glyph-script override (protocol 9+; expanded set at v10)**: HID cmd 30
  (`GLYPH_SCRIPT`) selects a glyph-script *override* of the keycap language legends —
  `GlyphScript.STANDARD` (0, normal) or one of the fantasy/retro scripts from the
  `fantasy` font-pack bundle. The `GlyphScript` enum (`command_ids.py`) is append-only
  and byte-identical to the firmware `poly_glyph_script`: `TENGWAR=1`, then the v10
  expansion `RUNES=2, AUREBESH=3, SGA=4, CIRTH=5, IBMVGA=6, C64=7, AMIGA=8, APL=9,
  BRAILLE=10`. Wired like idle-style (cmd 28): `PolyKybd.get/set_glyph_script` +
  `GLYPH_SCRIPT_MIN_PROTOCOL=9`, `PolyCore.get/set_glyph_script`, `M_GLYPH_SCRIPT_GET/SET`,
  `RemoteCore`, and `polyctl glyph-script [standard|tengwar|runes|…|braille]` (choices
  derived from the enum). GUI: the tray **"Glyph Script"** submenu (radio, built from
  the enum via `GLYPH_SCRIPT_LABELS` in `host.py`) **plus** a **"Reset glyph script to
  Standard"** button in the settings dialog (`SettingsDialog.setup(reset_glyph_script=…)`,
  shown only when a device is present). Firmware persists the choice; the glyphs need
  the `fantasy` bundle flashed (auto on connect; regrown to `content_version 2` for the
  expansion — reshipped `polyhost/res/fontpack/fantasy.plyf` + `bundles.json`).
  **Open-ended index (v10+):** the firmware accepts ANY glyph-script byte `0..0xFE` and
  renders the normal legend for one it can't draw, so the host may offer more scripts
  than a given keyboard has (they silently degrade) and **adding a new script needs NO
  `__protocol__` bump** — just a new `GlyphScript` value + `GLYPH_SCRIPT_LABELS` entry +
  the shipped font. The `__protocol__` 9→10 bump happened once, to establish that
  open-ended contract (pre-v10 firmware NACKed unknown indices); don't bump it again for
  more scripts. `GLYPH_SCRIPT_MIN_PROTOCOL=9` is a `FEATURE_MIN_PROTOCOL` entry (see the
  range-connect note above), so the Glyph-Script menu is disabled on a pre-v9 keyboard but
  the rest of the app still connects; within a glyph-script-capable device the script set is
  free to grow.
- **Tray/menu icons (`polyhost/res/icons/`) are Material Symbols at optical size
  48 — fetch the `_48px` cut, never `_24px`.** The optical-size axis changes the
  **geometry**, not just the header: the same symbol at opsz24 is drawn with
  heavier strokes for a smaller render target. Measured on a 48px canvas, an
  opsz24 file carries **~25% more ink on average (max +43%)** than its opsz48
  twin, so a mixed-opsz set renders visibly uneven — the new icons look bolder
  than the untouched ones sitting next to them in the same menu. This cost a
  full re-fetch of 28 files (2026-07).
  - Source: `https://raw.githubusercontent.com/google/material-design-icons/master/symbols/web/<name>/materialsymbolsoutlined/<name>_48px.svg`
    (filled variant: `<name>_fill1_48px.svg` — that's how brightness 100% differs
    from 50%). Emit as a single `<path>` under
    `<svg height="48px" viewBox="0 -960 960 960" width="48px" fill="#RRGGBB">`,
    one fill on the `<svg>` element, tinted from the palette documented in
    `gui/get_icon.py`.
  - ⚠️ **A wrong/missing filename fails SILENTLY**: `QIcon()` on a nonexistent
    path returns an **empty** icon — nothing raises at import or at runtime, the
    menu entry just renders without one. Icon names are plain string literals at
    ~50 `get_icon()` call sites, so **`tests/gui/icon_assets_test.py`** asserts
    every name resolves, that no shipped `.svg` is unreferenced (11 orphans had
    accumulated), and that the opsz48/single-fill format holds. It is Qt-free, so
    it runs in the normal suite rather than only under xvfb.
  - **Judge a candidate glyph by rendering and measuring it, not by its name.**
    Rasterise to a fixed canvas (`cairosvg` + PIL) and compare **ink coverage**
    and **glyph bounding height** against the set (baseline ≈19% ink, ≈34px tall
    on 48px). That is what caught both the opsz mismatch above and `abc` being
    only 12px tall — half the next smallest icon — which eyeballing the render
    had missed. The measurement also overruled three name-based picks: the
    `brightness_*` family is not a coherent ramp (the `backlight_*` family is),
    and `bedtime`/`bedtime_off` beat a sun for idle start/stop.
- **The font-pack flash events carry a `kind` — label UIs from it, not the event name.**
  The doom easter egg's game data (`.whx`) and executable engine pack (`.plyx`) ride the
  **font-pack transport**, so `PolyCore.install_doomwad`/`install_doompack` emit the same
  `fontpack_flash_progress`/`fontpack_flash_done` events as a real bundle flash. Both
  payloads now carry `"kind"` (`fontpack`/`doomwad`/`doompack`, `polyhost/core/events.py`
  `FLASH_KIND_*` + `flash_kind_label()`), and `polyctl` + the tray render their wording from
  it — a hardcoded "fontpack"/"updating keyboard fonts" reported a `.plyx` install as a font
  pack (field 2026-08). A missing `kind` means font pack (older cores), so the fallback is
  the previous wording.
  - ⚠️ **`install_doompack` sends UNSIGNED EXECUTABLE CODE, and nothing on either side
    checks a signature for it.** The `.sig` handling in `hid_fw_up` covers the *firmware*
    image only; the font-pack transport has no equivalent, and the firmware's
    `fw_staging_check_signature()` is reached only on the `FW_TARGET_FIRMWARE` target. The
    keyboard then *branches into* a `.plyx` it validated with a CRC32 (no MPU on the M0+),
    so anything that can talk raw HID can flash a crafted pack, select `IDLE_STYLE_IDDQD`
    over cmd 28, and get code execution on the next idle. Do **not** describe the keyboard
    as "signed firmware, so a malicious flash is covered" — it is not. Tracked as **FW-9**
    (open, high) in `polykybd-ctnd/docs/SECURITY_AUDIT.md`; the fix is firmware-side
    (verify the pack at load time), so there is nothing for the host to do beyond not
    over-claiming.
- **WinCompose install from the tray (Windows)**: WinCompose is what gives the keyboard real
  unicode output on Windows (`polyhost/input/unicode_input.py` — `wincompose_running()` picks
  `InputMethod.WinCompose` over the far more limited native path), so a fresh Windows box has
  the host but no WinCompose. The tray shows **"Install WinCompose…"** exactly while it is
  *not* running (`host.py` `_refresh_wincompose_action`, re-probed on `menu.aboutToShow` — no
  background polling), downloading our fork's installer via `services/wincompose_install.py`
  (Qt-free; reuses the updater's **web**, non-API release lookup so it doesn't share
  api.github.com's 60/hour anonymous limit) and starting it with `os.startfile` so Windows
  raises the normal UAC prompt. **No release is published on `thpoll83/wincompose` yet** —
  `find_installer()` returns None then, and the menu falls back to opening the releases page,
  so the entry is useful before and after the first release. Because the unicode mode is only
  pushed on *connect*, a fresh install would otherwise not reach the keyboard until a replug:
  the same menu-open probe fires `PolyCore.refresh_unicode_mode()` on a not-running→running
  transition (`M_UNICODE_MODE_REFRESH` → `RemoteCore` mirror → `polyctl unicode-mode`).
  `process_exists()` runs TASKLIST with **`CREATE_NO_WINDOW`** (else a console flashes under
  the `pythonw`/`.vbs` autostart chain) and **never raises** — it sits on the post-connect
  path, where an exception would abort the whole connect flow over a cosmetic detection.
- **The tray menu is TWO-TIER: a normal menu of ~9 rows, plus a Developer submenu
  that only ever ADDS.** The old menu had 16 top-level entries, one of which ("All
  PolyKybd Commands") held 15 more — mostly diagnostics, one click from a normal
  user. Now: status · Pause · [Language] · Brightness · Idle Display · Keycap Script ·
  Configure Keymap · Updates · Maintenance · Settings · Help & About · Quit, with
  **Developer** slotted in before Settings when developer mode is on. The invariant is
  that turning developer mode on **does not rearrange anything** (asserted by
  `tests/gui/host_client_test.py` `test_developer_mode_only_adds_a_submenu`), so muscle
  memory survives the toggle. `CommandsSubMenu` (`gui/cmd_menu.py`) builds Brightness +
  Maintenance + the Developer submenus and gates them off **explicit action lists**
  (`_device_actions` follow `connected`, `_fw_actions` follow `fw_enabled`) — it can no
  longer walk one menu's actions, since they live under different parents. ⚠️
  `managed_connection_status` still blanket-disables every top-level action first, so a
  **new group parent must be re-enabled explicitly there** or its whole submenu goes
  unreachable on a disconnect (that is why Updates / Help & About / Pause are listed).
  Two rows are **contextual** (built once, `setVisible` toggled): the newer-firmware
  entry (only while `safe_mode`) and Install WinCompose (only while it isn't running).
  The language menu is built lazily and inserts itself at `self._lang_anchor`
  (Brightness), not at index 1.
- **A menu row that can answer its own question should — the font-pack row is the
  pattern.** `PolyCore.fontpack_bundle_status()` is a **local** comparison (the cached
  `GET_ID` version block vs the shipped `bundles.json`, no device I/O on either side of
  the RPC), so the Updates row relabels itself on `aboutToShow` — *"Keyboard fonts: up
  to date"* (disabled) or *"Update keyboard fonts (N)…"* with the stale bundle ids in
  its tooltip — instead of hiding the answer behind a status dialog. Same idea in
  Brightness: *"Back to automatic"* renames itself to *"Clear manual override"* when
  `brightness_set_daylight_dependent` is off, because that is what it would actually do.
  Keep such refreshes to reads that are genuinely free; an `aboutToShow` that touches
  the device would stall the menu.
- **"Back to automatic" exists because the firmware's auto mode is a ONE-WAY DOOR from
  the host's side.** Any manual `set_brightness` drops the keyboard out of auto mode
  (its own LTR-559 sensor then backs off too) and nothing re-engages it until the host
  deliberately re-asserts — so the tray's brightness presets used to strand the keyboard
  in manual until a replug. The entry calls `PolyCore.refresh_daylight_brightness()`
  (daylight on → `VOLATILE|AUTO_ON` + the current value; off → `AUTO_OFF`, i.e. back to
  the keyboard's stored manual level), which is now `M_DAYLIGHT_REFRESH` + a `RemoteCore`
  mirror + `polyctl brightness --auto`. It returns `(True, "queued")` like every other
  command-API method — it is a `submit`, not a `run_sync`.
- **Developer mode (`--dev`) is SEPARATE from log verbosity — and it is a persisted
  setting, not just a flag.** `--debug N` used to conflate three things: the log level,
  the developer/diagnostic UI surface, and `allow_key_injection`. It is now split:
  **`--dev [0|1|2]`** (bare = 1) carries the level *and* turns developer mode on, while
  the **`developer_mode`** setting (default False) governs the surface alone. `main_app.resolve_dev`
  is the one pure decision point (unit-tested): flag absent → the setting decides and
  logging stays INFO; flag present → it wins **in both directions**, so `--dev 0` forces
  developer mode off over an enabled setting (hence `default=None` — "flag absent" must
  stay distinguishable from `--dev 0`). The setting exists because under daemon-by-default
  the tray GUI is launched by autostart **with no flags**, so a flag-only gate made every
  developer tool unreachable unless you started the app by hand. `--debug N` survives as a
  hidden deprecated alias (existing shortcuts / autostart entries) that logs a warning.
  `PolyHost(log_level, verbosity, developer, …)`, `run_headless(..., developer=)` and
  `SettingsDialog.setup(..., developer_mode=)` all take the two independently; the
  GUI-spawned daemon inherits only the **resolved level** as `--dev N` (`_spawned_daemon_flags`)
  and reads `developer_mode` from the same settings file itself. Read it at startup with
  `settings.read_setting("developer_mode", False)` — the file-only helper — **not**
  `PolySettings()`, which creates/rewrites the config and log-dumps every key before the
  launch path is even known.
- **Anonymous usage telemetry (`polyhost/services/telemetry.py` + `telemetry-collector/`)**:
  one small JSON POST per install per day — host/protocol version, OS + coarse release,
  arch, python, run mode, the attached keyboard's model/fw/protocol/hw/font-pack versions,
  six counters since the last report (sessions, connects, reconnect_flaps, fw_flashes,
  fontpack_flashes, update_installs), and a locally-generated random `install_id`. **On by
  default**, opt out in the settings dialog or `polyctl telemetry disable`;
  `polyctl telemetry status|preview|send` are the rest of the CLI surface. `PolyCore` owns
  the reporter (`start_telemetry()` is called next to `worker.start()` in **both**
  `host.py` and `headless.py` — both construct `PolyCore(start_worker=False)`, so the
  reporter does not start itself). The endpoint is `TELEMETRY_ENDPOINT` in `settings.py`;
  **empty disables sending entirely**, which is how it ships before a collector exists.
  - **The payload is an ALLOW-LIST at both ends**, and that is a privacy guarantee, not a
    style choice: `build_payload()` copies named fields (never `**status`), and the Worker
    re-validates and rebuilds the row it stores. The host can see window titles and app
    names — it reads them constantly for overlays — so the frozen `PAYLOAD_KEYS` test in
    `tests/services/telemetry_test.py` exists to make an accidental widening fail loudly.
    Never add a field by spreading a status dict.
  - ⚠️ **There is NO in-app consent step.** The first-run dialog was removed (#153,
    "a modal on every upgrade is a poor trade for a disclosure that arrives after the
    install"), so the **release notes are the disclosure** and the one INFO line
    `_log_telemetry_notice` prints at every start is the only thing a headless daemon can
    say. Don't gate that line on an "already told them" flag, downgrade it to debug, or
    drop it in a logging cleanup. Write the release notes *before* shipping a release that
    sets the endpoint. Posture + residual risk: `polykybd-ctnd/docs/SECURITY_AUDIT.md`
    **HOST-3**; user-facing page: `docs/telemetry.md` and the public
    `software/telemetry` docs page.
  - **Collector**: a Cloudflare Worker + D1 (`telemetry-collector/`, deployed by
    `.github/workflows/deploy-telemetry.yml` on push to `main`). It is **write-only by
    design** — no read route, therefore no route that can leak the dataset. Read the data
    with `wrangler d1 execute` or **`python telemetry-collector/dashboard.py --open`**,
    which renders a self-contained HTML dashboard locally (per-install version splits from
    each install's *newest* report, so a long-running tester doesn't outvote a new one).
    A hosted version is planned but unbuilt — design and its costs in
    `telemetry-collector/HOSTED_DASHBOARD.md`. Full setup/runbook: `telemetry-collector/SETUP.md`.
- ⚠️ **`workers.dev` is CLOUDFLARE's zone, not ours — so every zone-scoped Cloudflare
  product is unavailable on the collector.** This has now cost a round twice: first on
  rate limiting (WAF rate-limiting rules are zone-scoped, so the **Workers rate-limit
  binding** in `wrangler.toml` is the mechanism that works), then again on **Cloudflare
  Access**, the obvious way to put SSO in front of a hosted dashboard — also unavailable,
  so that auth would have to live *inside* the Worker until a custom domain exists. Rule
  of thumb: anything Cloudflare describes as "protect a route/hostname" needs a zone you
  own; anything configured as a Worker **binding** works. Don't accept advice (including
  mine) that reaches for a zone-level feature here without checking this first.
- **`wrangler` gotchas that fail SILENTLY** (full detail in `telemetry-collector/SETUP.md`):
  - ⚠️ **A command without `--remote` hits the LOCAL sqlite file and reports success.**
    So a `DELETE` appears to run and the row is still there on the next `SELECT --remote`
    — deleted three times before the cause was obvious (2026-08-07). This applies to every
    `d1 execute`, not just the schema step.
  - **`d1 info <name>` resolves the name through the local `wrangler.toml`**, so it 7404s
    ("database could not be found") while the file still holds a placeholder id. Use
    **`d1 list`** to get the real id.
  - **The API token needs `Workers Scripts: Edit` (plus `D1: Edit`).** Without it the
    deploy fails with `Authentication error [code: 10000]`, which names the *endpoint* it
    could not reach and not the permission it lacked. Verify a token fix by triggering the
    workflow (`workflow_dispatch`) rather than assuming — that is a 30 s check.
  - **`binding = "DB"` in `wrangler.toml` must stay `DB`**: `d1 create` prints a suggested
    binding named after the *database*, and adopting it 503s every ping.
- **Log collection is ONE Qt-free service with three front ends —
  `polyhost/services/log_bundle.py`.** "Send me your log" used to be a request
  nobody could satisfy: the logs are **five** rotating files
  (`host_log.txt`, `daemon_log.txt`, `polykybd_console.txt`, `startup_log.txt`,
  `forwarder_log.txt`) × up to 3 backups each, written **relative to the process
  cwd**, and under daemon-by-default the half that matters is the *daemon's*, not
  the GUI's. `build_bundle()` writes a `.zip` (logs + `diagnostics.txt` + a
  redacted `settings.yaml` + a README stating the timeframe and redaction state);
  `recent_text()` returns the same content for the clipboard. Front ends: the tray's
  **Help & About → "Collect logs…"**, a **"Collect Logs…"** button in the log viewer,
  and **`polyctl logs bundle|show|paths`**. Four things that are load-bearing:
  - ⚠️ **`polyctl logs` MUST work with no host running** — `main()` routes it
    through `_is_offline_command` *before* `connect()`, and a reachable daemon only
    enriches the diagnostics. The moment a user most needs the logs is the one where
    the app failed to start or the daemon died, i.e. exactly when `connect()` fails.
    Don't "simplify" it back onto the normal connect-first path.
  - **The rotation chain is read `.N` → `.1` → base, i.e. OLDEST first.**
    `RotatingFileHandler` moves the live file to `.1` and shifts the rest up, so
    reading base-first silently produces a backwards concatenation.
  - **Continuation lines inherit their record's keep/drop decision** in
    `slice_lines`. A traceback carries no timestamp of its own, so a naive
    per-line time filter keeps the `ERROR` line and drops the half that says what
    actually failed.
  - **Redaction is anchored on the log message's own wording, not "anything in
    quotes"** (`_TITLE_PATTERNS`), and masks **window titles only** — app/exe names
    are kept, since that is what overlay-matching support rounds actually need.
    Titles can name documents ("Q3 layoffs.xlsx"), so the dialog says so in red when
    the box is unticked; default is OFF because a first support round with everything
    masked usually has to be repeated. `browser_report_token` / `telemetry_install_id`
    are masked **always**, independent of that flag.
- **"Report a Problem" is the guided sibling of log collection —
  `polyhost/services/problem_report.py` + `gui/report_problem_dialog.py`.** The
  tray's **Help & About → "Report a Problem…"** takes a description, builds a log
  bundle, puts the composed issue body on the clipboard and opens a **pre-filled
  GitHub issue** in the browser. "Collect logs…" beside it stays the manual half,
  for when the file is going somewhere else. Four things are deliberate:
  - ⚠️ **Redaction defaults ON here and OFF in "Collect logs…", and that
    asymmetry is the point.** A local bundle is a file you inspect before
    sending; a report is aimed at a **public** tracker. Same data, different
    destination, so the safe default flips.
  - **The issue body carries NO log lines** — only the description, the
    diagnostics and the bundle's *filename*, with an instruction to attach it.
    GitHub has no API to attach a file to an issue without a token, and shipping
    one in an open-source client is shipping a public credential; more
    importantly, an attachment is a file the reporter can look at before
    uploading, which pasted log text is not.
  - **Diagnostics are path-scrubbed** (`scrub_paths`): `_diagnostics_text` ends
    with `Config:`/`Logs:` lines, and on every platform those contain the account
    name (`C:\Users\tom\…`, `/home/tom/…`). Home → `~`, plus a regex for any
    *other* user directory (a daemon under another account, another drive).
  - **A pre-filled new-issue URL is a GET**, so an oversized body is truncated or
    refused somewhere between browser and GitHub. `issue_url_for()` falls back to
    the blank form above `MAX_URL_BYTES` (6000); the body is on the clipboard
    either way, so the fallback costs a paste rather than the report. A test
    pins that a *realistic* report still prefills — otherwise the fallback
    quietly becomes the normal path.
- **Linux HID permissions**: `polyhost/device/99-hid.rules` must be installed as a udev rule for non-root HID access.
- **Venv**: always use `PolyKybdHost/.venv/bin/python` — system `python3` lacks numpy, PyQt5, and other runtime deps. 
  - **Note on multiple venvs**: This project shares a workspace with `qmk_firmware/`. The QMK build uses a separate global venv (`~/.qmk_venv`) installed by the session setup script. The two venvs are **completely isolated and do not interfere** — each has its own Python executable and `site-packages`. When you activate `source .venv/bin/activate` in PolyKybdHost, it activates *this* project's venv; QMK commands via the global alias (e.g., `qmk compile`) still use the separate `~/.qmk_venv` and will not conflict with PolyKybdHost's dependencies.
  - **In a fresh remote/web container the `.venv` does not exist yet** — create it and install the test deps: `python3 -m venv .venv && .venv/bin/pip install numpy pyserial hid platformdirs pyyaml pillow`, plus the hidapi **system** libs `sudo apt-get install -y libhidapi-hidraw0 libhidapi-libusb0` (the `hid` module raises `ImportError: Unable to load any of the following libraries:libhidapi-*` without them). That set is enough to run the device/unit tests (`tests.device.*`); GUI tests additionally need an X server (see below).
  - **To run the WHOLE suite** (not just `tests.device.*` — do this after any change touching
    `core/`, `gui/`, or `cli/`) you also need `requests packaging pynput pvlib geocoder PyQt5`
    (pip) **and** `xvfb x11-xserver-utils` (apt), run under `xvfb-run -a .venv/bin/python -m
    unittest discover -s ./tests -p "*_test.py"`. Without those deps `services/updater`,
    `sunlight_helper`, `langcode_flag`, `win_helper_parse`, and the `host_client`
    GUI-subprocess tests **ERROR and masquerade as failures** — they are missing-dependency
    env failures, not regressions (confirm by `git stash` + re-running on the pristine tree).
    A fully green run prints `OK (skipped=N)` with the env-gated tests skipped, not errored.
- **`hid_reconnect_retries` is clamped to ≥1 in `PolyKybd.connect()`** (`max(1, …)`, `device/poly_kybd.py`): `connect()` runs on every ~1 s reconnect probe, and with the setting at 0 the `range(retries)` GET_ID loop was skipped entirely, so it blindly re-enumerated the HID interface every probe — `Re-enumerating HID after 0 failed attempts…` log spam plus handle churn that can clip in-flight overlay transfers. **Nothing in the codebase writes this key** (grep-verified) — a 0/negative value is a hand-edit or stale config, not a code path; default is 5 (`settings.py`). Don't remove the clamp.
- **Chromium is available headless in the dev/remote container — use it to LOOK at
  generated HTML/SVG rather than reading the markup.**
  `/opt/pw-browsers/chromium --headless --no-sandbox --disable-gpu --hide-scrollbars
  --window-size=1100,2400 --screenshot=out.png "file:///abs/path.html"`, then `Read` the
  PNG. Add `--blink-settings=preferredColorScheme=0` to force the **dark** palette (the
  default render is light), which is the only practical way to check a
  `prefers-color-scheme` design without a browser in front of you. Ignore the D-Bus
  `ERROR:` lines — it screenshots fine anyway. This is what caught the telemetry
  dashboard's x-axis labels collapsing into an unreadable smear in the small-multiples
  grid: the HTML and the tests were both perfectly correct, and the defect existed only
  in the render. Same reasoning as judging a tray icon by rasterising it (above) —
  measure or look, don't infer from the source.
- **Test discovery**: test files follow `*_test.py` naming under `tests/` mirroring `polyhost/` structure. pytest is disabled in VS Code config; use `unittest`. New test packages require an `__init__.py`.
- ⚠️ **A stale `.pyc` can survive a CORRECT fix — clear `__pycache__` before you
  disbelieve your own change.** Python invalidates cached bytecode on
  **(mtime, size)**, so a **length-neutral edit landing in the same mtime second**
  as the existing `.pyc` is invisible to it and the *old* code keeps running. That
  is not exotic: it happened here renaming a format placeholder `stale` → `state`
  (5 chars → 5 chars) moments after the previous write, and the test kept failing
  with the *old* `TypeError` while the source on disk was already right — the
  traceback even quoted a line that no longer existed. Tell: a traceback whose
  quoted source doesn't match the file. Fix:
  `find . -name __pycache__ -path "*/polyhost/*" -exec rm -rf {} +`. Suspect it
  whenever a fix "doesn't take" — especially after a `cp`/restore, which sets a
  fresh mtime but can land in the same second.
- **No *test* CI**: no workflow runs the unit tests. (The repo *does* have two
  workflows — `bump-version.yml` + `release.yml`; see **Releases** below.)
- **GUI tests need a display**: `tests/gui/host_client_test.py` constructs the real `PolyHost` (default + `--connect` client mode) in a subprocess (one `QApplication`/process; `pynput` needs X) with Qt forced to `offscreen`. They **skip unless `DISPLAY` is set** — run them under a virtual X server: `xvfb-run -a .venv/bin/python -m unittest tests.gui.host_client_test`. `host.py` can't even be *imported* without an X server (pynput at module load), so plain `unittest discover` skips them. Installing `x11-xserver-utils` (xrandr) lets the in-process path construct under xvfb too (pywinctl/pymonctl `sys.exit(1)` without it).
  - ⚠️ **Do not chain two `xvfb-run -a` invocations in one shell command** — the
    second one hangs (observed ~10 min at 0.7% CPU / 4 s CPU time, on a suite
    that had run green in 27 s moments earlier; both were auto-picking a display).
    Run them as separate commands.
  - **To RENDER a widget headless (screenshots for the docs), you need BOTH
    `xvfb-run` and `QT_QPA_PLATFORM=offscreen`** — and for opposite reasons. Qt's
    **xcb** plugin does not load in the container at all ("Could not load the Qt
    platform plugin xcb ... even though it was found"), so a real display does not
    help Qt; `offscreen` renders into pixmaps perfectly well. The X display is
    still required, but only for **pynput**, which `host.py` imports at module load
    and which refuses to import without an X connection. Hence
    `xvfb-run -a env QT_QPA_PLATFORM=offscreen .venv/bin/python …` —
    **`tools/render_tray_menu.py`** does exactly this to regenerate the tray-menu
    screenshots used by the docs site (real `QMenu`, real labels/icons/order, driven
    in `--connect` client mode against a fake connected core, since a menu with no
    keyboard attached renders entirely greyed out).
    - ⚠️ Size a menu with **`resize(sizeHint())`, never `adjustSize()`**:
      `adjustSize` clamps a window to **2/3 of the screen**, and the offscreen
      platform reports an 800×600 screen — so anything taller than 400 px is
      silently cropped. The developer-mode menu lost its last row that way, with no
      warning and no error; only looking at the PNG caught it.
- **Use `scripts/run_tests.py` when a run might hang — it has a stall watchdog.**
  The suite is **~25 s** (~27 s under xvfb, where the 11 GUI-subprocess tests run
  instead of skipping). Twice on 2026-08-03 it instead wedged past a 200 s
  timeout with **no output at all** — and a bare `timeout` kill discards exactly
  the information you need. The runner arms
  `faulthandler.dump_traceback_later(..., exit=True)`, so a stall prints every
  thread's stack and fails the command:
  `python scripts/run_tests.py [--timeout 180] [-s tests/device]`.
  ⚠️ **Set `--timeout` BELOW whatever will kill the shell, or the dump is lost.**
  `--timeout 240` under a 120 s tool timeout means the outer kill lands first:
  SIGTERM, exit 143, **no traceback**. That cost three losses of the one
  artifact that identifies a stall. `--timeout 60` is plenty for a 25–28 s suite
  and fires well inside any shell limit. Redirect to a file
  (`> /tmp/tr.log 2>&1`) and read the whole thing; do **not** pipe it through
  `tail`, which has eaten the dump before.
- **✅ The intermittent test-suite stall is FIXED (2026-08-11): it was a deadlock in
  `ControlServer.stop()`, not environment flakiness.** It had gone unexplained
  across ~3 sessions and 20+ non-reproducing runs; the watchdog dump (finally
  captured once `--timeout` sat under the shell limit) points at it exactly.
  The hang is on the **main thread**, in
  `tests/server/instance_test.py::test_probe_auth_mismatch_is_not_stale` →
  `ControlServer.stop()` → `mpc.Client(...)` → `answer_challenge` →
  `recv_bytes`, i.e. blocked forever in the authkey handshake.
  - **Mechanism.** `stop()` sets `_running = False` **first**, then connects a
    throwaway `mpc.Client` to unblock the blocking `accept()`. But
    `multiprocessing.connection.Client` with an `authkey` performs a **blocking,
    un-timeoutable** challenge/response, and only a thread sitting inside
    `Listener.accept()` answers it. If the accept loop has already observed
    `_running == False` and exited, nothing ever delivers the challenge: the OS
    backlog completes the connect, and `stop()` blocks forever on the main
    thread — wedging the whole run.
  - **Why THIS test.** The auth-mismatch case deliberately drives the accept
    loop through its `AuthenticationError` path immediately before `stop()`,
    which is exactly the window where the loop re-checks `_running` and leaves.
    That is why the stall is rare, un-reproducible on demand, and always lands
    near the end of the suite.
  - **This supersedes the earlier "unexplained environment flakiness" note.**
    Ruled out then and still not the cause: orphaned processes, stale control
    sockets, and the `daemon=True` `RemoteCore` event pump (the ~20 threads
    parked in `recv_message` in the dump are that pump and the per-connection
    readers — they are noise, not the hang; **read the `Current thread` /
    unittest-framed stack, not the thread count**).
  - **The fix: waking `accept()` never needed a handshake at all.** `stop()` now
    pokes the endpoint with a **bounded raw connect** (`_wake_accept()`: an
    `AF_UNIX` socket on POSIX, an `open()` of the named pipe on Windows) instead
    of an `mpc.Client`. A bare connect wakes the socket regardless of whether any
    thread is in `accept()`, and `_accept_loop` **already** exits on the raised
    handshake error — so the whole authenticated round-trip was doing nothing the
    teardown needed, while supplying the only way to block. Note this beats the
    three options this note used to suggest: closing the listener first does not
    reliably wake a blocked `accept()` on Linux (which is *why* the poke exists),
    and timing-out or threading the `mpc.Client` only bounds the hang instead of
    removing it.
  - ⚠️ **`WindowReportServer.stop()` already had this exact fix, comment and all**
    ("A bounded raw socket is used deliberately rather than an authed
    `mpc.Client`… would block `stop()` forever"). The lesson is about *search*,
    not design: the deadlock was diagnosed from a stack trace across three
    sessions while a sibling module in the same package carried the remedy and
    the rationale in prose. **When a bug is found in one of the servers, grep the
    other two (`control_server` / `window_report_server` / `browser_report_server`)
    for the same shape before designing anything.**
  - **Measured, so don't re-litigate the rate:** 5/5 clean runs on the fix vs a
    stall on run 3 of 3 on `main` (~35 s each, 1417 tests). The regression test is
    `tests/server/control_server_test.py::StopDoesNotDeadlockTest`, which forces
    the accept thread out *without* `stop()` and then asserts `stop()` returns —
    i.e. it pins the race, not the symptom, and it fails against the old
    implementation.
- **Single-key keymap write**: the firmware supports `ID_DYNAMIC_KEYMAP_SET_KEYCODE` (0x05) — payload is `[layer, row, col, keycode_hi, keycode_lo]`. No need to write a full layer; `PolyKybd.set_dynamic_keycode()` wraps this.
- **Firmware update survives protocol mismatches**: `PolyHost.device_present` tracks "a device answers protocol-independent queries (GET_ID/GET_LANG)" separately from `connected` (protocol/version compatible). The flash/apply/bootloader actions and the release-update flow gate on `_fw_actions_allowed()` (present, not paused) — NOT on `connected` — so a keyboard on a mismatched protocol can always be updated (`CommandsSubMenu.update_enabled` re-enables exactly those items when the rest of the menu is greyed out). The HID flash protocol (`hid_fw_up`) is dispatched independently of `PROTOCOL_VERSION` in the firmware. Don't re-gate any firmware-update path on `self.connected`.
- **Autostart** (`polyhost/services/add_to_startup.py`): `setup_autostart_for_app()` registers the app to start at login (called from `main_app.py` unless `--portable`).
  - **Windows**: prefers a per-user, **non-elevated logon scheduled task** (`RunLevel Limited` / `LogonType Interactive`, via PowerShell `Register-ScheduledTask`) — needs no admin/UAC and starts earlier than the Startup folder, which Explorer throttles. The task launches the **proven venv-activating `.bat` wrapper** (`create_windows_bat_wrapper`); do **not** swap this for a direct `pythonw -m polyhost` call — running the venv interpreter without activation drops the `Scripts` dir from `PATH` and the app dies silently (regressed once, see git history). The `.bat` is run **windowless** through `wscript.exe` + a hidden-launch `.vbs` (`create_windows_hidden_vbs`, window style 0) so no console flashes. Falls back to a Startup-folder shortcut if task creation is refused (locked-down Task Scheduler). Gotchas learned the hard way: `New-ScheduledTaskAction -Argument ''` is rejected — only pass `-Argument` when non-empty; and f-strings with backslashes in the expression part break on Python < 3.12.
  - **Linux**: `.desktop` autostart entry; **macOS**: `launchd` plist.
  - ⚠️ **The generated launchers live in `add_to_startup.launcher_dir()` (the
    platformdirs user config dir, beside `settings.yaml`) — NOT in the checkout.**
    They used to be `polyhost/start_polyhost.{bat,vbs,sh}` under a `.gitignore`
    entry, so **`git clean -xdf` deleted the exact file the registered logon task
    points at** and autostart silently stopped working: the task still reads
    `State: Ready` / `LastTaskResult: 0` and starts nothing at the next logon
    (field, 2026-08-05, on a repo that gets cleaned and branch-switched a lot).
    Nothing can detect it after the fact either — the only process that could
    report the breakage regenerates the launcher on its way up, so the broken
    window is exactly "cleaned, and not started since". The scripts carry absolute
    paths to the venv and repo root, so their own location is irrelevant to how
    they work. A launch on the new code re-registers the entry at the new path and
    deletes the in-checkout leftovers (`_remove_legacy_launchers`).
  - ⚠️ **Every relaunch in the update chain must be spawned DETACHED — on Windows a
    plain `Popen` is how the app "doesn't start up again after the update".** Three
    sites relaunch after a self-update: `updater.restart_app()`, the generated
    locked-file relay script (`_write_relay_script`), and the daemon's relay spawn
    (`headless._restart_if_requested`) — all three used a bare
    `Popen(..., close_fds=False)` (fixed 2026-08-05; the GUI's own relay spawn and
    `daemon_launch.spawn_headless_daemon` were already correct). Without
    `DETACHED_PROCESS` Windows does one of two things, both fatal: it hands the child
    the **exiting parent's console** (closing that window sends CTRL_CLOSE and kills
    the freshly restarted app — the same "console opens, closing it drops the
    connection" failure `create_windows_bat_wrapper` avoids with `pythonw`), or —
    when the parent has *no* console, which the detached daemon does not — it
    allocates a **brand-new console window** for the child. In daemon mode that is
    the whole chain: daemon → relay (new console) → restarted daemon (inherits it),
    while the GUI's own relaunch inherits the old GUI's console. One closed window
    then takes down the daemon *and* the tray, and `probe_existing` reads `stale` at
    the next launch. Use `updater.detached_popen_kwargs()` /
    `detached_creationflags()` (`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`, stdio
    on DEVNULL) for anything that must outlive the process spawning it.
  - **Detaching the console does NOT escape a job object — `spawn_detached()` also
    tries `CREATE_BREAKAWAY_FROM_JOB`.** A VS Code debug session (and some
    terminals) launch the app into a job and tear the whole job down when the
    session ends; job membership is inherited, so a detached child still dies with
    it. A job that forbids breakaway fails the spawn with `ERROR_ACCESS_DENIED`
    (WinError 5), so it falls back to the plain detached spawn — never "no relaunch
    at all". Outside a job the flag is ignored, so the ordinary autostart/tray path
    is unaffected.
  - **A relaunch inherits `sys.executable` forever, so it must be normalised to
    `pythonw.exe`** (`updater.relaunch_executable()`): one session started from a
    terminal (`python -m polyhost`) used to make *every* subsequent post-update
    restart console-owning, long after the autostart `.bat` (which correctly calls
    `pythonw`) was out of the picture. The 2026-08-05 field log shows exactly that —
    `Restarting: ['…\\Scripts\\python.exe', '-m', 'polyhost', …]`.
  - **The relay script logs to `startup_log.txt`**: it runs detached with stdio on
    DEVNULL, so its old `print(..., file=sys.stderr)` on a failed DLL copy went
    nowhere. It is the last step of an update — a silent failure there reads as "the
    app never came back" with no evidence at all.
  - **`updater.preflight()` runs at the top of `UpdateInstaller.run()`** — the one
    choke point the tray, the daemon (`PolyCore.install_update`) and `polyctl update
    install` all pass through. It checks the *copy* (install dir + temp dir writable,
    both `blocking`) **and the restart** (the relaunch interpreter, the autostart
    entry, both warnings): an update that copies perfectly and then can't relaunch is
    indistinguishable from "the app never came back", except that by then the tree is
    already rewritten. A blocker aborts **before the download**, so nothing has
    changed; warnings are logged *and* emitted as `update_progress` lines so they
    reach the tray dialog and the CLI, not just the log.
  - `get_autostart_status()` reports which mechanism is in place (printed at startup); `remove_autostart()` tears all of them down. `--portable` removes any existing entry rather than just skipping registration.
  - ⚠️ **The Windows task is named `PolyHost` (`APP_NAME`), NOT `PolyKybdHost`** — so
    `Get-ScheduledTask -TaskName PolyKybdHost*` returns nothing on a perfectly healthy
    install and reads as "autostart is gone" (field, 2026-08-05). The check is
    `Get-ScheduledTask -TaskName PolyHost` / `schtasks /query /tn PolyHost`
    (`windows_task_exists`), with `Get-ScheduledTaskInfo -TaskName PolyHost` for
    `LastRunTime`/`LastTaskResult`. Same name for the Startup-folder `.lnk` and the
    Start-menu launcher.
  - `_install_windows_autostart` **verifies the task by querying it back** before
    reporting `"scheduled task (at logon)"`; that string is what the startup log
    prints, and a PowerShell exit code only says `Register-ScheduledTask` didn't
    raise. A "registered" task that isn't queryable now falls back to the
    Startup-folder shortcut instead of leaving no autostart at all.
- **Layout dialog** (`polyhost/gui/layout_dialog/`): fully implemented — layer switching re-renders all key labels from the cached buffer; clicking a key then selecting from the browser writes immediately to the device via `set_dynamic_keycode()` and keeps the local buffer in sync. `RenderableKey` carries `matrix_index` for row/col derivation.

## Releases

Host releases are **GitHub Releases** (tag `vX.Y.Z`; version in `polyhost/_version.py`),
created by **publishing** — *not* by pushing a tag. Use the `polykybd-github-release`
skill to draft the notes and drive the flow. Mechanics (learned 2026-07):

- ⚠️ **The host and firmware version numbers were deliberately aligned at 0.11.0
  (2026-08-05) — and they are NOT kept in lockstep after that.** The two are
  independent lines, each bumped by `bump-version.yml` from the labels on its own
  merged PRs, so a host-only or firmware-only change immediately re-separates them.
  That drift is expected and is **not** a bug to "fix": the thing that genuinely
  must move together is `__protocol__` / `PROTOCOL_VERSION` (see the connect-gate
  note above), which is a different number entirely. Re-aligning the display
  versions is a cosmetic choice to make at a release, by landing a `bump:minor` PR
  that does **not** itself edit `_version.py` — the workflow bumps *after* merge, so
  an edited version file would be bumped on top of.

- **A pushed tag does NOT create a release.** Release tags land on the auto-bump
  `chore: … [skip ci]` commit (`bump-version.yml`), and `[skip ci]` suppresses the
  tag-push trigger — so `release.yml` runs on **`release: published`** (this workflow had
  in fact *never* run; host releases were always hand-created in the UI). No build assets
  (pure Python).
- **`scripts/publish_release.py`** — one OS-independent command (stdlib only, byte-identical
  to the qmk copy; it auto-detects the repo). It publishes the **newest prepared `<TAG>.md`
  on the `release-notes` branch** — the source of truth for what's ready, because the tree
  version drifts *ahead* (every PR merge auto-bumps it). `--dry-run`/`--tag`. It forces
  `encoding="utf-8"` on git output — on Windows the default cp1252 codec crashes on the
  emoji notes.
- **Crafted notes** live one-file-per-tag on the `release-notes` branch (`<TAG>.md`, first
  line `# <title>`, rest = body); `release.yml` applies them on `release: published` via
  `gh release edit`.
- **Version bump is label-driven**: the merged PR's `bump:major`/`bump:minor`/
  `bump:protocol` label (else patch) drives `bump-version.yml`. Bump `__protocol__` in
  lockstep with the firmware (see the connect-gate note above).
- ⚠️ **From Claude Code on the web you can neither push tags (git proxy 403 on
  `refs/tags/*`) nor create a release (no `gh`, no create-release MCP tool)** — stage the
  notes on the branch and hand the user `python scripts/publish_release.py`.

