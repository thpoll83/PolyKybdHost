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

- ⚠️ **A green board is NOT evidence a reviewer read your code, and every bot here
  has a way of going quiet that looks like a clean pass.** The standing check, in
  full, is `pull_request_read` `get_reviews` plus the summary comment's body:
  - a review counts only when its **`commit_id` equals the PR head sha** AND its
    **body is not a refusal notice** (a quota / diff-too-large refusal is a real
    review object carrying the head sha, so the sha alone reads as reviewed);
  - **and the absence of a review object proves nothing either** — a CLEAN
    CodeRabbit pass creates none, it edits its summary comment to say *"No
    actionable comments were generated"*. So read the summary body's `📥 Commits`
    range alongside `get_reviews`.
  - **No check run answers this question.** A green `Sourcery review` /
    `Greptile Review` / CodeRabbit status has accompanied a PR that nothing read,
    measured, more than once.
  **The full field guide — which bot goes quiet in which disguise, the sticky
  walkthrough, the Merge Risk sha, the false `✅ Addressed in <sha>` attribution,
  the quota shapes and the rate-limit arithmetic — is the `triage-pr-review`
  skill**, mirrored in both repos. Load it when you are actually triaging a PR;
  it is ~51 KB that does not belong in every session's context.

- **A reviewer's CONCLUSION can be sound while its EVIDENCE is invented — and the
  evidence is worth correcting separately.** The existing rule above says verify and
  decline the false ones. The 2026-08-23 round on PolyKybd#35 sharpened it: **3 of 4
  findings had a defensible conclusion resting on a claim that was simply not true of
  the repo.** (1) *"the netlist shows LED1 uses `WS2812B-Mini`/`C527089`"* — real
  identifiers, read out of a **2024 generated netlist** describing a design two board
  revisions old. (2) *"a later BOM exporter reading `MPN` will produce a wrong
  manufacturer id"* — there **is no `MPN` column** in the BOMs that repo generates; the
  exporter reads `Value`, which was already correct. (3) *"omits the standard footprint
  header"* — it had been added two commits earlier. Only the fourth (an exposed pad
  drawn 5× too tall) was right as stated, and that one was genuinely valuable.
  - **Take the conclusion when it stands on its own merits** — the stale-netlist finding
    led to a real improvement (a library footprint should not restate what the schematic
    instantiates) even though its evidence was junk. Say so explicitly: *"fixed, but for
    a different reason"*.
  - ⚠️ **Reply with the counter-evidence anyway, because CodeRabbit stores a learning
    from the thread.** It did: after being shown the 2024 timestamps and the BOM
    history it recorded *"`*.kicad_sch` files are the authoritative current schematic
    sources… do not use `poly_kb.net`, `poly_kb.xml`… these artifacts are stale"*. That
    is a durable repo-wide fix bought with one reply. Declining silently buys nothing.
  - ⚠️ **The mirror case: a finding can be right about the code and STILL wrong to
    fix, when the code's contract is parity with something else.** Greptile's #200
    finding was correct in every particular — `oled_preview.Renderer.bbox()`
    measures a substituted `'!'` for a missing glyph in a `HINT_SMALL` run while
    `draw()` skips it. Applying the one-line fix would have been wrong anyway: that
    asymmetry is the FIRMWARE's (`kdisp_gfx_text_bbox_in` substitutes with no
    `small` guard; `kdisp_write_gfx_char_half` returns 0), and the module exists to
    mirror the C, not to be internally consistent. "Verify the finding" is not
    enough here — the finding verified fine; what needed checking was whether the
    **remedy** violated a contract the reviewer could not see.
    - **The response that leaves something behind is to pin BOTH halves as a
      test**, with the reasoning in the docstring, so the next reader (or the next
      bot) does not re-raise it — and to say on the thread where the real fix
      belongs. Declining without that just resets the clock.
    - ✅ **And that is what closed it: the real fix landed upstream (qmk#252,
      2026-09-01), so the pin has been INVERTED here.** `Renderer.bbox()` now skips
      an unresolvable glyph in a `HINT_SMALL` run instead of substituting `'!'`,
      matching `kdisp_gfx_text_bbox_in`; the test that pinned the old behaviour is
      `test_small_skips_a_missing_glyph_instead_of_substituting_bang`, ported from
      the C's own new case. **The lesson is unchanged and this is its payoff** —
      declining a correct finding on parity grounds only holds while somebody
      carries it to the end the contract points at. ⚠️ It also means a parity pin
      is a LIABILITY the moment the other side moves: nothing here would have
      failed, so the divergence would simply have flipped direction in silence.
      When you pin one, name the upstream change that would invalidate it.

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

## Mirrored skills (`qmk_firmware` ↔ `PolyKybdHost`)

Six skills exist in **both** repos and are kept **byte-identical**:
`add-gated-hid-command`, `mutation-test-suite`, `polykybd-github-release`,
`session-retro`, `triage-pr-review`, `update-polykybd-docs`. A skill loads only from the repos a session has attached,
so one that describes cross-repo work is unreachable from a session opened on the
other repo alone — which is what happened to `mutation-test-suite`, extended to
cover Python/unittest suites while living only in the firmware repo.

⚠️ **They had already drifted, and every difference was pure loss — not repo-specific
tailoring.** Measured 2026-09-07 before harmonising: `session-retro` lacked the whole
open-PR-sweep section on the host side, `update-polykybd-docs` lacked its Images
section there, and `polykybd-github-release` was missing the shallow-clone warning on
the host side and the corrected WinCompose `status.txt` ordering on the firmware side —
i.e. each copy was the newer one for a different note. Nothing anywhere flagged it,
because a skill has no build, no test and no reviewer.

**So the rule is copy, never fork**: edit one, `cp` it to the other, and check with

```bash
for s in add-gated-hid-command mutation-test-suite polykybd-github-release session-retro triage-pr-review update-polykybd-docs; do
    cmp -s /home/user/qmk_firmware/.claude/skills/$s/SKILL.md \
           /home/user/PolyKybdHost/.claude/skills/$s/SKILL.md \
      && echo "$s: ok" || echo "$s: DRIFTED"
done
```

A firmware-specific section in the host's copy (or the reverse) costs a reader one
skipped paragraph; a fork costs a note that only one repo ever sees. Take the first.
If a skill ever genuinely needs to differ per repo, split the differing part into a
separate skill rather than forking the shared one.

## Branching (all PolyKybd repos)

- **Give every branch a name that hints at its content.** When creating a branch, append a short, descriptive slug describing the change (e.g. `claude/fix-firmware-update-menu-daemon-mode`, not just the auto-generated `claude/<random-scientist>-<id>`). The random scientist/id suffix from Claude Code on the web is auto-assigned server-side and can't always be overridden mid-session, but whenever a branch name is chosen by us, make it self-explanatory so the branch list reads as a changelog.
- **Always start new work on a FRESH branch cut from the updated default branch — never keep committing to a branch whose PR has already merged.** Once a PR is merged, that branch is done: `git fetch origin <default>` (and for the next piece of work `git checkout -b claude/<new-slug> origin/<default>`). Cherry-pick only the still-unmerged commits onto the fresh branch if needed. This keeps each PR a clean, focused diff against the current default (`main` for host/rig, `PolyKybd` for the firmware) and avoids a new PR accidentally re-including already-merged commits.
  - ⚠️ **Violating this is INVISIBLE — a push to a branch whose PR has already
    merged SUCCEEDS and orphans the commit.** git reports an ordinary fast-forward,
    GitHub shows nothing (a merged PR does not reopen, update, or list the new
    commit), and the work is simply not in `main` and not in any PR. It is easy to
    hit without meaning to: the window is "the PR merged while you were still
    working", not "you deliberately reused an old branch" — that is exactly how
    the CLAUDE.md commit from #168 was stranded (2026-08-17, recovered as #171).
    The one check, worth running before reporting any push as done:
    `git merge-base --is-ancestor <sha> origin/main` (and `git log --oneline
    --merges -5 origin/main` to see whether your PR's merge already went in).
    Recovery is the restart above: `git checkout -B <branch> origin/<default>`,
    cherry-pick the orphan, `git push --force-with-lease`, open a NEW PR — expect
    an add/add conflict if another PR touched the same region meanwhile.
- ⚠️ **A CLAUDE.md conflict is one of TWO kinds, and telling them apart matters —
  the second one deletes your work silently if you resolve it the usual way.**
  This file is append-heavy and every branch adds notes at the same anchors, so
  conflicts here are routine (two in 90 minutes on 2026-08-18):
  - **Addition beside addition** — main and your branch each inserted a new note
    at the same anchor. Keep BOTH; put main's first so the diff against main
    stays minimal.
  - **Supersession** — main's PR *implemented* something and rewrote the note
    that said it was impossible (`Browser-URL matching is LOCAL-ONLY` → `…DOES
    cross machines`, #173). Main's version wins **outright**; keeping both ships
    a file that contradicts itself. Verify you contributed nothing to that region
    first — `git show <base>:CLAUDE.md | grep -c "<phrase>"` against your branch
    proves it is inherited, not yours.
  - ⚠️ **After resolving, grep each of your notes back by name.** Taking one side
    wholesale also deletes anything of yours that merely *shared the conflict
    block* — git reports a clean merge, the file has no markers, and the loss is
    invisible. That happened on 2026-08-18: a supersession block also contained
    two unrelated new notes, and "take theirs" removed them. The check is
    `for pat in "<note phrase>" …; do grep -c "$pat" CLAUDE.md; done` — one line,
    and the only thing standing between you and silently dropped work.
    ⚠️ Grep **prose**, not a phrase containing markup: this file wraps identifiers
    in backticks, so a pattern typed as `crash_summary() puts the crash counts`
    scores 0 against a line reading ``` `crash_summary()` puts the crash counts ```
    — a false "note lost" scare mid-resolution (2026-08-18). Pick a distinctive
    run of plain words, or include the backticks.
  - ⚠️ **The same grep-back is the check for a SCRIPTED edit, not just a merge —
    and there it catches a different cause.** Editing this file with a
    `s.replace(anchor, new)` drops whatever sits between the two when the
    replacement does not repeat the anchor's opening lines verbatim: python does
    exactly what it was told, nothing errors, and the file reads fine because the
    surviving text still forms a sentence. That is how a line vanished on
    2026-09-01 — the anchor began *"bot) does not re-raise it…"* and the
    replacement began one line lower, so that clause was silently deleted from a
    note being extended, not rewritten. Assert the anchor count before writing
    (`assert s.count(anchor) == 1`), then grep each note back by name afterwards.
    The merge case and this one share nothing but the remedy, which is the reason
    to state it once for both.

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
- `polyhost/client/remote_core.py` — **`RemoteCore`** (H4a): the GUI-as-socket-client adapter. `python -m polyhost --connect[=ENDPOINT]` runs the tray GUI as a pure client of a core in another process — `RemoteCore` mirrors the subset of the `PolyCore` API `host.py` consumes, over the control socket (two connections: one for request/response, one for the event subscription), and re-emits server events to the same `subscribe`/`emit` seam. State is cached from `status.get` + `status_changed`. `PolyHost(client_mode=, endpoint=)` builds it instead of a `PolyCore`, renders from `status_changed` (not `apply_reconnect`), does the **client-side** OS-language switch. ⚠️ **This note used to say it "guards every device-coupled menu (cmd menu / layout editor / keyboard-firmware release / MRU debug)" — that is STALE and was believed while designing a feature around it (2026-08-27).** Those were progressively moved onto RPC and now work in client mode: the cmd menu is built unconditionally and its flash/apply paths route through `_client_flash_firmware` / `_client_apply_staged`, the keyboard-firmware release check is an ordinary Updates row, the settings dialog + "Flash firmware .bin…" go over `fw.flash`, and the **layout editor runs on `core.keymap_*`** — its own comment says *"works in either mode (H4a-2)"*. The only things still `if not self.client_mode:` are the two Developer tools that read the in-process `device_mgr` directly (**Inspect MRU Cache**, **Dump Mock Bitmaps**), plus the device-owning startup itself. **The rule to carry forward: a new device-coupled GUI surface is expected to work in client mode over RPC** — client mode is the default under daemon-by-default, so anything gated off it is unreachable out of the box. Quitting the client closes its sockets only — the daemon keeps running.
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

### Shared components (extracted duplication — reuse these, don't re-type them)

Five pieces of plumbing existed as two-or-more hand-written copies and are now
single implementations. Each was extracted because a copy had **already drifted**
or was one edit away from it, so reaching for the shared piece is the point:

- **`polyhost/server/mpc_listener.py` — `MpcListenerServer`.** The accept loop,
  per-connection reader thread, opening `hello` frame, JSON-RPC error mapping and
  the non-deadlocking `stop()` shared by `ControlServer` and `WindowReportServer`.
  Subclasses implement `dispatch(conn, req_id, method, params)` and may override
  `on_connection_added/_dropped`, `send` (the control server serializes writes per
  connection), `after_dispatch`, `secure_listener` and `wake_address`.
  ⚠️ **The surfaces stay separate — that separation is the security boundary.**
  The base carries no registry and no `PolyCore` reference; the network endpoint
  still serves exactly one method. This is the direct fix for the class of bug
  CLAUDE.md already documents ("grep the other two servers before designing
  anything"): the bounded-raw-connect `accept()` wake lived in one server and not
  the other, and its absence hung the suite intermittently for ~3 sessions.
  ⚠️ `wake_address()` exists because a wildcard `0.0.0.0` bind is **not
  connectable** — the window-report server overrides it to dial loopback, or
  `stop()` could never wake `accept()`.
- **`polyhost/gui/update_ui.py` — `UpdateProgressController`.** The self-update
  progress dialog handling shared by `PolyHost` and `PolyForwarder`
  (`on_progress` / `close` / `stage_relay`). It drives a **duck-typed** dialog, so
  each app keeps its own styling (the tray snaps to the tray corner) and the module
  stays Qt-free and unit-testable. `stage_relay` is the one correct relay spawn:
  `spawn_detached([relaunch_executable(), path])`. The forwarder's copy had drifted
  to a bare `Popen([sys.executable, …])` — both halves of that are the documented
  failure modes (an un-normalised interpreter leaves the restarted app owning a
  console; a bare `Popen` skips `CREATE_BREAKAWAY_FROM_JOB` and the DEVNULL stdio).
  `PolyHost._update_progress` is a **property** over the controller's dialog so the
  controller is the single owner and the two can't disagree about whether a dialog
  is up.
- **`polyhost/gui/theme.py` — `apply_theme(app, setting)` / `dark_palette()` /
  `light_palette()`.** The Fusion theme both `QApplication`s wear; they had a
  byte-identical 22-line `set_style`. It is an explicit palette (not a stylesheet)
  because the palette is what propagates into the stock
  `QMessageBox`/`QProgressDialog`/file pickers neither app styles by hand — and
  that is also why light is a second explicit palette rather than
  `standardPalette()`. `apply_dark_palette` survives for the dialogs' `main()` dev
  launchers; **an app calling it would ignore the desktop**, which is the bug the
  OS-theme note below replaced.
- **`polyhost/util/observable.py` — `Observable`.** The `subscribe`/`emit` seam
  `PolyCore` and `RemoteCore` both expose (and both duplicated). Two properties are
  load-bearing and easy to drop when re-typing: `emit` **snapshots under the lock
  and fires outside it** (an observer that subscribes another must not deadlock the
  core), and a **raising observer is caught, logged and left subscribed** — the
  emitting side is a worker thread, so an escaping exception doesn't fail an event,
  it kills the thread that owns the device.
- **`PolyCore._flash_resource` + `poly_core.flash_progress_relay`.** Every resource
  that rides the font-pack transport (`.plyf` bundle, doom `.whx`, doom `.plyx`)
  goes through `_flash_resource`; they differ only in the "cannot read" noun, the
  validator, how the engine is invoked and the event `kind`. `flash_progress_relay`
  builds the `(progress_cb, cancel_flag)` pair — ⚠️ `cancel_flag` is a **one-element
  list** because the engines poll it by reference between chunks, and the only thing
  that raises it is a progress callback observing the worker's cancel Event. Getting
  that wiring wrong fails **silently**: the flash just becomes uncancellable.
  ⚠️ The engines return **`(ok, msg, commit_status)`** and `_flash_resource` discards
  the status deliberately — only the multi-bundle pass (`_fontpack_flash_bundles_job`)
  acts on it, to tell a lost COMMIT acknowledgement apart from a real refusal and queue
  a retry; a single explicit flash has nothing to retry into. That arity is **mocked in
  every test**, so a change to it would leave the suite green while a real flash raises
  `ValueError` inside the worker job — `TestFlasherReturnArity` asserts it against the
  real functions for exactly that reason (it had to be corrected once already, when the
  engines grew the third element).

**Deliberately NOT extracted** (recorded so it isn't re-litigated): the
`FW_UP_BEGIN` / `FONTPACK_BEGIN` erase-poll loops in `hid_fw_up.py` and
`hid_fontpack.py` are structurally similar (~50 lines each, plus an identical
`_erasing` closure) but genuinely diverge — the font-pack side supports cancel and
returns a 3-tuple, the firmware side owns the `?`/`S` confirm-poll. That is the
most safety-critical path in the repo and cannot be verified without hardware, so
the duplication is the cheaper risk. Same for the two dialogs' `main()` dev
launchers.

### Configuration (`polyhost/settings.py`)
YAML config persisted to XDG config dir via `platformdirs`. Covers unicode composition mode, brightness/daylight settings (solar calculations via `pvlib`/`geocoder`), HID rate limits, and debug flags.

### Services (`polyhost/services/`)
- `unicode_cache.py` — pre-computed unicode character mappings
- `sunlight_helper.py` — adaptive brightness via solar irradiance
- `add_to_startup.py` — OS autostart registration (see Key notes below)

## Threading model (HID worker)

Since the HID-worker refactor (`docs/hid-worker-refactor.md`), the Qt main thread does **no device I/O** after `PolyHost.__init__` (the one synchronous `connect()` at startup — which seeds `device_present` for firmware-action gating — is the only exception). There is deliberately **no synchronous language enumeration at startup**: `self.connected` can only be set by the reconnect decision tree (that's where the protocol/version gate lives), so the first worker probe always sees a False→True transition and runs the full fresh-connect flow (enumerate + menu build + unicode mode + cache reset). A startup enumerate just duplicated all of it within the first second (double menu build, field 2026-06-13) — don't re-add one.

- `HidWorker` (`polyhost/device/hid_worker.py`) owns the device. Periodic tasks on the worker: reconnect probe (1 s), console/serial reads (250 ms), daylight brightness incl. its network lookups (10 min).
- UI code enqueues jobs (`worker.submit`); overlay sends use `coalesce_key="overlay"` so rapid app switches supersede/cancel stale transfers instead of replaying them. Dialogs use `worker.run_sync` (short bounded block; raises `RuntimeError` while suspended). Tray pause maps to `suspend()`/`resume()`, and `exclusive()` restores the prior suspend state on exit. ⚠️ **There are TWO flash paths and only one of them uses `exclusive()`** — see the console-starvation note below, which is what makes the distinction matter.
- ⚠️ **Nothing the firmware prints during a flash is observable from the host** — and
  this is not a logging-level problem, so don't go hunting for a switch. QMK *drops*
  console output that no one drains, and during a flash nobody does. ⚠️ **TWO flash
  paths reach that outcome by DIFFERENT mechanisms**, so don't reason from one to the
  other:
  - The **core job** path (`PolyCore.flash_firmware` / `flash_fontpack`, i.e. the
    daemon, `polyctl`, and the tray's RPC flash) runs the whole upload as **one long
    job on the HID worker** and deliberately takes **no `exclusive()`** — its docstring
    says so, since the worker's single thread already blocks the reconnect probe.
    `HidWorker._run()` runs due periodics only **between** jobs, so the 250 ms console
    read simply never gets a turn for the duration.
  - The **GUI dialog** path (`host.py` `_on_fw_download_done()`, and `cmd_menu.py`'s
    `_paused_polling()` context manager) *does* wrap in `worker.exclusive()`, because
    `HidFwUpDialog` stages chunks from **its own QThread** — nothing would otherwise
    stop the worker's periodics contending for the device while the keyboard
    re-enumerates. There `suspend()` sets the cancel flag on every periodic, the
    console read included.

  Either way the
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
    - ⚠️ **These host tests pin the contract from ONE side only, and it is the less
      useful side.** `tests/device/hid_fontpack_test.py` encodes the firmware's reply
      bytes as **fixtures** (`_commit_status_reply`), so it catches the *host*
      misreading a status — the opposite direction from the bug that actually shipped,
      which was the firmware *emitting* `!` for a dropped link ack. A fixture is not
      the firmware. The firmware end is now pinned too (qmk
      `make test:fw_up_verdict` → `FontpackCommitStatusTest`), so a change to either
      side that breaks the mapping fails a test somewhere. **When you touch these
      status values, update BOTH suites** — and prefer adding the firmware-side
      assertion first, since that is the end a host fixture can never police.
- **The font-pack INSPECT and EXTEND dialogs are
  [`docs/fontpack-tools.md`](docs/fontpack-tools.md)** — a viewer for every bundle
  glyph as the keycap draws it, and a builder for new glyphs from a TTF/OTF with
  pure-Python `fontconvert` parity. Both are reached from the tray's **Debugging**
  submenu, so they are developer-mode only; unlike the other Debugging entries they
  work in client mode too, since they need no device. Three things the pointer has
  to carry, because they are the ones that mislead from outside:
  - **The two dialogs split accumulate from build.** The *extend* dialog builds ONE
    glyph and previews it (OK / Cancel, nothing saved); the *inspector* owns the
    working copies, the pending-edit list and Save as…. Looking for a save in the
    editor finds nothing.
  - ⚠️ **A `.plyf` carries no bundle NAME** — the PlyF header has abi /
    `content_version` / `font_count` and a per-font global ALL_FONTS index, and the
    id lives in `bundles.json` and the filename. So an opened file is named after
    itself, and a glyph out of one is `<stem>#<gidx>`.
  - ⚠️ **Editing a glyph needs the render options the `.plyf` does not carry**, which
    is what `polyhost/res/fontpack/fontpack_render_settings.json` and
    `lang_flags.json` are for — both mirrored byte-identically from the firmware's
    generated copies. Keep them in sync (`cmp`); the editor silently pre-fills the
    wrong controls otherwise.
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
  - **Each menu entry PREVIEWS its script** (2026-09-07): the icon is a two-glyph
    sample and the tooltip a longer one, drawn offline from the shipped
    `fantasy.plyf` by `services/glyph_script_preview.py` (Qt-free) and turned into
    a `QIcon` by `gui/glyph_script_icon.py`. STANDARD previews the normal Latin
    face from `res/preview/resident.plyf`, so the column reads as a comparison.
    Built on the submenu's first `aboutToShow` (30 ms for all 11), never at
    startup; a missing or malformed bundle leaves the menu exactly as it was.
    Four things were decided by rendering the real menu
    (`tools/render_tray_menu.py`, which now calls `_build_glyph_script_previews()`
    for the same reason it calls `_refresh_fontpack_action()` — a `grab()` fires no
    `aboutToShow`):
    - ⚠️ **The icon is TWO glyphs because a menu icon is a ~16 px SQUARE.** `QIcon`
      scales a pixmap to *fit*, so the six-glyph sample arrives about five pixels
      tall and reads as a smudge. The tooltip carries the rest.
    - ⚠️ **A glyph is scaled against the ALPHABET's ink box, not its own.** Braille
      'a' is a single dot; measured against itself it fills the icon as a solid
      white square. `ink_extent()` over `a..z` keeps the dot a dot — and keeps
      every entry of one script at one scale whatever sample it draws.
    - **The script's font is found by BLOCK BASE, not by position in the pack.**
      `0xE800 + (value-1)*0x40`, mirroring the firmware's `glyph_script_blocks[]`
      (`tools/glyph_script_demo.py` assumes pack ORDER instead — weaker). A pack
      that reorders or lacks a block then yields no preview rather than a preview
      of the neighbouring script; the firmware table is pinned in
      `tests/services/glyph_script_preview_test.py`.
    - **The tooltip image rides in the HTML as a base64 `data:` URI** — Qt's rich
      text loads those, so there is no temp file to write or clean up. The test
      draws it through a `QTextDocument` and counts lit pixels, because a tooltip
      whose image Qt cannot load renders as an empty box and says nothing.
      ⚠️ `QMenu.setToolTipsVisible(True)` is required — action tooltips are off by
      default, so without it the whole tooltip half is a silent no-op.
- **Keycap legend size (protocol 13+)**: HID cmd 34 sets how large a key's MAIN
  legend is drawn — `GlyphSize.SMALL` (the original face), `MEDIUM`, `LARGE`. Wired
  exactly like the glyph script: `PolyKybd.get/set_glyph_size` behind a
  `"glyph_size"` `FEATURE_MIN_PROTOCOL` entry, `PolyCore`, `M_GLYPH_SIZE_GET/SET`,
  the `RemoteCore` mirror, `polyctl glyph-size`, and a **"Keycap Size"** tray
  submenu gated on `self.supports("glyph_size")`.
  - ⚠️ **`GlyphSize` is a CLOSED range and that is the ONE way it differs from
    `GlyphScript` — do not "simplify" it to match.** An unknown SCRIPT index is
    accepted by the firmware and degrades to the normal legend, which is what lets
    the host offer faces a keyboard lacks without a protocol bump. An unknown SIZE
    is NACKed, because it would otherwise persist as a setting that silently renders
    small. So never send a value outside the enum, and don't expect a newer keyboard
    to take one. `tests/device/poly_kybd_capabilities_test.py` pins the contrast.
  - The bigger faces ship in the **`latinbig`** bundle (auto-flashed on connect like
    every other). Latin only: a CJK/Arabic/Indic legend, or a keyboard without the
    bundle, keeps drawing small — so selecting a size is always safe and takes effect
    on its own once the bundle lands.
  - **`tools/glyph_size_preview.py`** renders and clip-checks the sizes straight from
    the FIRMWARE's generated headers, mirroring `plan_main_legend()` coordinate for
    coordinate. `--check` is the gate to re-run after any change to the firmware's
    `latinbig` entries; `--out` writes the contact sheet the docs page uses. Same
    caveat as `oled_preview.py`: it is a Python model of the C and can drift.
- ⚠️ **`tools/apply_tuner.py`'s export grammar CANNOT express the `caps` column** —
  its key-line regex is `base|shift|altgr`, matching what the keycap tuner emits, and
  the LUT's four sub-columns are lower/upper/**caps**/AltGr. A bulk edit that touches
  caps cells therefore cannot go through the CLI: **import the module and call its
  `set_cell()` / `str_cell()`** so the surgical `sheet2.xml` path (which preserves the
  other sheets' formula caches) is still the same tested code. ⚠️ Those two are only
  the XML edit — `set_cell()` RETURNS the modified sheet and persists nothing, so the
  caller still owns the language-column arithmetic (`base = 2 + langs.index(lang)*4`,
  `+0/1/2/3` for base/shift/caps/AltGr), rewriting the zip entry, and the `cog -r
  lang_lut.c` afterwards. The whole loop, with its verification steps, is the
  firmware repo's `tune-lang-lut-cells` skill; this note is only about which half
  the CLI cannot do. Hit on 2026-09-03,
  where 14 of the 117 cells drawing `§ £ ± µ` were caps. Widening the regex is a
  bigger change than it looks — the tuner never emits `caps`, so the grammar would
  gain an arm nothing exercises.
- **Macros (protocol 15+)**: HID cmds 36/37/38 behind ONE `"macros"`
  `FEATURE_MIN_PROTOCOL` entry — splitting the gate would let the editor load a list
  from a keyboard that cannot save it. `PolyKybd.get_macro_info` /
  `read_macro_buffer` / `write_macro_buffer` / `get_macro_label` / `set_macro_label`,
  then `PolyCore.macro_list/macro_set/macro_clear`, `M_MACRO_LIST/SET/CLEAR`, the
  `RemoteCore` mirror, `polyctl macro list|get|set|clear`, and a **Macros tab in the
  keycode browser** (`gui/layout_dialog/macro_tab.py`).
  - **A tab, not a window.** The browser is already a `QTabWidget` whose "Layers &&
    Mods" page BUILDS a keycode rather than listing a fixed set, so a macro page is the
    same shape — and it puts authoring and placement in one view. `KeycodeBrowser`
    takes `core=None`; without one the tab is simply absent, and the existing tabs are
    not reordered (pinned by a test, same invariant as the developer-menu one).
  - ⚠️ **`PolyCore.macro_*` is WHOLE-BUFFER on purpose.** The bodies are NUL-delimited
    in one shared buffer, so writing macro 3 means rewriting everything after it;
    read-modify-write is the only shape that cannot corrupt a neighbour. A label-only
    edit skips the body write entirely. The mock device is backed by a real `bytearray`
    rather than a dict of strings for exactly this reason — a per-macro mock could
    never show a neighbour being clobbered.
  - ⚠️ **The label meter is in PIXELS, not characters, and that is not a nicety.**
    `polyhost/services/macro_label.py` mirrors the firmware's
    `kdisp_gfx_text_bbox` for the single-font ASCII case a label always is. Measured
    against the committed `nano_font.h`: `'email'` 25 px, `'work mail'` 48,
    `'password'` 49, `'Hello World!'` 61, `'WWWWWWWW'` **exactly 72** — so the real
    budget is ~12 characters, 8 in the worst case, and a character count is wrong in
    both directions. It parses `nano_font.h` **directly** rather than through
    `load_all_fonts()`, which returns the `ALL_FONTS[]` priority list and deliberately
    excludes the three standalone UI faces (no codepoint can reach them — that is why
    the firmware draws a label through a single-font array).
  - **What a macro can type is keystrokes, not characters.** `macro_body.encode_text`
    REFUSES anything outside printable ASCII + tab/newline rather than dropping it: a
    macro that silently types less than you asked for is worse than one that refuses,
    because you find out when it matters. Accented letters and emoji belong on the
    language/emoji layers, and the docs page says so.
  - `tools/macro_label_preview.py --check` renders the keycap the way the firmware's
    `render_macro_key()` composes it and counts pixels outside the 72×40 window (320
    cells, 0 clipped) — the same "verify by rendering" rule as `glyph_size_preview.py`,
    with the same caveat that it is a Python model of the C and can drift.
  - ⚠️ **The macro ICON lookup (`macro_look.load_render_fonts`) UNIONS the firmware
    headers with the shipped `.plyf` bundles — it must not choose between them, and
    that is the OPPOSITE remedy from `preview_data.choose_source` one section below.**
    Both face the same hazard (a checkout beside this repo is a working tree at
    whatever branch it is on), but the pairs differ: there, two renderings of the SAME
    data, so the newer wins; here, the headers carry the resident half and the bundles
    are what the host actually flashes, and either can be ahead. Preferring the
    headers alone previewed the stale set — a slot's Mayan numeral drew as `M3`
    because `symbol.plyf` v9 ships that font while a clone on `PolyKybd` has no such
    header, and the keyboard drew it perfectly well (field, 2026-09-08). The union is
    safe by construction: `find_glyph` stops at the first font covering the codepoint,
    so appending can only ADD hits. **It fixes the icon PICKER for the same reason** —
    it enumerates candidates from the bundles and then looks each one up, so a glyph
    the headers lacked was dropped from the grid and could not be chosen at all.
    ⚠️ The `(no glyph)` warning still rests on the source being `"headers"`, i.e. on
    the RESIDENT faces having been visible; keep that meaning if the value is reworked.
  - ✅ **The CAPTION half of that preview used to have no such fallback — `_Small_`
    was NOT in `res/preview/ui_fonts.plyf` (it shipped `_Nano_` and `_Mid_` only), so
    `load_caption_faces()` needed a firmware checkout. FIXED by exporting the third
    face**, which is what this note already said the right answer was ("exporting the
    third face, not another fallback path"). It landed for a different consumer — the
    status-screen preview draws every row with it — which is the usual way a
    long-standing gap gets closed.
- **The keymap editor — key geometry, the case plate, the three preview modes and
  where the preview data comes from — is
  [`docs/layout-editor.md`](docs/layout-editor.md).** Read it before touching
  `gui/layout_dialog/`, `scripts/export_preview_data.py` or
  `scripts/export_board_outline.py`. Four things in it that are easy to get
  backwards from the code: the key geometry comes from the KLE
  (`polyhost/res/polykybd-split72.json`) and QMK's `layouts.*.layout` is **not** a
  second opinion on it (64 of the 74 keys disagree — it is a coarse grid carrying
  no column stagger and no thumb rotation at all, and the PCB is the authority);
  the plate outline is the **case** SVG, not `Edge.Cuts`; a legend using a display-
  list op `oled_preview.py` lacks is **refused**, so the key falls back to its
  keycode text, which looks exactly like the op not working; and the preview data
  ships with the host while a strictly-NEWER firmware checkout overrides it, so a
  stale export and a stale clone are different faults with the same symptom.
  - ⚠️ **`python tools/preview_doctor.py` is what answers "why is this preview
    wrong"** — host and firmware commits, the layer-enum diff, every layer key's
    resolved token, the brightness legend expressions. Three separate reports (a
    blank L5, missing emoji/Intl keys, the old moon brightness icons) were ONE
    stale clone, and two rounds were spent inferring which end was stale, wrongly.
    Ask for its output before theorising.
  - ⚠️ **A GENERATED file whose generator's INPUT PATH has died fails silently, and
    no `cmp` can catch it** — which is the difference from the mirrored files this
    repo already guards (`noto-fonts.yaml`, `iso_lang_country.py`, the six skills).
    A copy has a counterpart to compare against; a generated artifact has only the
    question *"does its generator still resolve its input"*, and nothing asks it.
    `layer_names.yaml` rotted through TWO renames that way and mislabelled the
    editor's layer tabs against an enum that no longer existed. **Run the generator
    — or the `cmp` — rather than trusting either kind of file.**
- **The brand mark (`p{color,gray,think,warn}.*`) is GENERATED — edit
  `tools/gen_brand_icons.py`, never the PNGs.** It draws a 6x6 keycap grid whose
  UNLIT keys spell a "P" in negative space, on a 1024-unit viewBox (the 64px
  original's proportions scaled up), and writes the whole set per variant: an SVG
  master, `p<v>.png` (256, the canonical file `add_to_startup` and the About dialog
  use), `p<v>@1024.png` for docs/store, the `p<v>_<n>.png` size ladder, `.ico` and
  `.icns`. Redesigned 2026-09-05 from a six-hue rainbow to one blue -> cyan sweep,
  with "HOST" stamped out of the bottom row's four rightmost keys.
  - **`get_icon()` feeds QIcon the LADDER, not the 256 master.** The mark is hard-
    edged squares, so Qt smoothly downscaling 256 -> 16 for a tray blurs exactly the
    thing that carries the shape. `BrandMarkTest` (tests/gui/icon_assets_test.py)
    asserts the set is complete AND that each ladder PNG's pixels match its name —
    a ladder built by copying one file is as blurry as no ladder, and looks fine
    until it is on somebody else's taskbar.
  - ⚠️ **cairosvg does NOT honour `<mask>`** — the stamp is punched by redrawing the
    body fill over the key instead, which is why the body gradient is
    `gradientUnits="userSpaceOnUse"`: the punched pixels then match the body around
    them exactly. A mask renders as a silent no-op (the key just draws whole), so
    check the render, not the SVG source.
  - **The busy and warning states draw the RING ONLY** (`RING`, and the engraved
    ghosts are skipped there too), so the hourglass / warning triangle sits in
    cleared space instead of over a dimmed grid — which is also why neither
    carries a dimming overlay any more. The P goes with the inner keys; a
    transient state reads by its glyph, and the ring plus the HOST stamp still
    names the app. ⚠️ The triangle is STROKED, so its nominal width understates
    it by half the stroke on each side — an unshrunk one overlaps the ring keys.
  - ⚠️ **Whether the inner keys are cleared is counted in the SVG master, not in
    pixels** — the engraved ghosts are white at 5% opacity over the body, a
    couple of levels of difference, so a pixel threshold for them would be
    fragile in exactly the direction that matters.
    `test_the_state_variants_draw_the_RING_ONLY` counts `url(#keys)` and the
    ghost rects instead (25/11 for the full mark, 20/0 for the ring). The pixel
    test beside it answers a DIFFERENT question — that the glyph stays inside
    the cleared middle — and does NOT catch a variant that kept its inner keys;
    that gap was found by mutation-testing, not by reading the tests.
  - **The hourglass is a plain silhouette: two caps and ONE body path**, with a
    straight-sided `base` run (0.36 of the bulb height) under each cap before
    the taper starts — without it the shape reads as a bare bowtie. `wall`
    places the taper's control point between the axis and the bulb edge: ~0.53
    is a straight wall, below it bows inward (concave) and above it outward
    (convex); 0.32 ships. Drawing the bulbs as separate shapes leaves a gap at
    the neck that reads as broken glass, and it is filled shapes throughout,
    never strokes, because an outline fills in at 16 px and becomes a blob.
  - **The stamp is rendered only at 128 px and up** (`STAMP_MIN_SIZE`); the smaller
    renders come from an unstamped master, so a tray icon stays a clean grid instead
    of carrying four keys of mush. Measured: clean at 128+, legible at 96,
    unreadable at 64.
  - ⚠️ **Pillow's ICO writer SKIPS every requested size LARGER than the base image,
    silently.** Handing it the 16 px render first (natural, when the entries are
    rendered per size and iterated small-to-large) writes a **single-entry 16x16
    `.ico`** that Windows then upscales into a blur — no error, no warning, and the
    file opens fine. The base must be the LARGEST; the rest go in `append_images`.
    `test_every_ico_carries_the_whole_size_set` reads the ICONDIR count with
    `struct` so it needs no image library.
  - ⚠️ **Abutting rects leave a hairline seam once antialiased.** The stamp's pixel
    cells are inflated 6% so neighbours overlap; without it every letter shows faint
    grid lines through it at 1024.
  - The brand `.svg` files are excluded from the Material-Symbols format tests
    (`BRAND_SVG`): they are multi-layer generated artwork with many fills, not
    single-fill menu glyphs, and no `get_icon()` call names them.
  - **Downstream generators re-run from `pgray.png`** — `browser-extension/generate_icons.py`
    and `browser-extension/store/make_promo.py`. Run both after regenerating.

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
  - ⚠️ **A tint is drawn on BOTH theme grounds now, so a colour picked against
    one can vanish against the other — measured, the brightness family did.**
    The apps follow the OS light/dark setting (see the theme note below), and
    `#FFFF55` is 7.6:1 on the dark chrome (#505050) and **1.07:1 on the light
    one** (#F0F0F0): yellow on white, reported from the field 2026-09-07. It is
    `#B59D24` gold now (3.00 / 2.36), and the three other off-palette one-offs
    went with it — `sync_problem` was `#A96424`, 1.74:1 on DARK (the same fault
    the other way), and `delete` `#F19E39`; both adopted the palette colour
    their meaning already had. Every colour in the set now sits between 2.20:1
    and 3.22:1 on both grounds, and `IconContrastTest` holds a 2.0 floor.
    - ⚠️ **A ramp cannot be expressed in LIGHTNESS — that is what made the old
      one unfixable rather than merely wrong.** The four brightness entries were
      shades of one yellow (a paler `#F9DB78` for 1%), and a pale tint is the
      worst case of all on a light ground. The ramp is across the palette now:
      grey off, **amber** at 1%, gold at 50/100% (the Material glyphs carry the
      rest — fewer rays, outline vs filled), and **green** for "back to
      automatic", which is the palette's enabled/ok rather than a brightness
      level. So amber means caution *and* the dim end, and green means ok *and*
      automatic; the alternative was two more one-off colours, and the set only
      just stopped having those.
  - **Judge a candidate glyph by rendering and measuring it, not by its name.**
    Rasterise to a fixed canvas (`cairosvg` + PIL) and compare **ink coverage**
    and **glyph bounding height** against the set (baseline ≈19% ink, ≈34px tall
    on 48px). That is what caught both the opsz mismatch above and `abc` being
    only 12px tall — half the next smallest icon — which eyeballing the render
    had missed. The measurement also overruled three name-based picks: the
    `brightness_*` family is not a coherent ramp (the `backlight_*` family is),
    and `bedtime`/`bedtime_off` beat a sun for idle start/stop.
- ⚠️ **The WINDOW icon and the TASKBAR BUTTON icon are answered by different
  questions, and `setWindowIcon()` only answers the first.** Windows groups
  taskbar buttons by **AppUserModelID**, and a process that never sets one is
  identified by its host executable — `pythonw.exe` — so the button showed the
  **Python** icon while every title bar was correct (field, 2026-09-04: *"for
  all these dialogs the program icon is not shown in the task bar"*).
  - **It was never a missing icon**, which is why chasing `setWindowIcon` call
    sites finds nothing: `IconStateManager.__init__` runs `update()` with
    `dirty_flag` already set, so `QApplication.setWindowIcon` is called at
    startup and every dialog inherits a real `p*.png`. Four dialogs additionally
    override it with `pcolor.png`; that is cosmetic, not the fix.
  - **The Linux half had been solved all along, three lines away** —
    `QApplication.setDesktopFileName('PolyHost')` in `main_app.py`, commented
    *"important for XWayland icon matching"*, i.e. the same question with the
    same failure mode. `set_windows_app_id()` is its counterpart and sits in the
    same `if/elif`, so the two are read together.
  - ⚠️ **It must run BEFORE the first window exists** — a window keeps the
    identity it was born with — and it must never raise: this is cosmetic, and an
    exception there kills the tray before it appears. One call in `main_app`
    covers the **forwarder** too, which is the second tray app that otherwise
    gets forgotten.
  - ⚠️ **`WINDOWS_APP_ID` is STABLE, not a name to tidy.** Windows keys pinned
    buttons and jump lists off that string, so renaming it orphans a user's
    pinned icon. A test pins the literal for that reason.
  - **Not verifiable from this container** — the code path is `win32`-only, so
    the tests cover the wiring (asked for on Windows, nowhere else, a failure
    swallowed and logged) and hardware confirms the icon.
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
- **The unicode input method is WATCHED for the life of the core, and an
  ambiguous reading is applied WITHOUT being stored** (`PolyCore`
  `_start_wincompose_settle` / `_wincompose_settle_loop` / `_apply_unicode_mode`,
  firmware protocol 17). It used to be detected exactly once, in the post-connect
  flow — and at Windows logon autostart brings PolyKybdHost up **before**
  WinCompose, so `get_input_method()` found no `wincompose.exe`, pushed plain
  `Windows`, and the keyboard typed Alt+numpad sequences (which cannot produce an
  emoji) for the rest of the session. Nothing corrected it: the tray probe needs
  the user to open the menu and deliberately skipped its FIRST look, and a
  headless daemon has no tray at all. Field report 2026-09-08, and the firmware
  half of the same bug is in `qmk_firmware/CLAUDE.md` (cmd 20 called QMK's
  notification callback rather than the setter, so the legend moved and the mode
  did not). What is load-bearing:
  - ⚠️ **A plain-`Windows` reading is an ABSENCE, not an observation.** Every other
    reading is positive — the process is running, or the platform is not Windows.
    Just after logon, "no wincompose.exe" is equally consistent with "it has not
    started yet", which is the whole reason the watcher exists. So ambiguity does
    **not** decide whether to push, it decides whether the push is **stored**:
    the mode is applied VOLATILE (cmd 20 `data[3]`, protocol 17) — while WinCompose
    is absent, `Windows` genuinely IS how the keyboard should type — and re-asserted
    persistently on the first pass after the window closes. If WinCompose turns up
    first, the stored mode was never disturbed, and the firmware's
    `eeprom_update_byte` skips the write for a value it already holds. On firmware
    older than 17 there is no way to apply without storing, so the reading is
    **held** instead: the alternatives are a wrong stored value and a delay, and
    the delay is recoverable.
  - ⚠️ **The window is measured from the PROCESS start, not the connect.**
    WinCompose races the logon; it does not race a replug three hours later, where
    treating the reading as ambiguous would only postpone the re-assert that exists
    to catch a *different* keyboard being plugged in.
  - ⚠️ **The push dedupe is over (mode, persist), not the mode alone.** Re-asserting
    the same mode to make a volatile one stick is the entire point of the window
    closing; a mode-only dedupe swallows it and the keyboard loses the setting at
    the next power cycle. Mutation-checked.
  - ⚠️ **The watcher thread must never touch the device.** `_apply_unicode_mode`
    reads the CACHED protocol via `protocol_supports(self.keeb.protocol_version, …)`
    rather than `keeb.supports()`, which lazily calls `query_version_info()` — HID
    I/O, which belongs on the worker. Same reason the TASKLIST probe is on its own
    thread rather than a worker periodic: ~50 ms must not sit between the reconnect
    probe and the console read.
  - **The watch is permanent and bidirectional, with no deadline.** Stopping when
    WinCompose appears would catch a late start and never notice it being *quit*,
    which leaves the keyboard emitting compose sequences that produce nothing —
    and only the tray covered that, which a daemon does not have. 10 s probes for
    the first 10 minutes after a connect, then one a minute. A cut-off would just
    be another guess at how slow a logon can be.
  - **A mode counts as pushed only when the device confirms it** — `worker.submit`
    only QUEUES the command, so recording at submit time records a mode the device
    may never have taken (paused, mid-flash, unplugged) and the dedupe then
    suppresses the retry, which is the very failure the watcher exists to fix.
  - ⚠️ **`shutdown()` and `_start_wincompose_settle` share a lock plus a one-way
    flag**, or a reconnect landing concurrently clears the stop Event and starts a
    fresh watcher holding the core after its worker has stopped.
- **A settings change applies its device side effects through ONE core hook —
  `PolyCore.note_settings_changed(keys=None)`.** There are exactly two settings
  writers: `settings_set` (polyctl and the client-mode dialog) and the in-process
  settings dialog, which writes the file directly. The dialog already carried a
  hand-written "nudge the core" line for the daylight brightness, so a second side
  effect meant a second copy — and that is how enabling
  `unicode_send_composition_mode` mid-session came to do nothing at all until the
  next reconnect (the watcher is armed only in the post-connect flow, and only when
  the setting was already on). `keys=None` means "anything in the dialog may have
  changed", which is all a whole-file write knows. Add the side effect to the hook,
  never to a caller.
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
- ⚠️ **The telemetry collector CANNOT double as a problem-report backend — four
  independent reasons, and the last one is a feature.** The obvious idea when
  "Report a Problem" was designed (2026-08-18) was to POST the report to the
  Cloudflare Worker that already exists. It doesn't fit, and each obstacle would
  have to be removed separately: the Worker caps a request body at **8 KB** (a
  description plus diagnostics blows past it, let alone logs); the D1 schema is
  `UNIQUE(install_id, day)` and upserts, so a **second report the same day
  overwrites the first** — exactly when a user is retrying because it broke
  again; the payload is an **allow-list rebuilt server-side** (`PAYLOAD_KEYS`,
  frozen by a test *designed* to make widening fail loudly), so free text can only
  arrive by deliberately undoing that guarantee; and the Worker is **write-only by
  design — there is no read route**, which is precisely what makes the dataset
  unleakable, so retrieval would mean building the route the design exists to
  avoid, plus auth *inside* the Worker (Cloudflare Access is zone-scoped and
  unavailable on `workers.dev` — see the note above). Hence the shipped design is
  a **pre-filled GitHub issue** with the bundle attached by the reporter: no
  backend, no new data store, and the user sees what they send. Don't re-propose
  the Worker without answering all four.
- **Logs, crash reporting and the guided problem report are
  [`docs/diagnostics.md`](docs/diagnostics.md)** — the Qt-free `log_bundle` service
  and its three front ends (tray, log viewer, `polyctl logs`), the pre-filled GitHub
  issue, and the modeless dialog a firmware `crash:` console line raises. Five
  things stay here because they bind code outside that subsystem:
  - ⚠️ **A NEW LOG FILE reaches nobody unless `LOG_SOURCES` knows about it.** That
    one declaration (filename, viewer tab title, whether it is time-sliced) replaced
    **four** hand-kept lists — `log_bundle.py` plus a `log_files` dict in `host.py`
    *and* in `forwarder.py`, which is a second tray app with its own viewer — and
    they had already drifted: `crash_log.txt`, the file whose whole purpose is
    proving whether the app crashed, shipped into **none** of them. Registering is
    only half: check the file's lines carry a sliceable `[YYYY-MM-DD HH:MM:SS,mmm]`
    prefix, because `slice_lines` starts `keep = False` and silently drops a whole
    file that has none.
  - ⚠️ **Never rotate, delete or `os.replace` `crash_log.txt`** — `faulthandler`
    holds the file DESCRIPTOR, so a rename leaves the live process dumping into a
    file nobody reads and eventually into a deleted inode, silently. It is bounded
    by an in-place trim before the fd exists, and cleared by TRUNCATION, which is
    safe only because every writer opens with `"a"` (**O_APPEND**).
  - **Redaction defaults ON for a report and OFF for "Collect logs…", deliberately** —
    a local bundle is a file you inspect before sending, a report is aimed at a
    public tracker. Same data, different destination, so the safe default flips.
  - ⚠️ **`polyctl logs` must work with NO host running** — it is routed before
    `connect()`, because the moment a user most needs the logs is the one where the
    app failed to start or the daemon died.
  - ⚠️ **"The tray icon is gone" is NOT "the app crashed"** — check the process list
    first (and read it in PAIRS; each launch showed two `pythonw.exe`). Under
    daemon-by-default the daemon still owns the device and keeps switching overlays
    with no GUI attached, which is exactly why nothing looks broken.
- **Multi-machine forwarding fails SILENTLY in three different ways, and NONE of
  them is diagnosable from the forwarder's own log.** All three were hit on one
  setup that had worked for weeks (field, 2026-08-17); the forwarder log showed
  nothing but a repeating error with no cause in it. Check these before reading
  any code:
  - ⚠️ **A disabled relay reads as `Connection timed out`, NOT "connection
    refused"** — so the log looks like a network problem rather than a host that
    isn't listening. A closed port would RST, but the keyboard machine's firewall
    silently drops SYNs to a port nothing has bound, and the old allow-rule went
    away with the listener. The *cause* is logged once, on the **other machine**,
    by `RemoteHandler.listen_to_forwarder` ("Remote overlay entries are configured
    but the legacy plaintext window relay (TCP 50162) is disabled") — and only
    when remote entries are mapped and `window_report_network_enabled` is off. In
    daemon mode that line is in `daemon_log.txt`, not the tray log.
  - ⚠️ **`WindowReportServer` is started ONLY by `HeadlessHost`** (`headless.py`
    `_maybe_start_window_report_server` is its one construction site — `host.py`
    has none). So under `--no-daemon`, `window_report_network_enabled` is a
    **silent no-op**: the setting reads back true and nothing listens.
  - ⚠️ **A forwarded window is used only while the keyboard machine's OWN focused
    window is a `remote: true` mapping entry** (`active_window.py`
    `is_remote_mapping_entry`, the `elif` in the window tick) — normally the
    remote-desktop client you are viewing the other machine through (the shipped
    entry is `nxplayer`/NoMachine). Without such an entry both logs look perfectly
    healthy — the forwarder reports windows, the daemon receives them — and the
    keycaps simply never change.
  - The user-facing version of all three is the docs site's
    [Multi-Machine Setup](https://www.polykybd.org/using/multi-machine/) page
    (rewritten 2026-08-17, docs#51). ⚠️ **The relay gate that caused this shipped
    in 0.10.5 and the docs kept recommending the dead path for six weeks** — when
    you flip a transport off by default, move that page in the same change.
  - **Browser-URL matching DOES cross machines — but only over the authenticated
    RPC path** (`--report-rpc`; the forwarder gained this in 0.12.x). Three things
    had to be true at once, so if a `url:` / `urls-contains:` entry is not firing
    for a forwarded window, check them in this order: the forwarder runs its own
    loopback receiver for the extension (`handler/browser_url_source.BrowserUrlSource`,
    shared with `PolyCore` so the two roles cannot drift — the extension itself is
    unchanged and always POSTed to `127.0.0.1` on its own machine); the report
    carries the optional `url` param (**RPC only**); and `RemoteHandler._match_remote`
    passes it to the matcher. ⚠️ **The legacy plaintext relay deliberately does NOT
    carry the URL**: its framing is positional `handle;name;title;os` with the
    free-text field in the *middle*, so a title containing `;` already truncates the
    title and kills the `os` field — a fifth field would deepen a live bug on a
    transport that is off by default. Two details that are easy to get backwards:
    a **None url is STORED** (unlike a None os, which is ignored — the OS belongs to
    the sending machine, a URL to the window in that report, so keeping the last one
    would pin a stale site's overlay onto the next non-browser window); and the URL
    is **part of the window's identity on both ends**, because an SPA route change
    moves neither handle nor title — the forwarder re-sends on a URL change rather
    than waiting out its 15 s heartbeat, and `remote_changed` re-matches.
- ⚠️ **The FORWARDER is a second tray app, and it is easy to forget.**
  `polyhost/forwarder.py` (`PolyForwarder`) has its own `QApplication`, its own
  menu and its own `forwarder_log.txt` — so a user-facing tray feature added to
  `host.py` is simply **absent** there until wired separately. It matters most
  for support features: the forwarder runs on a **different machine** from the
  keyboard, so its logs can never appear in a bundle collected host-side, and
  its failure domain (which window backend that desktop selects, the report
  transport, the authkey) is exactly the log-diagnosable kind. Both "Report a
  Problem…" and "Collect logs…" are wired in both places, and the forwarder
  supplies its **own** diagnostics text leading with `FORWARDER mode (no keyboard
  attached to this machine)` — the plain version line otherwise reads exactly
  like a report from the keyboard machine, which is a different failure domain
  entirely. `tests/gui/host_client_test.py` has a `forwarder` smoke mode; it
  **skips** without `pywinctl`, which `forwarder.py` imports at module load.
- **Both tray apps FOLLOW THE OS light/dark setting (2026-09-07) —
  `services/os_theme.py` (Qt-free reader + rule) + `gui/theme.apply_theme`.**
  They wore the dark palette unconditionally, so a light Windows desktop got a
  dark tray menu and dark dialogs against light windows (field). `ui_theme`
  ('auto' default, or 'light'/'dark') overrides the desktop; the settings dialog
  renders it as a **dropdown** via `settings_dialog.CHOICES`, the one place a
  fixed value set gets a combo instead of the free-text fallback.
  - **Detection is per platform and never raises**: Windows reads
    `AppsUseLightTheme` (the APP one — `SystemUsesLightTheme` is the
    taskbar/Start colour and can differ) with `winreg`, macOS `defaults read -g
    AppleInterfaceStyle` (⚠️ the key only EXISTS in dark mode, so a failed read
    means light), Linux `gsettings` `color-scheme` then the gtk-theme name. A
    desktop that does not answer reports None and `resolve_theme` falls back to
    **dark** — the historical look, so a failed detection changes nothing rather
    than flipping somebody's tray.
  - ⚠️ **The STYLE stays Fusion in both themes; only the palette changes.** Qt 5's
    native Windows style has no dark mode, so dark must be Fusion, and switching
    style by theme would make the app look like two different programs depending
    on a system setting — with the Fusion-shaped bits (`cmd_menu`'s proxy style,
    the inspectors) only ever checked in one of them. This follows the OS's
    light/dark CHOICE, not the platform's native chrome.
  - **The tray re-follows on `menu.aboutToShow`** (`PolyHost._refresh_theme`), so
    switching the desktop needs no restart; the detection is cached 5 s because on
    macOS/Linux it is a subprocess. The **forwarder reads it once at startup** — it
    has no such hook, and its dialogs are short-lived.
  - ⚠️ **A rendered pixmap does NOT follow a palette change, so the glyph-script
    previews are dropped and rebuilt** — their ink is picked from the palette
    (`glyph_script_icon.preview_ink`: the OLED cool white on dark, the palette's
    own text colour on light), and near-white ink on a light menu is an invisible
    icon.
  - ⚠️ **Some developer dialogs hardcode dark colours** (`mru_inspector_dialog`,
    `fontpack_inspector_dialog`, `fontpack_extend_dialog`) — mostly around OLED
    previews, where a black ground is the content rather than chrome. Left alone
    deliberately; every surface a normal user sees draws from the palette.
  - **Verified by rendering the real menu in both themes**
    (`ui_theme` in `settings.yaml` + `tools/render_tray_menu.py`), which is also
    what showed the Material menu icons read on white — they are mid-tone.
  - ⚠️ **A Linux tray menu can look light while the app palette is dark, and that
    is NOT evidence the palette applied** — reported from a Linux desktop while the
    apps were still unconditionally dark. The likely mechanism is that the menu is
    exported to the shell (StatusNotifier/DBusMenu) and drawn with the system
    theme rather than by Qt, but that is **unverified here**. The way to tell them
    apart is a real window: open Settings, which Qt certainly draws.
- **Linux HID permissions**: `polyhost/device/99-hid.rules` must be installed as a udev rule for non-root HID access.
- **Venv**: always use `PolyKybdHost/.venv/bin/python` — system `python3` lacks numpy, PyQt5, and other runtime deps. 
  - **Note on multiple venvs**: This project shares a workspace with `qmk_firmware/`. The QMK build uses a separate global venv (`~/.qmk_venv`) installed by the session setup script. The two venvs are **completely isolated and do not interfere** — each has its own Python executable and `site-packages`. When you activate `source .venv/bin/activate` in PolyKybdHost, it activates *this* project's venv; QMK commands via the global alias (e.g., `qmk compile`) still use the separate `~/.qmk_venv` and will not conflict with PolyKybdHost's dependencies.
  - **In a fresh remote/web container the `.venv` does not exist yet** — create it and install the test deps: `python3 -m venv .venv && .venv/bin/pip install numpy pyserial hid platformdirs pyyaml pillow`, plus the hidapi **system** libs `sudo apt-get install -y libhidapi-hidraw0 libhidapi-libusb0` (the `hid` module raises `ImportError: Unable to load any of the following libraries:libhidapi-*` without them). That set is enough to run the device/unit tests (`tests.device.*`); GUI tests additionally need an X server (see below).
  - **To run the WHOLE suite** (not just `tests.device.*` — do this after any change touching
    `core/`, `gui/`, or `cli/`) you also need `requests packaging pynput pvlib geocoder PyQt5 pywinctl`
    (pip) **and** `xvfb x11-xserver-utils` (apt), run under `xvfb-run -a .venv/bin/python -m
    unittest discover -s ./tests -p "*_test.py"`. Without those deps `services/updater`,
    `sunlight_helper`, `langcode_flag`, `win_helper_parse`, and the `host_client`
    GUI-subprocess tests **ERROR and masquerade as failures** — they are missing-dependency
    env failures, not regressions (confirm by `git stash` + re-running on the pristine tree).
    A fully green run prints `OK (skipped=N)` with the env-gated tests skipped, not errored.
  - ⚠️ **A missing dependency DELETES tests, and the `Ran N` line is the only thing
    that says so — the run still looks substantial.** A module that fails to import
    contributes exactly ONE error and ZERO tests, so 24 unimportable modules read as
    24 errors while quietly removing **465 tests**: measured 2026-09-09, the same tree
    ran **1982** tests with `hid`/`requests`/`pynput` absent and **2447** with them
    installed, `OK (skipped=60)`. The trap is that comparing a failure set against a
    baseline then confirms only that YOUR branch added nothing — both runs are missing
    the same 465 tests, so it comes back clean for a reason that has nothing to do with
    coverage, and the device/core half of the suite has never run against the branch at
    all. **Install the deps and read the count**; the failure list alone cannot tell a
    green suite from an absent one. Same rule as the appending-tests-after-`__main__`
    note, in the opposite direction.
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
- **RUN the real entry point once before believing a mocked suite — the output is
  where format bugs live.** Same instinct as rendering a widget or rasterising an
  icon above, applied to the CLI: a suite whose fixtures you wrote can only be as
  right as your idea of the real data. `crash_summary()` reported *"2 native fault
  dump(s)"* for a single crash, because a fatal signal prints **both** a
  `Fatal Python error` line and a `Current thread` line and the unit fixture had
  only the first. Every test passed; one `polyctl logs bundle` in a temp dir with
  a realistic file showed it immediately (2026-08-18). Cheap recipe: make a temp
  dir, write a realistic log, run the actual command, read the artifact —
  `cd /tmp/x && PYTHONPATH=<repo> <repo>/.venv/bin/python -m polyhost.cli.polyctl
  logs bundle --since 1h`, then unzip and look. It is ~30 s and it has now caught
  two bugs in one PR that the tests could not see.
- ⚠️ **`polyhost/forwarder.py` is UNTESTABLE in the documented environment — put
  any forwarder logic worth testing in a Qt-free module instead.** It imports
  `pywinctl` at module load (the backend selection at the top), and pywinctl is
  **not** in the full-suite dependency list above, so the module cannot even be
  imported in a normal test run — a `DISPLAY` is necessary but not sufficient.
  `PolyForwarder.__new__` (constructing the object without `QApplication.__init__`,
  to call one plain method) fails at the *import*, before Qt is reached. Hence the
  `--host-file` reconnect fix (2026-08-17) put the connection lifetime in
  `server/window_report_client.py` `WindowReportSession` — stdlib-only, 10 unit
  tests — and left only the two-line "no target ⇒ close" branch in the forwarder.
  A test gated on both `DISPLAY` and pywinctl would be permanently skipped, which
  is worse than none: it reads as coverage.
- **Test discovery**: test files follow `*_test.py` naming under `tests/` mirroring `polyhost/` structure. pytest is disabled in VS Code config; use `unittest`. New test packages require an `__init__.py`.
  - ⚠️ **`patch.object(Class, "method")` does NOT reach a fixture that already
    BOUND that method** — and the repo's own fixture idiom is what creates the
    trap. Several suites deliberately bind the real implementation onto a
    `SimpleNamespace` stand-in (`functools.partial(PolyCore._x, core)`, or a
    lambda) so the shipped bookkeeping is what runs; that partial captures the
    function object at fixture-build time, so a later `patch.object` on the class
    rebinds the attribute the partial no longer consults. The patch is a silent
    no-op and the test fails for a reason that has nothing to do with the code
    (2026-09-08, the volatile-mode re-assert test). Either drive the real input —
    for a time-based rule, move the clock (`core._started_at = time.monotonic() -
    601`) — or override the attribute **on the instance**, which is what the code
    actually calls.
  - ⚠️ **Appending test methods after a file's trailing `if __name__ ==
    "__main__":` block registers NOTHING, and the suite stays green.** The
    indented `def`s become part of the `if` body, so they parse, never run, and
    never appear as failures. Hit while adding 5 CLI tests (2026-08-20); the
    only tell was that the run reported **44 tests before and 44 after**.
    Generalise: after adding tests, check the **count changed**, not just that
    the suite is green — `python3 -m unittest ... 2>&1 | tail -3` prints it.
    Same family as the mocked-suite traps above: green is not evidence your new
    code ran.
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
  - ⚠️ **A mutation-test harness hits this on the RESTORE, where it corrupts the
    VERIFICATION rather than the fix** — the worse direction, because the natural
    reading is "my change broke something". Measured 2026-09-08: after three
    mutations of `macro_label.py`, `diff` reported the file byte-identical to the
    baseline while the suite still failed all three mutants' tests, the interpreter
    having loaded bytecode compiled from the last mutant. **Clear `__pycache__`
    after restoring, not only after editing**, then re-run — the confirmation run
    at the end of a mutation sweep is exactly where this lands.
- **No *test* CI**: no workflow runs the unit tests — but the repo is **not**
  CI-less, and this line said "two workflows" while there were four. They are
  `bump-version.yml` + `release.yml` (see **Releases** below), `deploy-telemetry.yml`
  (the Cloudflare Worker), and **`codeql.yml`, which analyses every PR** and is the
  one automated reviewer here that cannot go quiet — see the CodeQL note in the
  code-review conventions above. So a PR gets static analysis and no unit-test run;
  the suite is yours to run locally (`scripts/run_tests.py`).
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
    - **`tools/render_layout_editor.py` is the same trick for the LAYOUT EDITOR**,
      and the docs site's `using/keymap-editor` screenshots come out of it. It
      builds the real `KbLayoutDialog` against a fake core whose keymap is parsed
      from the FIRMWARE — the `LAYOUT_*` macro bodies zipped against
      `keyboard.json`'s matrix positions — so every key shows what the keyboard
      really has there. `--compare` additionally writes a Symbol/Preview/Real
      close-up.
      - ⚠️ **The layer TABS come from `layer_names.c`, not from `layers.h`.** A
        real editor draws `DYNAMIC_KEYMAP_UPDATE_MAX_LAYER_COUNT` (8) tabs named
        `Qwerty`/`ColemkDH`/`Fn`; the enum has 12 entries named `_L0`/`_ADDLANG1`.
        Rendering from the enum therefore produces a screenshot with four tabs too
        many that **contradicts the docs page describing the real names** — which
        is what the first cut did.
      - ⚠️ **`show()` it before the first `fitInView`, even offscreen.** An unshown
        widget has not laid out, so the view still reports its pre-resize size and
        the FIRST mode captured renders a postage-stamp keyboard in a full-size
        panel while every later one is correct. That reads as a mode-specific bug
        rather than a layout race.
      - ⚠️ **At board scale Preview and Real are indistinguishable** — a keycap
        lands in ~50 px, far too small for the OLED simulation's bloom and pixel
        grid to survive. Only a magnified CROP shows the difference, which is why
        `--compare` exists and why the docs figure is a close-up rather than three
        whole boards.
- **Use `scripts/run_tests.py` when a run might hang — it has a stall watchdog.**
  Twice on 2026-08-03 the suite wedged past a 200 s timeout with **no output at
  all** — and a bare `timeout` kill discards exactly the information you need. The
  runner arms `faulthandler.dump_traceback_later(..., exit=True)`, so a stall
  prints every thread's stack and fails the command:
  `python scripts/run_tests.py [--timeout 240] [-s tests/device]`.
  ⚠️ **Set `--timeout` BELOW whatever will kill the shell, or the dump is lost** —
  under a 120 s tool timeout an outer kill lands first: SIGTERM, exit 143, **no
  traceback**. Raise the Bash tool's own timeout past it (`timeout: 400000`).
  Redirect to a file (`> /tmp/tr.log 2>&1`) and read the whole thing; do **not**
  pipe it through `tail`, which has eaten the dump before.
  - ⚠️ **The suite is NOT ~25 s any more, and this note used to say it was — it is
    2354 tests and 65–90 s under xvfb, so the `--timeout 60` this file recommended
    now fires on a HEALTHY run.** Measured 2026-09-08 across three runs (65 s,
    75 s, 90 s) in the same container; the figure drifts with load, so treat 240 as
    the floor rather than tuning it down. Worse than a wasted run: at 60 s the dump
    lands wherever teardown happens to be, and on the run that produced this note
    that was the main thread in `PolyCore.shutdown` → `worker.run_sync` — i.e. an
    almost exact match for the `ControlServer.stop()` deadlock documented as FIXED
    below, complete with ~20 threads parked in `recv_message`. **A watchdog dump is
    only evidence of a stall if the run actually exceeded a realistic budget**;
    check the wall clock before reading the stack.
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

## Releases

Host releases are **GitHub Releases** (tag `vX.Y.Z`; version in `polyhost/_version.py`),
created by **publishing** — *not* by pushing a tag. Use the `polykybd-github-release`
skill to draft the notes and drive the flow. Mechanics (learned 2026-07):

- ⚠️ **A `PROTOCOL_VERSION` bump means BOTH artifacts get released, and the check that
  catches it is the PUBLISHED versions, not the in-tree ones.** The existing "bump
  `__protocol__` in lockstep with `PROTOCOL_VERSION`" rule is about the *sources*, and
  it can be perfectly satisfied while the releases are a protocol apart. Measured
  2026-09-09: firmware `PolyKybd` and host `main` both read protocol 17, while the
  newest **published** host (v0.14.18) was still 16 — so a firmware-only release would
  have shipped protocol 17 to every user's protocol-16 app. Read the sibling's newest
  release (`list_releases`, then its `__protocol__`/`PROTOCOL_VERSION` at that tag)
  before drafting.
  - ⚠️ **Nothing downstream catches it, because the connect gate is NOT exact-match.**
    The host connects to any protocol `>= MIN_SUPPORTED_PROTOCOL` and gates each
    feature through `FEATURE_MIN_PROTOCOL`, so an old host pairs with new firmware and
    silently leaves the new features off — quieter than a refusal, and worse to
    diagnose. (The release skill's own pitfall claimed exact-match for a long time,
    which made the pairing read as self-enforcing when it is not.)
  - **Publish the host first, then the firmware** — the host is the side that has to
    understand the new protocol, so that order never leaves a user holding firmware
    their app cannot drive.

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
  - ⚠️ **Set the label when the PR is OPENED (`issue_write`, `labels:`), never
    only ask for it in the body.** #212 (2026-09-04) asked for `bump:minor` in its
    body, was merged without it, and the label applied as the merge was happening
    landed 12 s too late — host went to **0.14.17**, not 0.15.0. Full note in
    `qmk_firmware/CLAUDE.md` § Releases ("Before the merge means AT OPEN").
- ⚠️ **From Claude Code on the web you can neither push tags (git proxy 403 on
  `refs/tags/*`) nor create a release (no `gh`, no create-release MCP tool)** — stage the
  notes on the branch and hand the user `python scripts/publish_release.py`.
  The same proxy also **403s on branch DELETION** (`git push origin --delete
  <branch>`, verified 2026-08-18), so a leftover branch has to be removed in the
  GitHub UI — don't burn retries on it, and don't create scratch branches you
  can't clean up.

