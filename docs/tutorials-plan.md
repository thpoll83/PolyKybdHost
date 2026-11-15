# Host-driven tutorials: plan

Status: steps 1 and 2 done in the host (2026-11-15); step 3 needs firmware. Firmware side:
`qmk_firmware/keyboards/polykybd/anim/TUTORIAL.md` and `TUTORIAL_NEXT.md` describe the
first-run (Eden) tutorial, which is compiled into the firmware. This plan is for
tutorials the HOST starts: one YAML file per topic, picked in a dialog, played with the
focus ring, the status OLED and a host-side step panel.

## What already exists

| part | where | protocol |
|---|---|---|
| ring on one key, N times or until cancelled | cmd 47 op 0, `PolyKybd.key_attention()` | 32 |
| ring along a path of layer keys, advanced by the firmware from the active layer | cmd 47 op 2, `services/midi_guide.py` | 34 |
| keymap read (whole buffer) and single-key write | VIA cmd 18 / cmd 5 | VIA |
| status text, "lit set" spotlight, board reveal wave | `anim/tutorial.c`, first-run tutorial only | none |

What does not exist:

- No key, layer or keycode event reaches the host. The raw channel is strictly
  request/response; the only event log is the agent keys' `READ_EVENTS` (cmd 45 op 2).
- The host cannot write text to the status OLED, dim keys or start the reveal.
- The host has no whole-layout write. The firmware answers VIA `SET_BUFFER` (cmd 19,
  `dynamic_keymap_set_buffer_poly`) and `RESET` (cmd 6). ⚠️ `RESET` also wipes the
  user's macros (`KEYMAP_STORAGE.md`).

## Steps

1. **Ring the key the layout editor just changed** (host only, protocol 32). Done in
   `PolyCore.keymap_set`: see *Step 1* below.
2. **Tutorial runner, YAML loader, dialog and step panel**, with ring and guide only
   (host only, protocol 32/34). Steps that need a firmware event advance with the
   panel's Next button. See *Step 2* below.
3. **Cmd 49 TUTORIAL** (firmware protocol 35), with the `add-gated-hid-command` skill.
   Adds status text, spotlight, reveal and armed events. Also takes the first-run
   tutorial's on/off/replay op that `TUTORIAL_NEXT.md` step 3 plans. HIL test with the
   `add-hil-test` skill; the ctnd PR merges before the firmware PR; the host release is
   published before the firmware release.
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
| tray item, dialog, step panel | Help & About → "Tutorials…" (`host.py`), `polyhost/gui/tutorials_dialog.py` |
| shipped scripts | `polyhost/res/tutorials/midi-layer.yaml`, `brightness.yaml` |

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
- `say` is shown in the step panel only. It reaches the status OLED with cmd 49.
- Texts in shipped scripts are English. Extracting them into the translation catalogues
  (`scripts/i18n_strings.py`) is not done yet; a script can give
  `{en: ..., de: ...}` maps.
- `requires`, `spotlight` and `reveal` are not accepted yet: the loader refuses unknown
  fields. They are added with cmd 49.

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
  - point: {layer_key: Fn}
    say: ["Hold Fn", ""]
    text: Hold Fn. The keycaps change to the Fn layer.
  - point: {keycode: TO(7)}
    say: ["Keep Fn held,", "tap the ringed key"]
    wait: {layer: Utility}   # ends with Next until cmd 49
  - point: {keycode: KC_DAUTO}
    say: ["AUTO or MAN", ""]
    wait: {seconds: 8}
```

Step fields:

| field | value | needs |
|---|---|---|
| `say` | two OLED lines, ASCII 0x20..0x7E | cmd 49 op 1; else shown in the panel only |
| `text` | longer text for the host panel | none |
| `point` | `{keycode: ...}`, `{layer_key: NAME}` (the first key of the path to that layer) or `{key: [row, col]}`. A keycode is found in the keymap the keyboard holds, base layer first, so a user's remap is followed. Names: QMK's (`keycodes.h`), PolyKybd's own (`KC_DAUTO`, `KC_BASE`, from `res/preview/legends.json`), `MO(n)`/`TO(n)`/`TG(n)`, or a number | cmd 47 op 0 |
| `guide_to_layer` | a layer name from cmd 35 | cmd 47 op 2 |
| `spotlight` (planned) | `{keys: [...]}` or `{layer_keys: NAME}` | cmd 49 op 2 |
| `reveal` (planned) | `{from: keycode}` | cmd 49 op 3 |
| `wait` | `next`, `{seconds: N}`, `{layer: NAME}`, `{press: keycode}`, `{keycode: ...}` | `layer`/`press`/`keycode` need cmd 49 op 4/5; else they become `next` |

Rules for the loader:

- A script whose `min_protocol` is higher than the keyboard's is listed with a
  "needs firmware" badge and cannot start.
- An unknown field is an error shown in the dialog, not ignored: a typo in `wait`
  would otherwise make a step wait for ever.
- Text goes through `_()` for shipped scripts (`scripts/i18n_strings.py` learns the
  folder). User scripts may give `title: {en: ..., de: ...}`.
- The status OLED shows ASCII only. For a UI language that needs other characters,
  `say` is shown in the panel and the OLED shows the key name only.

## The dialog

Built like `SettingsDialog`: categories on the left; on the right one card per script
with title, summary, step count and the firmware badge. Start opens a small
always-on-top step panel with Back, Next and Skip and the step's `text`. The panel is
required because the OLED fits about 2 x 21 characters. It must work in client mode
over RPC: the runner is in the core, the dialog and panel only send commands.

## Cmd 49 TUTORIAL (step 3)

| op | does |
|---|---|
| 0 INFO | which ops exist, text limits |
| 1 TEXT | two status OLED lines, which half, timeout |
| 2 SPOTLIGHT | 72-bit key mask; every other keycap dims (the first-run "lit set") |
| 3 REVEAL | the board wave from a key (first-run chapter 3) |
| 4 ARM | conditions: key (row, col) pressed, layer N active, keycode K sent |
| 5 POLL | sequence number and the conditions matched since the last poll |
| 6 END | restore text, spotlight and ring |
| 7 FIRST-RUN | on / off / replay / status of the Eden tutorial |

- The firmware reports only matches against the armed conditions, never raw key
  positions, and only while a session is open. It must not work as a key logger.
- If no POLL arrives for about 10 s, the firmware runs END itself, so a host crash does
  not leave the board dimmed.
- TEXT and SPOTLIGHT are read by both halves' renderers, so they are part of the
  `poly_sync_t` contract (`TUTORIAL_NEXT.md` → *Anything the per-half render READS is
  part of the sync contract*). Measure the free bytes in the sync struct before fixing
  the text length.

## Tutorial candidates

| id | steps |
|---|---|
| `midi-layer` | Fn, the key above right Shift (guide), spotlight on the notes |
| `accents` | hold Intl (letters show their variation), tap Ctrl (number row is the picker), pick, type the letter. ⚠️ No spotlight: `INTL_LAYER.md` says nothing may overlay that layer |
| `rgb-settings` | guide to the settings layer, spotlight on the RGB row (`RGB_SETTINGS_ROW.md`), one step per key |
| `brightness` | utility layer, brightness keys, a custom value, then auto (LTR-559), then point at the status OLED brightness row |
| `emoji-search` | emoji layer, type "grin", the result keys. Requires a flashed dictionary (`emoji_search_dict`) |
| `layouts` | the Lang key and the region tabs, in the order of first-run chapter 4 |
| later | shortcut hints while a modifier is held (`HINT_ICONS.md`), macro recording, combos and tap dance, glyph scripts, app overlays and the ESC mark, agent keys, the settings layer |
