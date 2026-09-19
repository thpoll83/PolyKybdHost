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
  believing the badge. Merge the base, wait for the stacked PR's `base.ref` to
  become `main`, then merge it. Recovery is the `re-land-orphaned-pr` skill — and
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

## Key notes

Nine groups, ordered roughly by how often a session needs them. Six subsystems that
are read only while you are inside them have moved to `docs/` and are reached from a
pointer bullet in the group they belong to — the layout editor, the font-pack
inspect/extend dialogs, diagnostics, telemetry, icons and autostart. Each pointer
keeps the parts of its subject that bind code *outside* it; if a rule is in a
pointer, it applies to you even if you never open the file.

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
  twice". The `add-gated-hid-command` skill drives the whole job.
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

- ⚠️ **`managed_connection_status` blanket-disables every top-level action first**, so a
  **new group parent must be re-enabled explicitly there** or its whole submenu goes
  unreachable on a disconnect.
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
- ⚠️ **The forwarder's tray mark spells an F, not a P** (`IconStateManager(prefix=)`),
  because both apps can sit in one notification area. It tracks whether reports are
  **landing** (`relay_ok`, set by the `send_to_host` wrapper around `_send_to_host`) —
  it used to call `set_connected()` once at startup and never revisit it. ⚠️ `think`/
  `warn` are deliberately unprefixed: they clear every inner key, so no letter survives
  in them and an `f` twin would be a byte-identical copy with no `cmp` guarding it.
- ⚠️ **A wrong or missing icon NAME fails silently** — `QIcon()` on a nonexistent path
  returns an empty icon and the row renders without a picture. `tests/gui/icon_assets_test.py`
  is the guard.
- ⚠️ **A rendered pixmap does not follow a palette change** — the glyph-script previews
  are dropped and rebuilt on a theme switch, or near-white ink lands on a light menu.

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
are [`docs/telemetry-internals.md`](docs/telemetry-internals.md). Six rules bind code
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
- **Chromium is available headless — use it to LOOK at generated HTML/SVG** rather than
  reading the markup (`--headless --screenshot`, then Read the PNG; add
  `--blink-settings=preferredColorScheme=0` for dark). This caught a dashboard defect
  that existed only in the render while the HTML and the tests were both correct.

### Tests

`*_test.py` under `tests/` mirroring `polyhost/`; **unittest, not pytest**. Use
`scripts/run_tests.py` when a run might hang — it arms a stall watchdog that prints every
thread's stack (`--timeout 240`, and set it **below** whatever will kill the shell).
⚠️ **The suite is ~2350 tests and 65–90 s under xvfb**, so a 60 s timeout fires on a
healthy run: check the wall clock before reading a watchdog dump as evidence of a stall.
GUI tests need `xvfb-run -a`; rendering a widget headless needs `xvfb-run` **and**
`QT_QPA_PLATFORM=offscreen`, for opposite reasons. The rest — the fixture traps, the
headless-render recipes, and the `ControlServer.stop()` deadlock post-mortem — is in
[`docs/testing.md`](docs/testing.md).

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
- **No unit-test CI**, but `codeql.yml` analyses every PR — the one automated reviewer
  here that cannot go quiet.

## Releases

Host releases are **GitHub Releases** (tag `vX.Y.Z`; version in `polyhost/_version.py`),
created by **publishing** — *not* by pushing a tag, which lands on the auto-bump
`[skip ci]` commit and triggers nothing. Use the `polykybd-github-release` skill; the
mechanics, the `release-notes` branch convention and `scripts/publish_release.py` are
in [`docs/releases.md`](docs/releases.md).

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
- **Host and firmware version numbers are NOT kept in lockstep** (they were aligned
  once, at 0.11.0, cosmetically). The number that must move together is
  `__protocol__` / `PROTOCOL_VERSION`.
- ⚠️ **From Claude Code on the web you can neither push tags nor create a release** —
  stage the notes on the branch and hand the user `python scripts/publish_release.py`.
  The same proxy 403s on branch **deletion**, so don't create scratch branches you
  can't clean up.
