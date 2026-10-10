# CLAUDE.md — PolyKybdHost

This file provides guidance to Claude Code (claude.ai/code) when working in the **PolyKybdHost** repo (the Python host software).

For cross-repo context (how this repo relates to `qmk_firmware/` and `AdafruitGFX/`), see [`../CLAUDE.md`](../CLAUDE.md).

## Code review conventions (all PolyKybd repos)

- **Docstring coverage: ignore CodeRabbit's "Docstring Coverage … threshold 80%"
  pre-merge check.** That 80% target is a CodeRabbit default, **not** a project
  policy — the check is non-blocking and we deliberately do not chase it. Document
  new code where a docstring genuinely helps a reader, and no more.
- **Verify an AI reviewer's finding against the code before acting on it.** Several
  arrive confidently wrong, and a conclusion can be sound while its evidence is
  invented. The rule is **verify, not dismiss** — the same rounds that produced false
  findings also produced genuinely valuable ones. **Reply with the counter-evidence**
  rather than declining silently: CodeRabbit stores a repo learning from the thread,
  which is a durable fix bought with one reply.
- ⚠️ **A green board is NOT evidence a reviewer read your code.** Every bot here has a
  way of going quiet that looks like a clean pass: a quota refusal is a real review
  object carrying the head sha, and a CLEAN CodeRabbit pass creates no review object at
  all. Check `get_reviews` **and** the summary comment's `📥 Commits` range; no check
  run answers this question.
- ⚠️ **Raise a new LIMIT with the maintainer before writing it into code or docs**
  (maintainer's rule, 2026-10-09) — a cap, a bound, a ceiling, a size. A 48-icon cap
  per app came in with #240 with no measurement behind it and cut Kate's F1, F2 and
  Find in Files; a replacement guessed on the spot (512, then 1440) was the same
  mistake twice in one session. Say the number, what it counts and what it is
  measured against, and wait for an answer. Prefer a value the system already
  defines (the pool is `OVERLAY_POOL_CAPACITY`) to a new one.
- ⚠️ **Sourcery's `dangerous-subprocess-use-audit` needs a `# nosemgrep` marker plus a
  written audit, not contorted code** — and the marker applies to the line
  **immediately following** it, so putting it atop an explanatory comment block
  silently does nothing.

The full field guide — which bot goes quiet in which disguise, the sticky walkthrough,
the false `✅ Addressed in <sha>` attribution, the parity-pin case, and the worked
examples behind each rule above — is [`docs/review-conventions.md`](docs/review-conventions.md)
and the `triage-pr-review` skill.

## Mirrored skills (`qmk_firmware` ↔ `PolyKybdHost`)

Nine skills exist in **both** repos and are kept **byte-identical**:
`add-gated-hid-command`, `check-mirrored-artifacts`, `cross-repo-pr-sweep`,
`mutation-test-suite`, `polykybd-github-release`, `prune-claude-md`,
`session-retro`, `triage-pr-review`, `update-polykybd-docs`. A skill loads only from
the repos a session has attached, so one describing cross-repo work is unreachable
from a session opened on the other repo alone.

**The rule is copy, never fork**: edit one, `cp` it to the other, and check with

```bash
for s in add-gated-hid-command check-mirrored-artifacts cross-repo-pr-sweep \
         mutation-test-suite polykybd-github-release prune-claude-md \
         session-retro triage-pr-review update-polykybd-docs; do
    cmp -s /home/user/qmk_firmware/.claude/skills/$s/SKILL.md \
           /home/user/PolyKybdHost/.claude/skills/$s/SKILL.md \
      && echo "$s: ok" || echo "$s: DRIFTED"
done
```

⚠️ They had already drifted once, and **every difference was pure loss** — each copy
was the newer one for a different note. Nothing flagged it, because a skill has no
build, no test and no reviewer.

⚠️ **A shared `CLAUDE-SHARED.md` imported by both repos would NOT reduce context** —
imported files load at launch. What *does* reduce it, in increasing order: a
`docs/*.md` read on demand; a **path-scoped rule** (`.claude/rules/*.md` with `paths:`
frontmatter), which loads only when a matching file is read; and a **skill**, which
costs nothing until invoked. ⚠️ A path-scoped rule fires on the **Read tool**, not on
`cat`/`sed` through Bash — so it supplements a CLAUDE.md pointer, never replaces one.
The measurements behind all of this are in
[`docs/skills-and-context.md`](docs/skills-and-context.md).

## Branching (all PolyKybd repos)

- **Give every branch a name that hints at its content** — a short descriptive slug,
  so the branch list reads as a changelog.
- **Always start new work on a FRESH branch cut from the updated default** (`main`
  here, `PolyKybd` in the firmware). Once a PR is merged that branch is done.
  ⚠️ **Violating this is INVISIBLE**: a push to a merged branch succeeds and orphans
  the commit — git reports a fast-forward, GitHub shows nothing, and the work is in no
  PR. The one check, before reporting any push as done:
  `git merge-base --is-ancestor <sha> origin/main`.
- ⚠️ **A MERGE orphans work the same way, and the check above does not fire** —
  because you never pushed. Merge a stacked PR within a minute of its base and
  GitHub has not retargeted it yet, so it merges into the base's **branch**, which
  is itself already merged and closed: both PRs read "merged" and the second one's
  content is nowhere (2026-09-19, #244 at 15:37:09 and #245 at 15:37:17 — none of
  #245 reached `main`). So run the same ancestry check on a **merged PR's head**,
  and confirm by content (`git cat-file -e origin/main:<a file it added>`), before
  believing the badge. Merge the base, then **retarget the stacked PR yourself**
  (`update_pull_request base=main`) and merge it once `base.ref` reads `main`.
  ⚠️ Do not wait for GitHub to do it: it retargets only when the base BRANCH is
  deleted, and merged branches are kept here, so the wait never ends (#301 still
  read its merged base minutes after #300 merged, 2026-10-01). Recovery is the
  `re-land-orphaned-pr` skill — and
  it is a re-land, never a second merge, because by then the branch is stale
  enough that merging it reverts whatever landed in between.
- ⚠️ **A CLAUDE.md conflict is one of TWO kinds** — *addition beside addition* (keep
  both, main's first) or *supersession* (main's version wins outright, or you ship a
  file that contradicts itself). **After resolving, grep each of your notes back by
  name**: taking one side wholesale also deletes anything of yours that merely shared
  the conflict block, and git reports a clean merge. The same grep-back is the check
  after a **scripted** edit — assert the anchor count before writing, since a
  `s.replace(anchor, new)` silently drops whatever sits between the two.

Worked examples and the recovery procedures: [`docs/branching.md`](docs/branching.md).

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
# ⚠️ Use the RUNNER for a whole-suite run. `unittest discover -s ./tests`
#    prepends tests/ to sys.path, where tests/tools/ SHADOWS the repo's own
#    tools/, and reports 25 failures that do not exist — see the Tests section.
xvfb-run -a .venv/bin/python scripts/run_tests.py                     # all tests
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

**PolyKybdHost** is a PyQt5 system-tray application bridging the PolyKybd HID keyboard
to the host OS: it tracks the active window and sends overlay/keymap/language commands
over HID. The full file-by-file map — entry points, `PolyCore`, the control socket and
its three servers, `polyctl`, headless mode, `RemoteCore`, the device layer, the
platform input abstraction, the window handlers and the settings/services — is
[`docs/architecture.md`](docs/architecture.md). Read it before adding a module or a
control-socket method. Five rules bind code outside it:

- ⚠️ **`PolyCore.__init__` OPENS THE KEYBOARD** (`keeb.connect()`), so anything that
  decides whether this process should be the host must happen **before** the core is
  constructed, not in a `start()` afterwards. `instance.claim_instance()` is that
  gate: an OS file lock held for the life of the process, taken in `main_app` before
  any device code runs. Probing the socket alone is a check-then-act — two hosts
  starting in the same millisecond both read STALE and both open the device.
- **`PolyCore` is the Qt-free operational core** and must stay importable without
  PyQt5 and without a display. It communicates **only** through observer callbacks
  with JSON-serializable payloads; worker-side code must never touch a Qt object.
  Guarded by `tests/core/import_guard_test.py`.
- **A new device-coupled GUI surface is expected to work in client mode over RPC.**
  Client mode is the default under daemon-by-default, so anything gated off it is
  unreachable out of the box.
- ⚠️ **Six pieces of plumbing are shared implementations because a hand-written copy
  had already drifted** — `MpcListenerServer`, `UpdateProgressController`,
  `gui/theme.apply_theme`, `util/observable.Observable`, `util/filelock` (the
  endpoint claim and the settings save both need an OS file lock) and
  `PolyCore._flash_resource`. Reach for the shared piece; that is the point of it.
  ⚠️ **Extracting one drops the INLINE comments that made the original pass
  review** — `util/filelock` lost the comment on an `except … pass` that had been
  written for CodeQL's empty-except rule, because the extraction moved the
  rationale into the new module's docstring, where neither the linter nor the next
  reader looks. Re-run the checks on the extracted copy, not just on the callers.
  ⚠️ **When a bug is found in one of the three servers, grep the other two**
  (`control_server` / `window_report_server` / `browser_report_server`) for the same
  shape before designing anything — a deadlock was diagnosed across three sessions
  while a sibling module carried the remedy and its rationale in prose.
- ⚠️ **The network `WindowReportServer` serves exactly one method and holds no
  `PolyCore` reference.** That separation is the security boundary, not tidiness.

## Threading model (HID worker)

The Qt main thread does **no device I/O** after `PolyHost.__init__`. `HidWorker`
(`polyhost/device/hid_worker.py`) owns the device and runs the reconnect probe (1 s),
console reads (250 ms) and daylight brightness (10 min); UI code enqueues jobs.
The full contract — job coalescing, `run_sync`, `suspend`/`exclusive`, the reconnect
split and the probe debounce — is [`docs/hid-worker-refactor.md`](docs/hid-worker-refactor.md).
Six rules bind code outside it:

- **There is deliberately no synchronous language enumeration at startup.** The first
  worker probe must see a False→True transition and run the full fresh-connect flow; a
  startup enumerate duplicated all of it within the first second. Don't re-add one.
- **The probe is debounced (3 strikes)** because the keyboard goes deaf for hundreds of
  ms after a large overlay transfer. A single failed probe must not flap the connection
  state — that resets the MRU cache, wipes the overlays and forces a resend that keeps
  the keyboard busy for the next probe, a self-sustaining wipe-and-resend oscillation
  seen in the field.
- ⚠️ **Nothing the firmware prints during a flash is observable from the host** — QMK
  drops console output nobody drains, and during a flash nobody does. The tell is a gap
  in the firmware console timestamps spanning the flash. Use `tools/poly_console.py` in
  a second terminal. Two rounds were spent concluding "it printed nothing" from a log
  that structurally could not contain it.
- **`FW_UP_COMMIT` has FOUR status bytes** — `.` accepted, `?` awaiting the physical
  ACCEPT/REJECT on the keyboard, `S` not validly signed, `!` staged-CRC mismatch. `S`
  was split out because both refusals used to arrive as `!` and every consumer reported
  "CRC mismatch" for an image whose CRC was perfect. **Don't collapse them back.**
  `?` means "re-poll me", not "failed"; the host may CANCEL the prompt but never accept
  it, so do not add a host-side "allow unsigned" checkbox.
- **`polyctl fw version` is a LIVE query (HID cmd 0x43), not a cache** — it is asked
  exactly when a cache cannot answer, and it reported the pre-flash version after an
  update had demonstrably installed. It fails loudly ("suspended") mid-flash rather
  than handing back a stale string; the failure is the feature.
- **The no-blocking-the-main-thread rule covers NETWORK I/O too.** Every GitHub call
  the GUI makes runs on its own thread; a menu handler starts one and opens a progress
  dialog, never calls `requests` itself.
- ⚠️ **A MODAL opened from a bridge handler dispatches the OTHER queued bridge
  events**, re-entering `_on_job_done` before it returns. One update check reports
  host then firmware, so the firmware dialog opened on top of the host one — three
  times, each fix uncovering the next call site (#257). Route every dialog a bridge
  event can open through ONE serializer; the worked example and the rule are in
  [`docs/hid-worker-refactor.md`](docs/hid-worker-refactor.md) → *Threading model*.
- ⚠️ **A COM object never crosses a thread, and every thread that calls COM
  initializes it itself.** comtypes calls `CoInitializeEx` only on the thread that
  FIRST imports it, and our background workers (the shortcut harvest, the relay)
  exit when idle and are replaced. A cached COM object handed to the next thread
  is used from a dead apartment with COM not initialized. It does not raise a
  Python exception: it kills the headless daemon with a native access violation
  and no log line, and the tray survives with a dead pipe while the keyboard keeps
  working. This has happened TWICE with the same tell, a run of
  `Windows fatal exception: code 0x80010108` (RPC_E_DISCONNECTED) dumps in
  `crash_log.txt` ending in `access violation`: WMI in pywinctl's `getAppName`
  (2026-09-14, see `handler/win_process.py`) and the UI Automation harvest
  (2026-09-23, #264). `shortcut_source/uia.py` is the pattern: a per-thread
  cache, COM initialized under `_IMPORT_LOCK`, and `release_thread()` called in
  the worker's `finally`, dropping the object BEFORE `CoUninitialize`.

## Key notes

Nine groups, ordered roughly by how often a session needs them. Six subsystems that
are read only while you are inside them have moved to `docs/` and are reached from a
pointer bullet in the group they belong to — the layout editor, the font-pack
inspect/extend dialogs, diagnostics, telemetry, icons and autostart. Each pointer
keeps the parts of its subject that bind code *outside* it; if a rule is in a
pointer, it applies to you even if you never open the file.

⚠️ **Work that was deliberately NOT done — with the reason and with what would settle
it — is [`docs/FUTURE_WORK.md`](docs/FUTURE_WORK.md).** Read it before designing
something the file has already weighed. A deferral written only as a code comment is
invisible: the macOS glyph-table note sat one line from the code it describes for the
life of a branch and nothing surfaced it.

### Protocol, versions and the connect gate

**Version handling is RANGE-connect + per-feature gating, not exact-match.**
`decide_reconnect_apply` connects to any firmware whose protocol is
**≥ `MIN_SUPPORTED_PROTOCOL`** (= 2); each feature is then gated individually by
**`FEATURE_MIN_PROTOCOL`** (`device/poly_kybd.py`) through
`protocol_supports()` / `PolyKybd.supports()`. Newer firmware than the host **prompts**
(safe mode by default). The gate, the wire-format encode branches, the safe-mode plumbing
and the state-generation counter are in [`docs/protocol-gate.md`](docs/protocol-gate.md).

- ⚠️ **Every new device-facing command MUST be version-gated — no exceptions.** Add the
  `FEATURE_MIN_PROTOCOL` entry, guard both `PolyKybd` accessors with `self.supports()`,
  gate the GUI menu, surface it in `polyctl`, and bump `__protocol__` + the firmware
  `PROTOCOL_VERSION` in the same change. An **ungated** command silently connects and
  then NACKs at runtime on an older keyboard instead of cleanly disabling — the exact
  failure the range-connect model exists to prevent, and a gate that "has been forgotten
  twice". The `add-gated-hid-command` skill drives the whole job. **Two tests now
  enforce it** against an emulated keyboard of every protocol
  (`tests/device/protocol_gate_sweep_test.py`, `tests/core/core_protocol_sweep_test.py`):
  a new `Cmd` needs its introducing protocol in `device/mock_firmware.py`
  `CMD_MIN_PROTOCOL`, and a new `PolyKybd` method a `CALLS` entry. On their first
  run they found cmd 31 (`replay_startup_anim`), a v11 command, sent ungated to v2–v10.
- **Still bump `__protocol__` (`polyhost/_version.py`) in lockstep with the firmware
  `PROTOCOL_VERSION`.** It now defines the host's *newest-known* protocol, not a hard
  connect gate, so forgetting it only downgrades the status and disables that one
  feature — quieter, and worse.
- **Firmware update survives protocol mismatches.** Flash/apply/bootloader actions gate
  on `_fw_actions_allowed()` (device present, not paused), **not** on `self.connected`.
  Don't re-gate any firmware-update path on `connected`.
- ⚠️ **`parse_id_version_block` finds the font-pack block POSITIONALLY** (`'V'` at
  exactly `nul + 1`), so anything the firmware adds to the GET_ID reply must go
  **after** it. Prepending makes every deployed host read "no bundles on the device"
  and re-flash all eight on every connect.
- **v21: prepare and enable ride on cmd 33** as flag bits in its width byte (0x40
  reset before the pairs, 0x20 show after; `send_overlay_mapping(reset=, show=)`).
  ⚠️ **The prepare step is sent LAZILY on v21**, right before the first image report
  (`ensure_prepared()` in `send_overlays_mru`), because an upload into a slot the old
  mapping still shows would appear on the old key. A warm switch sends no image, so
  its reset rides on the first mapping report and the switch is its mapping reports
  alone (warm 249 → 129 reports over all 60 sets). An empty mapping has no report
  to carry the flags and keeps the separate cmd 11 reports.
- ⚠️ **The raw channel is strictly request/response**, and `send_and_read_validate`'s
  drain depends on it: since protocol v3 the firmware sends no unsolicited replies, so
  a stale reply means one thing only. Making push work means framing plus routing in
  exactly the code path stale-reply bugs live in.

### The font pack

The external-flash font pack ships as **N per-family bundles**
(`polyhost/res/fontpack/<id>.plyf` + `bundles.json`), flashed per slot on a fresh
connect for whatever the device is missing or behind on. The slot layout, the
autocheck job, the retry/verify logic and `polyctl fontpack` are in
[`docs/fontpack.md`](docs/fontpack.md); firmware-side architecture is in the qmk repo's
`keyboards/polykybd/FONT_PACK.md`.

- ⚠️ **A bundle can report a FAILED flash and still read as UP TO DATE, so the version
  comparison alone must never decide what to re-flash.** FONTPACK writes **in place**,
  so a stream whose COMMIT *acknowledgement* was lost leaves a complete, CRC-valid slot
  advertising the new version. The core therefore remembers failures and re-flashes them
  regardless of version, and verifies a failed COMMIT before believing it.
- **One bundle's failure must not abort the pass** — the old return-on-first-failure
  cost six good bundles a flash because slot 0 failed.
- ⚠️ **The GET_ID version block reflects the MASTER's slots only**, so it can never
  prove the slave got the bundle; say `slave-unconfirmed` rather than claiming success.
- ⚠️ **Bundle 8 is the overlay ICON library (`icons.plyi`, magic `PlyI`, cmd 42,
  protocol v20), not a font.** It is built by `scripts/build_icon_library.py` from the
  templates (`--check` is a test), its ids are frozen in `res/fontpack/icon_ids.yaml`
  (append-only: the id IS the glyph index), and the send path fills a pool slot only
  when an image's packed bytes EXACTLY match a glyph (`services/icon_library.py`) and
  the keyboard reports exactly the shipped bundle version. A bundle whose slot the
  device's `V` block does not list is never flashed (`device_has_slot`), or a v19
  keyboard would refuse `icons.plyi` on every connect.
  ⚠️ **Rebuild it in BATCHES, never per overlay change** (maintainer's rule,
  2026-10-02). Each rebuild bumps `content_version`, and every keyboard re-flashes
  the slot on its next connect. An icon missing from the library is simply uploaded
  as a bitmap like any other overlay image (`poly_kybd.py`, the `upload()` branch),
  so `--check` lists new eligible icons as **pending** and fails only when the
  shipped files disagree with `icon_ids.yaml`. Rebuild when the pending list is
  worth a re-flash, for example before a release.
  **An icon enters the library only if more than one app uses it** (maintainer's
  rule, 2026-10-09), and the library never decides what a key shows. The send
  path's hit test is the image BYTES, whatever made them (a template, a generic
  icon, a plyi glyph); the plyi only changes how a miss travels, as a cmd 42 fill
  instead of an upload.
- ⚠️ **One switch shows at most 600 distinct images, and that is the ONE limit**
  (the module constant `OVERLAY_POOL_CAPACITY` in `device/device_settings.py`, which
  the `DeviceSettings.OVERLAY_MAPPING_CAPACITY` property returns, = the firmware's
  `NUM_OVERLAY_SLOTS`, #344). It counts IMAGES, not keys: keys sharing an image share a slot, so the
  shortcut planner has no cap of its own, and the forwarder relay reuses the value
  only as its network bound. The send path enforces it: a switch never evicts its own
  slots, so past 600 the extra keys stay BLANK and a warning is logged. Before that
  guard, 650 images in one switch drew 600 right keys and 50 WRONG ones while the send
  reported success. An MRU hit counts toward the 600 too, since a hit re-stamps its
  slot with the current batch.
  ⚠️ **The claim pass and the send loop must agree on which image a key ENDS UP
  showing** (#346). `send_overlays_mru` claims the switch's pool hits before
  allocating, so a new image can only evict a slot the switch does not want. Both
  passes apply the same rules: a later source wins a key, a synthetic source skips a
  key a template already draws, and a content-key hit counts only if the bytes match
  (`OverlayMRUCache._key_hit`). The two CodeRabbit findings on #346 were both the
  passes disagreeing: a claimed image a later source replaced left a new image's key
  blank, and an edited file under the same name kept its old pixels. Change one pass,
  change the other, and run `tests/device/mru_claim_test.py`.
- **The flash events carry a `kind`** (`fontpack` / `doomwad` / `doompack`) — label UIs
  from it, not from the event name; the doom `.whx` and `.plyx` ride the same transport.
- ⚠️ **`install_doompack` sends EXECUTABLE CODE over that transport.** The `.sig`
  handling in `hid_fw_up` covers the *firmware image only*. Do not describe the keyboard
  as "signed firmware, so a malicious flash is covered" — the fix is firmware-side.
- ⚠️ **`tests/device/hid_fontpack_test.py` pins the COMMIT status contract from the HOST
  side only**, which is the less useful side — the bug that shipped was the firmware
  *emitting* `!` for a dropped link ack. When you touch these values, update the
  firmware suite (`make test:fw_up_verdict`) too.

### Device features over HID

The per-feature device commands — **glyph script** (cmd 30, v9+, with the v10
open-ended index and the rendered menu previews), **keycap legend size** (cmd 34, v13+),
and **macros** (cmds 36/37/38, v15+, behind one `"macros"` gate) — are wired identically:
`PolyKybd` accessors behind a `FEATURE_MIN_PROTOCOL` entry, `PolyCore`, an `M_*` control
method, the `RemoteCore` mirror, a `polyctl` subcommand and a gated tray submenu. The
full wiring, the preview rendering and the label-measurement rules are in
[`docs/device-features.md`](docs/device-features.md).

- **The idle TIMEOUT (cmd 40, v18+) is the same wiring one more time**, gated on
  `"idle_timeout"`: six fixed presets (15 s…5 min) replacing what was a compile-time
  2 minutes in the firmware. ⚠️ **Its reply carries the duration in SECONDS as well
  as the preset index, and the UI labels from the SECONDS** — that is the only way a
  host older than a firmware which adds a preset renders "10 min" instead of "preset
  6". `IdleTimeout.label_for()` is the one place that decides; don't relabel from the
  local enum. The SET range stays closed (see the GlyphSize/GlyphScript note below —
  this one follows GlyphSize).
- ⚠️ **`expect(Cmd.X)` matches only the two `P<cmd>` bytes, which a NACK carries
  too** — so `send_and_read_validate` returning True says the reply arrived, never
  that the firmware accepted it. On a CLOSED range that is the difference between a
  refusal and a silent success: read the verdict at `reply[2]` (`.` accept, `!`
  refuse) before reporting one. `set_idle_timeout` does, and validates the preset
  through the enum before any I/O; `set_glyph_size`, `set_idle_style` and
  `set_glyph_script` still have the older prefix-only shape.
- ⚠️ **`GlyphSize` is a CLOSED range and `GlyphScript` is OPEN — that asymmetry is
  deliberate, and it is the one way they differ.** An unknown SCRIPT index is accepted
  by the firmware and degrades to the normal legend, which is what lets the host offer
  faces a keyboard lacks **without a protocol bump**. An unknown SIZE is NACKed, because
  it would persist as a setting that silently renders small. Never "make them
  consistent"; `tests/device/poly_kybd_capabilities_test.py` pins the contrast.
- ⚠️ **`PolyCore.macro_*` is WHOLE-BUFFER on purpose** — the bodies are NUL-delimited in
  one shared buffer, so read-modify-write is the only shape that cannot corrupt a
  neighbour.
- ⚠️ **The macro label meter is in PIXELS, not characters** (`services/macro_label.py`
  mirrors the firmware's bbox): the real budget is ~12 characters, 8 in the worst case,
  and a character count is wrong in both directions.
- ⚠️ **`tools/apply_tuner.py`'s export grammar cannot express the `caps` column** — a
  bulk edit touching caps cells must import the module and call `set_cell()`, which
  returns the sheet and persists nothing. The whole loop is the firmware repo's
  `tune-lang-lut-cells` skill.

### The layout editor

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

### The tray, its menus, and the OS around them

The tray menu is **two-tier**: ~9 normal rows plus a **Developer** submenu that only ever
ADDS — turning developer mode on **does not rearrange anything** (asserted by
`tests/gui/host_client_test.py`). Both apps follow the OS light/dark setting. The menu
construction, the theme reader, the brightness rows, the WinCompose install path, the
unicode-mode watcher and the icon rules are in [`docs/tray-ui.md`](docs/tray-ui.md).

- **The tray app and the forwarder are translated into 20 languages; how and why is
  [`docs/i18n.md`](docs/i18n.md).** Every string a user reads in `gui/`, `host.py`
  or `forwarder.py` goes through `_()`, `_f()` or `_nf()` from `polyhost.i18n`, and
  `tests/i18n_test.py` fails on an unmarked literal handed to a Qt text call. After
  adding or changing one, run `python scripts/i18n_strings.py update`. Logs,
  `polyctl` output and the core's message text stay English on purpose. ⚠️ A
  function that calls `_()` must not also assign `_` (`ok, _ = f()`): Python then
  makes `_` local to the whole function and the call raises `UnboundLocalError`.
- ⚠️ **`managed_connection_status` blanket-disables every top-level action first**, so a
  **new group parent must be re-enabled explicitly there** or its whole submenu goes
  unreachable on a disconnect.
- ⚠️ **A tray balloon (`show_balloon` → `QSystemTrayIcon.showMessage`) reaches
  NOBODY on macOS** — Qt's Cocoa backend routes it through `NSUserNotificationCenter`,
  which silently drops a notification from a process with no bundle id of its own, and
  we always run as a bare `python -m polyhost`. `messageClicked` dies with it, so
  "click the tray icon to update" was an instruction to click something never shown.
  **Never make a balloon the only carrier of anything.** `PolyHost._balloons_reach_user()`
  (`host.py`) is the gate, over `balloons_are_delivered()` in `gui/tray_notify.py`: it
  asks whether the executable sits inside `<name>.app/Contents/MacOS/`, the rule
  `NSBundle` itself applies, so a real bundle re-enables delivery with nothing here to
  revert (the USER still has to grant notification permission — bundling buys the
  prompt, not the banner). The fallbacks are a directly-opened dialog (once per version
  per session, serialized through `_fallback_prompt` because ONE check reports host then
  firmware and a modal dispatches the second event while the first is open) plus the
  version on the **top-level** Updates row. ⚠️ **`IconStateManager` owns the tray
  tooltip** — it restores its OWN stored text when a warning expires, so a direct
  `tray.setToolTip` survives only until the next `set_warning`. Anything with a
  lifetime goes through `set_base_tooltip`, and `_refresh_tray_tooltip` is the one
  place that decides what that text is.
- **Developer mode (`--dev`) is SEPARATE from log verbosity**, and it is a persisted
  setting, not just a flag — under daemon-by-default the tray is launched by autostart
  with no flags, so a flag-only gate makes every developer tool unreachable.
- **A settings change applies its device side effects through ONE core hook**,
  `PolyCore.note_settings_changed(keys=None)`. Add the side effect to the hook, never to
  a caller; there are two settings writers and the second copy is how enabling a setting
  mid-session came to do nothing at all.
- ⚠️ **`PolySettings.save()` merges per KEY against the file, and must keep doing so** —
  the daemon and the tray both hold a `PolySettings`, so a whole-file rewrite from a
  stale in-memory copy silently reverts the other one. That is how the telemetry install
  id was lost: the GUI generated and saved it, the daemon saved 8 minutes later from the
  empty value it had loaded first, and the next run generated a new id, counting the
  machine as two installs. `save()` re-reads the file and imposes only the keys this
  process changed, through a temp file + `os.replace`, **under a cross-process lock** —
  read-merge-replace is itself a read-modify-write, and six concurrent writers of six
  different keys lose 3–4 of them per run without it. ⚠️ Two details are load-bearing:
  `_read_file()` returns **None, not `{}`**, when the file cannot be read (merging
  against `{}` fills every unchanged key with a DEFAULT and silently resets the user's
  settings), and the lock is **best effort** — a save that cannot take it still writes,
  because losing the write outright is worse than the rare interleaving.
  ⚠️ **`save()` never raises**: the constructor saves on every start, and on
  Windows `os.replace` fails with `WinError 5` while any process has the file open
  (Python's `open()` never shares delete). That killed the tray at startup twice
  in a row (2026-09-25). The replace is retried for ~1 s on Windows, and a save
  that still fails is logged and kept pending in memory. ⚠️ It **returns whether
  it wrote**, and a caller that tells the user a change was saved must check it:
  `read_setting()` readers (the shortcut harvest's privacy switch among them) see
  the file, not the in-memory value.
- ⚠️ **The FORWARDER is a second tray app** (`polyhost/forwarder.py`) with its own
  `QApplication`, menu and log file, **on a different machine from the keyboard**. A
  user-facing tray feature added to `host.py` is simply absent there until wired
  separately — which matters most for support features, since its logs can never appear
  in a bundle collected host-side. Its menu **follows the tray app's shape minus the
  device group** (status · Pause · — · update · Settings… · Help & About · Quit) and its
  About is the **shared** `gui/about_dialog.build_about_dialog`; render both with
  `tools/render_tray_menu.py --mode all`, since nothing but an eye on the two images says
  whether they still match. ⚠️ Its Settings is an **allow-list**
  (`FORWARDER_SETTING_KEYS`) — `SettingsDialog` renders whatever dict it is handed, so
  the whole `settings.yaml` would put brightness and font-pack rows on a machine with no
  keyboard, every one a control that writes a value and changes nothing.
  ⚠️ **Process-wide Qt identity is "wired separately" too.** `PolyHost.__init__` set
  the application name and the forwarder never did, so its windows carried the X11
  WM_CLASS `__main__.py` (Qt falls back to the script name). Two things read that one
  string: GNOME's `.desktop` matching, which drew a grey gear on every forwarder dialog,
  and the GNOME Wayland reporter, which uses the class as the app name, so the keyboard
  drew no ESC mark either (#265). `main_app` now sets it before either app is built.
  Put anything process-wide there, not in one app's constructor.
- ⚠️ **The forwarder's tray mark spells an F, not a P** (`IconStateManager(prefix=)`),
  because both apps can sit in one notification area. It tracks whether reports are
  **landing** (`relay_ok`, set by the `send_to_host` wrapper around `_send_to_host`) —
  it used to call `set_connected()` once at startup and never revisit it. ⚠️ `think`/
  `warn` are deliberately unprefixed: they clear every inner key, so no letter survives
  in them and an `f` twin would be a byte-identical copy with no `cmp` guarding it.
- ⚠️ **A wrong or missing icon NAME fails silently** — `QIcon()` on a nonexistent path
  returns an empty icon and the row renders without a picture. `tests/gui/icon_assets_test.py`
  is the guard.
- **The brand mark and the menu/tray icon rules are [`docs/icons.md`](docs/icons.md);
  the ESC program mark — the per-application icon, its three sources and the
  rule that governs them — is
  [`docs/generic-icons-plan.md`](docs/generic-icons-plan.md).** ⚠️ Read the
  second before adding any per-application anything: its rule is **no
  per-application configuration**, and it reverses an earlier 70-entry
  name→slug map. Both files were unreachable from this file until 2026-09-23
  even though the Key notes intro named "icons" as a pointer — the plan's rule
  was found by grep, one step from being broken.
- ⚠️ **A FLOOR MUST NOT DECIDE A CONTEST.** `MIN_SCORE` answers "may we draw
  this when there is nothing else"; clearing it used to END icon resolution, so
  every macOS `.icns` (measured 0.117 against a floor of 0.08) won outright and
  four newly shipped marks were inert on hardware — shipped, tested, changed
  nothing. Candidates are ranked now; the floor only gates usability.
- ⚠️ **A rendered pixmap does not follow a palette change** — the glyph-script previews
  are dropped and rebuilt on a theme switch, or near-white ink lands on a light menu.
- ⚠️ **Defaulting a platform path OFF because it is obnoxious can hide that it
  never worked.** macOS language switching was disabled in 0.18.1 to stop a
  password dialog, and for three months a language key repainted the tray menu
  and reported `True, "OS-language auto-switch disabled"`. The dialog came from
  `languagesetup`, which sets the system UI language and had never once switched
  an input source. **Check whether the path was doing its job before muting it.**
- **The input helpers — the keystroke-cycling `set_language` every platform
  inherits, the per-platform compat maps, and the four traps around them — are
  [`docs/architecture.md`](docs/architecture.md) → *Platform input abstraction*.**
  Two rules bind code outside it: `LangComp(platform)` REQUIRES its argument
  (reading another platform's map mostly WORKS, which is the trap), and a
  helper's `get_current_language` and `set_language` must answer in ONE
  namespace or the sync re-fires on every probe forever.
### Updates, autostart and daemon mode

Autostart registration and the post-update relaunch chain are
[`docs/autostart.md`](docs/autostart.md). Six rules bind code outside it:

- ⚠️ **There are TWO locks, and they are deliberately different files.**
  `claim_instance()` guards the control endpoint (the core daemon holds it);
  `claim_gui()` guards the tray icon (the GUI holds it). Under daemon-by-default the
  GUI is a *client* and never owns the endpoint, so only the GUI lock can stop a second
  tray — and one shared file would have the tray block the very daemon it just spawned.
  ⚠️ **`claim_gui()` waits ~3 s rather than refusing at once**, because the post-update
  relaunch spawns the replacement before this process exits; `main_app` also releases
  the claim explicitly before `restart_app()`. Refusing immediately there is *"it
  doesn't start up again after the update"*.
- ⚠️ **Registering autostart must never START the app** — it always runs from an
  app that is already running. macOS made this concrete: the plist carries
  `RunAtLoad`, so the `launchctl load` in `add_to_startup()` launched a SECOND copy,
  and a first-time install came up with two tray icons, two core daemons and an
  `EADDRINUSE` crash from the loser — which had already opened the keyboard
  exclusively, locking the winner out of the device for 50 minutes. The tell is that
  the second process starts a few ms **before** the first logs "Autostart
  registration: …", since that line lands after `subprocess.run` returns.
- **GUI self-update must be applied by the DAEMON, not the client.** In daemon mode the
  tray is a `--connect` client and the daemon owns `PolyCore` — and therefore the
  protocol gate. Running `UpdateInstaller` in the GUI process refreshed only the client
  while the daemon kept running pre-update code, stuck on the old `__protocol__` until
  manually restarted. After the daemon re-execs, the GUI waits for the endpoint to go
  **down → back LIVE** before relaunching, or it re-attaches to the old daemon.
- ⚠️ **Every relaunch must be spawned DETACHED** (`spawn_detached()`), and
  `sys.executable` normalised to `pythonw.exe`. A plain `Popen` on Windows is how *"it
  doesn't start up again after the update"* happens.
- ⚠️ **The generated launchers live in the platformdirs config dir, NOT the checkout** —
  in-tree they were deleted by `git clean -xdf` while the task still read `State: Ready`.
  ⚠️ The Windows task is named **`PolyHost`**, not `PolyKybdHost`.
- **`updater.preflight()` runs before the download**, at the one choke point the tray,
  the daemon and `polyctl update install` all pass through — an update that copies
  perfectly and then cannot relaunch is indistinguishable from "the app never came back".

### When something is reported broken

Logs, crash reporting and the guided problem report are
[`docs/diagnostics.md`](docs/diagnostics.md); the three silent failure modes of
multi-machine forwarding are in the same file; the telemetry client and its collector
are [`docs/telemetry-internals.md`](docs/telemetry-internals.md). Eight rules bind code
outside those files:

- ⚠️ **A NEW LOG FILE reaches nobody unless `LOG_SOURCES` knows about it.** That one
  declaration replaced four hand-kept lists which had already drifted —
  `crash_log.txt`, the file whose whole purpose is proving whether the app crashed,
  shipped into **none** of them. Registering is half: check the lines carry a sliceable
  timestamp prefix, or `slice_lines` silently drops the whole file.
- ⚠️ **Never rotate, delete or `os.replace` `crash_log.txt`** — `faulthandler` holds the
  file descriptor, so a rename leaves the live process dumping into a deleted inode.
  Clear it by TRUNCATION, which is safe only because every writer opens with `"a"`.
- **Redaction defaults ON for a report and OFF for "Collect logs…"** — same data,
  different destination, so the safe default flips.
- ⚠️ **`polyctl logs` must work with NO host running** — the moment a user most needs
  the logs is the one where the app failed to start.
- ⚠️ **`Connected to PolyKybd.` does not mean a usable device** —
  `_open_interfaces()` returns True when `HidHelper` found no raw HID interface
  (it sets `self.interface = None` and does not raise), so the core logs a
  connect and every command afterwards returns `'No Interface'`. Nor is
  `exclusive access and device already open` proof of a second process: the same
  function reassigns `self.hid` without closing the previous helper, so one
  process collides with the handle it is replacing. **Reading a bundle is the
  `triage-log-bundle` skill**, which carries these and the rest of the lines
  that lie.
- ⚠️ **The problem scan matches firmware console lines against a CURATED list
  (`problem_scan.CONSOLE_PATTERNS`), never keywords** — healthy output says
  `transport_fail=0 giveup=0`. A new firmware failure message needs an entry there
  to reach the user. Its log handler is on the root logger of whichever process
  installs it (the core, or a daemon-client tray), and must not log from its own
  callback. Details: [`docs/diagnostics.md`](docs/diagnostics.md) → *The problem scan*.
- ⚠️ **"The tray icon is gone" is NOT "the app crashed"** — under daemon-by-default the
  daemon still owns the device with no GUI attached. Check the process list, in PAIRS.
- ⚠️ **The telemetry payload is an ALLOW-LIST at both ends — a privacy guarantee.**
  `build_payload()` copies named fields and never spreads a status dict. **There is no
  in-app consent step**, so the release notes are the disclosure and the one INFO line
  printed at every start is all a headless daemon can say: do not gate it, downgrade it
  or drop it in a logging cleanup.

### Environment

- **Linux HID permissions**: `polyhost/device/99-hid.rules` must be installed as a udev
  rule for non-root HID access.
- **Venv**: always use `PolyKybdHost/.venv/bin/python` — system `python3` lacks numpy,
  PyQt5 and other deps. Creating it in a fresh container, the apt packages the `hid`
  module needs, and the extra deps + `xvfb` the GUI half of the suite requires are in
  [`docs/dev-environment.md`](docs/dev-environment.md).
- ⚠️ **A missing dependency DELETES tests, and the `Ran N` line is the only thing that
  says so.** A module that fails to import contributes one error and **zero tests**: the
  same tree ran **1982** tests with `hid`/`requests`/`pynput` absent and **2447** with
  them installed. Comparing a failure set against a baseline then comes back clean for a
  reason that has nothing to do with coverage. **Install the deps and read the count.**
- ⚠️ **A text-mode `open()` without `encoding=` on a NON-ASCII file of ours is a
  Windows crash, and this repo has now paid for it TWICE.** Python decodes with
  the platform default — the ANSI code page on Windows (cp1252), never UTF-8 —
  so any file of ours carrying an em dash, a box-drawing rule or a ⚠️ is a
  grenade there. (Pure ASCII is safe under every codec, and `PYTHONUTF8=1` opts
  a whole process out — neither is something we can assume about a user's
  machine.)
  `lang_compat.py` took `PolyHost.__init__`, the tray and the daemon down with
  `UnicodeDecodeError: byte 0x8f` (field, Windows 11 / Python 3.13, 2026-09-22),
  three months after `publish_release.py` hit the identical codec on the
  identical trigger — and **that note went into `docs/releases.md`, scoped to
  releases, where nobody reading an input helper would ever find it.**
  ⚠️ **The crash is the LUCKY outcome.** Only five byte values are undefined in
  cp1252, so most of our files decode to MOJIBAKE and parse on:
  `forced_country_match_{linux,macos}.txt` do exactly that, harmless only
  because their non-ASCII sits in comments. A non-ASCII character in a VALUE
  would resolve to the wrong layout in silence, on every Windows machine.
  **The rule is by FILE OWNERSHIP.** A file we ship and author (`res/` data,
  `requirements.txt`, `bundles.json`) gets `encoding="utf-8"`. A file the USER
  owns (`--host-file`, a chosen `.poly.cmd`, KDE's `kxkbrc`) keeps the platform
  default until we define a fallback policy, because forcing UTF-8 there newly
  REJECTS a legacy cp1252 file that reads fine today. Find every candidate by
  **re-running** the AST sweep — every tracked `.py`, calls to the BUILTIN `open`
  only, no `encoding` keyword, no `b` in the mode — and classify each hit by
  ownership. ⚠️ **Scope the sweep to the whole tree, not `polyhost/`**: the
  2026-09 pass stopped there, reported 5, and missed four more of ours in
  `setup.py`, `tools/` and `tests/` that a reviewer then found (2026-09-22).
  Three hits remain today and all three are user-owned.
- **Chromium is available headless — use it to LOOK at generated HTML/SVG** rather than
  reading the markup (`--headless --screenshot`, then Read the PNG; add
  `--blink-settings=preferredColorScheme=0` for dark). This caught a dashboard defect
  that existed only in the render while the HTML and the tests were both correct.

### Tests

`*_test.py` under `tests/` mirroring `polyhost/`; **unittest, not pytest**. Use
`scripts/run_tests.py` when a run might hang — it arms a stall watchdog that prints every
thread's stack. ⚠️ **`--timeout` bounds ONE test, not the run** (it re-arms per test),
so it needs no tuning as the suite grows. Do not write the suite's length or test count
down anywhere: every figure this file has carried went stale, and a whole-run budget set
from one fired on a healthy run. Run the full suite backgrounded, or under a tool timeout
well past it, since an outer kill throws the dump away.
GUI tests need `xvfb-run -a`; rendering a widget headless needs `xvfb-run` **and**
`QT_QPA_PLATFORM=offscreen`, for opposite reasons. The rest — the fixture traps, the
headless-render recipes, and the `ControlServer.stop()` deadlock post-mortem — is in
[`docs/testing.md`](docs/testing.md).

- **No keyboard needed: `dev_mock_primary` (+ `dev_mock_protocol`) makes the mock the
  device**, and its overlay path is the real `PolyKybd` over `MockFirmware`, a Python
  copy of the firmware's side of the HID channel with a `FaultPlan` for the recovery
  paths. ⚠️ It copies the firmware's QUIRKS too, on purpose. What it models, what it
  does not, the board view and the sweeps: [`docs/mock-device.md`](docs/mock-device.md).
- ⚠️ **HOW YOU INVOKE THE SUITE CHANGES THE ANSWER, and both wrong ways look
  like results.** `unittest discover -s ./tests` PREPENDS `tests/` to
  `sys.path`, and `tests/tools/` then SHADOWS the repo's own `tools/`, so
  anything reaching `tools.gfx_font` blows up: measured on one tree,
  **3418 tests / 5 failures + 21 errors** against
  `scripts/run_tests.py`'s **3441 / 1 error**. And a baseline taken in a
  `git worktree` under `/tmp` silently skips every test gated on
  `../qmk_firmware` (129 skips vs 44), so the comparison reads as your branch
  un-skipping 85 tests. **Run the runner, and baseline IN PLACE** — check the
  two commits' files back out in the real checkout. Both cost a full cycle in
  2026-09-23. Details in [`docs/testing.md`](docs/testing.md).
- ⚠️ **A `skipUnless` guard that checks a SUBSET of what the code checks turns a
  missing dependency into an infinite HANG.** `_FONTGEN` imported numpy+freetype
  while `_build()` also needs uharfbuzz/fontTools/PIL, so on a partial set the
  guard said run, the dialog took its error path — a **modal** `QMessageBox`
  with nobody under xvfb to dismiss it — and the suite sat for 48 minutes with
  no output. Derive such a guard from the function the code itself calls. A
  missing dep normally skips or errors; this class hangs, and only
  `scripts/run_tests.py`'s watchdog (or `py-spy dump --pid`) names it.
- ⚠️ **A change to CONCURRENT FILE ACCESS is not done when the tests pass.** The
  per-key settings merge took four review rounds and produced two regressions
  *while fixing the previous one* — merging against `{}` on a read failure reset
  every untouched key, and degrading an unreadable file to defaults let the
  constructor's save destroy it. Its diff looked small. Before calling one done:
  mutation-sweep it (`mutation-test-suite`), and race it with REAL processes —
  six concurrent writers of six different keys lose 3–4 per run unlocked and none
  locked, which no single-process test would ever have shown.
- **RUN the real entry point once before believing a mocked suite.** A suite whose
  fixtures you wrote can only be as right as your idea of the real data; one
  `polyctl logs bundle` in a temp dir caught two format bugs every test passed over.
- ⚠️ **Appending test methods after a file's trailing `if __name__ == "__main__":`
  registers NOTHING** — the indented `def`s become part of the `if` body, parse fine and
  never run. **Check the test COUNT changed**, not just that the suite is green.
- ⚠️ **`patch.object(Class, "method")` does NOT reach a fixture that already BOUND that
  method**, which this repo's fixture idiom does constantly. Drive the real input, or
  override the attribute on the instance.
- ⚠️ **A stale `.pyc` can survive a CORRECT fix** — invalidation is (mtime, size), so a
  length-neutral edit in the same mtime second is invisible. The tell is a traceback
  quoting source that no longer exists. Clear `__pycache__` after **restoring** too, not
  only after editing — a mutation sweep's confirmation run is exactly where this lands.
- ⚠️ **`polyhost/forwarder.py` is UNTESTABLE in the documented environment** (pywinctl at
  module load). Put forwarder logic worth testing in a Qt-free module; a test gated on
  both `DISPLAY` and pywinctl is permanently skipped, which reads as coverage.
- ⚠️ **The suite cannot execute the platform input paths** — Win32, Carbon and
  pynput keystrokes are mocked by necessity. All four field defects of
  2026-09-22 lived in that region while 2949 tests stayed green, so a green
  board says nothing about it: budget a hardware round.
- **No unit-test CI**, but `codeql.yml` analyses every PR — the one automated reviewer
  here that cannot go quiet.

## Releases

Host releases are **GitHub Releases** (tag `vX.Y.Z`; version in `polyhost/_version.py`),
created by **publishing** — *not* by pushing a tag, which lands on the auto-bump
`[skip ci]` commit and triggers nothing. Use the `polykybd-github-release` skill; the
mechanics, the `release-notes` branch convention and `scripts/publish_release.py` are
in [`docs/releases.md`](docs/releases.md).

- ⚠️ **`scripts/publish_release.py` is byte-identical across `qmk_firmware`,
  `PolyKybdHost` and `wincompose`, nothing checks that, and it had already
  diverged in BOTH directions at once** — these two repos held the
  commit-pin and the `make_latest` correctness, wincompose held the
  create-time gate, and each copy was the newer one for a different thing.
  `md5sum */scripts/publish_release.py` is the check. Its tests live in
  **`PolyKybdHost/tests/scripts/publish_release_test.py`**, the only one of
  the three repos with a Python runner, so a break introduced here fails
  there.

- ⚠️ **`release.yml` now REFUSES a tag whose tree declares a different
  `__version__`** — its first step, before the release is created or its notes edited.
  The updater compares exactly those two numbers (`updater.py` fetches
  `archive/refs/tags/<tag>.tar.gz` and tests the installed `__version__` against
  `_version_from_tag(tag)`), so a release published before its bump merged hands out a
  tarball that can never reach the advertised version — and every later check offers
  the same update again, forever. wincompose shipped that failure through its own
  mechanism (`PK-0.9.19`). ⚠️ **On a mismatch it WITHDRAWS the release** — marks it a
  prerelease, which drops it out of `releases/latest`, the only channel `updater.py`
  reads — because failing the job retracts nothing: this workflow uploads nothing to
  withhold, and on `release: published` the release is public before the step runs.
  Prerelease rather than delete, so it is reversible and keeps the notes and the tag.
  The pre-publish defence is still `publish_release.py`. ⚠️ **The fix is to MOVE the tag, and only while no
  release holds it** — publishing never moves one, and the tarball people install IS
  `archive/refs/tags/<tag>.tar.gz`, so delete the release the refusal left behind before
  moving anything. [`docs/releases.md`](docs/releases.md) → the first bullet has both
  refusal cases.

- ⚠️ **A `PROTOCOL_VERSION` bump means BOTH artifacts get released, and the check is
  the PUBLISHED versions, not the in-tree ones.** The source-lockstep rule can be
  perfectly satisfied while the releases sit a protocol apart, and nothing downstream
  catches it because the connect gate is not exact-match — an old host pairs with new
  firmware and silently leaves the new features off. **Publish the host first**, then
  the firmware.
- ⚠️ **Version bump is label-driven, and the label must be set AT OPEN.** A request in
  the PR body is documentation, not a label; `bump-version.yml` reads labels at merge
  time and a label applied as the merge happens lands too late. `create_pull_request`
  cannot set labels — use `issue_write` with `labels:` right after opening.
- ⚠️ **The bump lands through its own auto-merged PR, because `main` requires a PR**
  (2026-10-09). It depends on "Allow GitHub Actions to create and approve pull requests"
  and on the `main` rule requiring a PR and nothing more: a required check or approval
  would leave every bump PR hanging. Details in [`docs/releases.md`](docs/releases.md).
- ⚠️ **Since 1.0, PATCH is the default and `bump:minor` is the exception** (maintainer's
  rule, 2026-10-03). Before 1.0 a small change landed as a 0.9.x patch; after 1.0 almost
  every PR carried `bump:minor`, so the firmware went 1.0.0 → 1.7.0 in six days and the
  host 1.3.0 → 1.15.0 in nine. Leave the label off (patch) for fixes, diagnostics,
  developer tools and small additions, **even when the PR bumps `PROTOCOL_VERSION`**:
  the protocol is its own number. Use `bump:minor` only for a feature an owner would
  call new, the kind that names a release. When unsure, ask.
- **Host and firmware version numbers are NOT kept in lockstep** (they were aligned
  once, at 0.11.0, cosmetically). The number that must move together is
  `__protocol__` / `PROTOCOL_VERSION`.
- ⚠️ **From Claude Code on the web you can neither push tags nor create a release** —
  stage the notes on the branch and hand the user `python scripts/publish_release.py`.
  The same proxy 403s on branch **deletion**, so don't create scratch branches you
  can't clean up.
