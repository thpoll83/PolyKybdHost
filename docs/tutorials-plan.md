# Host-driven tutorials: plan

Status: steps 1 to 3 done (2026-11-15): host, firmware protocol 35 and rig tests. Firmware side:
`qmk_firmware/keyboards/polykybd/docs/features/tutorial.md` and `keyboards/polykybd/docs/design/tutorial-next.md` describe the
first-run (Eden) tutorial, which is compiled into the firmware. This plan is for
tutorials the HOST starts: one YAML file per topic, picked in a dialog, played with the
focus ring, the status OLED and a host-side step panel.

## What already exists

| part | where | protocol |
|---|---|---|
| ring on one key, N times or until cancelled | cmd 47 op 0, `PolyKybd.key_attention()` | 32 |
| ring along a path of layer keys, advanced by the firmware from the active layer | cmd 47 op 2, `services/midi_guide.py` | 34 |
| keymap read (whole buffer) and single-key write | VIA cmd 18 / cmd 5 | VIA |
| status text, "lit set" spotlight, board reveal wave | `features/anim/tutorial.c`, first-run tutorial only | none |

What does not exist:

- No key, layer or keycode event reaches the host. The raw channel is strictly
  request/response; the only event log is the agent keys' `READ_EVENTS` (cmd 45 op 2).
- The host cannot write text to the status OLED, dim keys or start the reveal.
- The host has no whole-layout write. The firmware answers VIA `SET_BUFFER` (cmd 19,
  `dynamic_keymap_set_buffer_poly`) and `RESET` (cmd 6). ⚠️ `RESET` also wipes the
  user's macros (`keyboards/polykybd/docs/features/keymap-storage.md`).

## Steps

1. **Ring the key the layout editor just changed** (host only, protocol 32). Done in
   `PolyCore.keymap_set`: see *Step 1* below.
2. **Tutorial runner, YAML loader, dialog and step panel**, with ring and guide only
   (host only, protocol 32/34). Steps that need a firmware event advance with the
   panel's Next button. See *Step 2* below.
3. **Cmd 49 HOST TUTORIAL** (firmware protocol 35): status text, spotlight, reveal and
   key/layer conditions. See *Cmd 49* below. Rig tests in polykybd-ctnd; the ctnd PR
   merges before the firmware PR; the host release is published before the firmware
   release. The first-run tutorial's on/off/replay (`keyboards/polykybd/docs/design/tutorial-next.md` step 3) is a
   separate change, with a row in the tray's Maintenance menu.
4. **Whole-layout load and reset in the layout editor**, written with `SET_BUFFER` in
   chunks, followed by the reveal (op 3).
5. **Docs page** on polykybd.org, after the release that has step 3
   (`update-polykybd-docs` skill).

## Step 1: ring after a key edit

`PolyCore.keymap_set` writes the key and, when the write succeeded, rings that key
once (cmd 47 op 0, count 1). It rings only when:

- the firmware supports `key_attention` (protocol 32+), and
- the edited layer is the keyboard's default layer (cmd 22). On any other layer the
  keycap still shows the old legend until that layer is held, so a ring there would
  point at the wrong legend. Once cmd 49 reports the active layer, this check can use
  it instead.

The ring goes through `_manual_ring`, so it increments `_manual_ring_seq` and a queued
MIDI guide cancel does not stop it. A refused ring (a key without a display) is logged
and does not fail the write. `polyctl keymap set` uses the same core method, so a
write from the command line rings too.

## Step 2: what is built

| part | file |
|---|---|
| YAML loader and checks | `polyhost/services/tutorials/loader.py` |
| one run (rings, steps, `seconds` timer) | `polyhost/services/tutorials/runner.py` |
| core methods, `tutorial` event, 0.5 s periodic | `PolyCore.tutorials_list`, `tutorial_start`, `tutorial_action`, `tutorial_state` |
| control socket | `tutorials.list`, `tutorial.start`, `tutorial.action`, `tutorial.state` |
| command line | `polyctl tutorial list / start ID / next / back / stop / status` |
| tray item, dialog, step panel | top-level "Tutorials…" (`host.py`), `polyhost/gui/tutorials_dialog.py` |
| shipped scripts | `polyhost/res/tutorials/*.yaml`, listed under *Shipped tutorials* below |

How a run behaves:

- One run at a time. Starting another stops the first.
- A ring is 12 ripples, 2.5 s apart (the MIDI guide's values), not "until
  cancelled". A host that stops without a cancel leaves the keyboard ringing for about
  30 s at most.
- The run's rings count as manual ring requests (`_manual_ring_seq`), so a queued MIDI
  guide cancel does not end them. While a tutorial runs, the automatic MIDI guide does
  not start.
- The keymap (cmd 35, cmd 22, VIA cmd 18) is read once per run, at the first step that
  points at a key by keycode or layer.
- Closing the step panel stops the tutorial.

Limits of step 2:

- The host can read only layers 0..8 (the five layouts, Fn, Numpad, Utility, MIDI).
  A key on the settings, language, Intl or emoji layer is found by keycode only if the
  same keycode is also on a readable layer; otherwise the script gives `{key: [row, col]}`,
  which does not follow a user's remap.
- On firmware before protocol 35 (and on the DOOM monolith, which NACKs cmd 49) `say`
  is shown in the step panel only, and `spotlight`, `reveal` and event waits are left
  out.
- Texts in shipped scripts are English. Extracting them into the translation catalogues
  (`scripts/i18n_strings.py`) is not done yet; a script can give
  `{en: ..., de: ...}` maps.
- `requires` is not implemented: a script cannot yet say it needs, for example, a
  flashed emoji dictionary.

## Script format

YAML only. A file someone puts in a folder must not run code in the daemon, and YAML
strings can be extracted into the translation catalogues.

- Shipped: `polyhost/res/tutorials/*.yaml`.
- User: `<config dir>/tutorials/*.yaml`, beside `settings.yaml`. A user file with the
  same `id` as a shipped one replaces it.

```yaml
id: brightness
category: light            # layers | languages | light | emoji | editor | other
title: Display brightness  # or {en: ..., de: ...}
summary: Set a fixed brightness, step it up and down, or let it follow the light.
min_protocol: 32
steps:
  - guide_to_layer: Utility
    say: ["Hold Fn, then tap", "the ringed key"]
    wait: {layer: Utility}   # ends with Next until cmd 49
  - point: {keycode: KC_DAUTO}
    say: ["AUTO or MAN", ""]
    wait: {seconds: 8}
```

Step fields:

| field | value | needs |
|---|---|---|
| `say` | one or two status-display lines, ASCII 0x20..0x7E, each at most 128 px in the 15 px status face (the loader measures it), both together at most 59 bytes | cmd 49 TEXT; else shown in the panel only |
| `text` | longer text for the host panel | none |
| `point` | `{keycode: ...}`, `{layer_key: NAME}` (the first key of the path to that layer) or `{key: [row, col]}`. A keycode is found in the keymap the keyboard holds, base layer first, so a user's remap is followed. Names: QMK's (`keycodes.h`), PolyKybd's own (`KC_DAUTO`, `KC_BASE`, from `res/preview/legends.json`), `MO(n)`/`TO(n)`/`TG(n)`/`OSL(n)`, or a number | cmd 47 op 0 |
| `guide_to_layer` | a layer name from cmd 35. The last key of the path is one that stays on the layer (`TO`, `TG`) when the keymap has one, not an `OSL` that leaves it after one key | cmd 47 op 2 |
| `spotlight` | a list of keys in the `point` forms, plus `{layer: NAME}` (every key with a keycode on that layer); `[]` darkens all but the ringed key. Applies to that step only | cmd 49 SPOTLIGHT |
| `reveal` | `{from: <point>}`: the wave from that key lights the dark keys and ends the spotlight. A reveal step keeps the spotlight of the step before | cmd 49 REVEAL |
| `wait` | `next`, `{seconds: N}`, `{layer: NAME}`, `{press: keycode}`, `{key: <point>}` (that key position is pressed, whatever it types then: the macro slot picker swallows keys and reports the base layer's keycode), `{leave: NAME}` (the keyboard is no longer on that layer, read from POLL) | `layer`/`press`/`key`/`leave` need cmd 49 ARM/POLL; else they become `next` |

A step after `guide_to_layer: NAME` with `wait: {layer: NAME}` is about that layer
when the guide's last key stays on it (`TO`, `TG`). This lasts until a step that
waits for a press of `KC_BASE` or of a layer key, or for `leave`. When POLL reports
that the keyboard left the layer (the user took a one-shot key, or pressed another
layer key), the runner goes back to the guide step. A layer that is held (`MO`) or
entered on purpose with an `OSL` is never needed: releasing it is part of the
tutorial.

Layer names are cmd 35's for the stored layers. The layers the keyboard compiles in
(`Settings`, `Language`, `Intl`, `Emoji` on split72) cannot be read over HID: the
runner takes their keys from `res/preview/board.json` (`fixed_layers`, written by
`scripts/export_preview_data.py`). It uses them only when the export's matrix is the
keyboard's and the keyboard stores as many layers as the export says. On split42
those steps ring nothing and say why.

Rules for the loader:

- A script whose `min_protocol` is higher than the keyboard's is listed with a
  "needs firmware" badge and cannot start.
- An unknown field is an error shown in the dialog, not ignored: a typo in `wait`
  would otherwise make a step wait for ever.
- Planned: shipped scripts' texts go into the translation catalogues
  (`scripts/i18n_strings.py` learns the folder). Today any script may give
  `title: {en: ..., de: ...}` maps.
- The status OLED shows ASCII only. For a UI language that needs other characters,
  `say` is shown in the panel and the OLED shows the key name only.

## The dialog

Built like `SettingsDialog`: categories on the left; on the right one card per script
with title, summary, step count and the firmware badge. Start opens a small
always-on-top step panel with Back, Next and Stop and the step's `text`. The panel is
required because the status display fits two short lines (128 px each). It must work in client mode
over RPC: the runner is in the core, the dialog and panel only send commands.

## Cmd 49

The wire format and the firmware side:
`qmk_firmware/keyboards/polykybd/docs/protocol/protocol-history.md` → *v35*. What the host does with it:

- `TutorialRun.start()` sends INFO. An answered INFO switches cmd 49 on for the run;
  a refused one (DOOM monolith) leaves the run ring-only.
- Each step sends TEXT (`say`, or empty), SPOTLIGHT (the step's keys plus the ringed
  ones, or off), REVEAL, and ARM with the step's event wait (or none).
- `PolyCore._tutorial_periodic` (0.5 s) calls `poll()`: POLL feeds the keyboard's 10 s
  watchdog and moves on when condition 0 matched. A finished or stopped run sends END.
- The keyboard reports matches against the armed conditions only, never raw key
  positions, and only while a session is open.
- The slave learns TEXT, SPOTLIGHT, REVEAL and END as the forwarded report, not
  through `poly_sync_t` (firmware `keyboards/polykybd/docs/protocol/split-sync.md` → *Host state goes to the slave as
  the report*).
- RAM: +108 B in the pack firmware (main SRAM free 6056 → 5948 B, local gcc 13.2); not
  in the DOOM monolith.

## Shipped tutorials

| id | steps |
|---|---|
| `midi-layer` | Fn, the key above right Shift (guide), spotlight on the notes |
| `brightness` | guide to Utility, the preset row, - and +, AUTO/MAN, back to typing |
| `accents` | hold Intl (guide, `MO`), press e, tap Ctrl (the picker), pick an accent, the remap key. The spotlight keeps the picker row and Ctrl lit; `keyboards/polykybd/docs/features/intl-layer.md`'s "nothing may overlay this layer" is about app overlays |
| `rgb-lighting` | guide to Settings, on/off, effects, hue and saturation, brightness and speed, back to typing |
| `emoji-search` | guide to Emoji, the mode key, type a word (no `say`, so the status display shows the query), results, Clear/Space/Backspace, back to typing |
| `keyboard-language` | the Lang key, the continent row, tap a language (`leave`) |
| `base-layouts` | guide to Settings, `KC_L0`..`KC_L4`, back to typing |
| `record-macro` | Fn, then the `OSL(Utility)` key twice (one-shot, then REC), the slot picker (`key` wait on M0), record (no `say`, so the status display shows REC), stop, play |

Later: shortcut hints while a modifier is held (`keyboards/polykybd/docs/display/hint-icons.md`), combos and tap
dance, glyph scripts, app overlays and the ESC mark, agent keys.
