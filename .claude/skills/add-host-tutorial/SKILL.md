---
name: add-host-tutorial
description: Write, change or fix a PolyKybdHost tutorial script (polyhost/res/tutorials/*.yaml) — the step-by-step guides in Help & About → Tutorials… that ring keys, put two lines on the status displays and darken the other keys (cmd 47 / cmd 49). Use when asked to "add a tutorial for X", "write a guide for the Y layer", "the Z tutorial rings the wrong key / gets stuck / goes back", or after a keymap change that moves a key a tutorial points at. Covers reading the firmware feature first, the YAML fields, the 128 px status-line check, the fixed layers (Settings, Language, Intl, Emoji), which waits to use, and a dry run of every step against the default split72 keymap. NOT for the runner or the cmd 49 protocol themselves (docs/tutorials-plan.md, the add-gated-hid-command skill) and NOT for the first-run tour in the firmware.
---

# Add or fix a host tutorial

A tutorial is one YAML file. The field reference is
[`docs/tutorials-plan.md`](../../../docs/tutorials-plan.md) → *Script format*; the
runner is `polyhost/services/tutorials/runner.py`. Shipped scripts are in
`polyhost/res/tutorials/`; a user's are in `<config dir>/tutorials/`.

## 1. Read the feature on the keyboard side first

Every bug found in the first eight scripts came from the keyboard doing something the
script did not expect. Before writing a step, find in `qmk_firmware/keyboards/polykybd`:

- **Which layer the keys are on**, in `split72/keymaps/default/keymap.c`. Layers 0..8
  are stored and the host reads them over HID. Layers 9..12 (`_SL` Settings, `_LL`
  Language, `_ADDLANG1` Intl, `_EMJ` Emoji) are compiled in: the host reads them from
  `res/preview/board.json` → `fixed_layers`, on split72 only. Their names in a script
  are `Settings`, `Language`, `Intl`, `Emoji`.
- **How the user enters and leaves that layer.** `TO`/`TG` stay on, `MO` only while
  held, `OSL` for one key. A custom key can also switch layers (`KC_LANG` turns on
  `_LL`; picking a language turns it off).
- **What the status display shows during the step.** The tutorial text has priority
  over the macro-recording screen and the emoji query (`oled_helper.c`). A step where
  the user must read the display has no `say`.
- **Whether a mode swallows key events.** The macro slot picker does, and reports the
  base layer's keycode, so a `press` wait on `QK_MACRO_0` never matches there.

## 2. Write the steps

| what the step does | use |
|---|---|
| go to a layer that stays on | `guide_to_layer: NAME` + `wait: {layer: NAME}`. The guide takes a `TO`/`TG` path over an `OSL`. Leaving that layer later sends the user back to this step |
| go to a held layer (Intl) | `guide_to_layer` + `wait: {layer: NAME}`. Releasing it is normal, so no step goes back |
| enter with a one-shot on purpose (REC) | `point: {keycode: OSL(7)}` and a `press` wait on the key after it |
| a key that has a keycode | `point: {keycode: ...}` (found in the keymap, base layer first) |
| a key whose keycode the mode hides | `wait: {key: {keycode: ...}}` (arms the position) |
| a step that ends when a layer closes | `wait: {leave: NAME}` |
| show only some keys | `spotlight: [...]`; add the keys the user must see (an inverted Ctrl) |
| a step that needs the emoji layer's tab or search mode | `emoji_mode: search` (or `tab`), and `min_protocol: 37`. Never ask the user to press the mode key: it toggles, so the press switches a user who was already in that mode out of it |
| leave the layer at the end | `point: {keycode: KC_BASE}` + `wait: {press: KC_BASE}`, then a `reveal` step |

`say` is one or two lines, ASCII, at most 128 px each in the status face and 59 bytes
together. The loader refuses a longer line and names it. Measure while writing:

```bash
.venv/bin/python -c "from polyhost.services.tutorials import loader as L; print(L.say_width('Hold Fn, then tap'))"
```

## 3. Check

```bash
# every shipped script loads, and the error list names any refused field
.venv/bin/python -c "from polyhost.services.tutorials import loader as L; f, e = L.load_all()[:2]; print(sorted(f), e)"
# every ring, guide, spotlight and wait resolves on the default split72 keymap
.venv/bin/python .claude/skills/add-host-tutorial/simulate_tutorials.py <id> [--firmware DIR]
.venv/bin/python -m unittest tests.services.tutorials_loader_test tests.services.tutorials_runner_test
```

`simulate_tutorials.py` exits 1 on a load error or a step with `err=` set. Read its
output step by step: the guide path should end on the key the text names, and an
`arm` list should be empty only on steps that end with Next or seconds. Add a new id to
`test_every_shipped_script_loads` in `tests/services/tutorials_loader_test.py`.

Then list the new script in `docs/tutorials-plan.md` → *Shipped tutorials*.

## Pitfalls

- ⚠️ **A guide into a layer must end on a key that stays.** The first brightness script
  rang `TO(7)` by keycode; a user took Fn + Esc (`OSL(Utility)`) instead, the step
  passed, and after one key the spotlit keys showed base-layer letters (2026-11-16,
  PolyKybdHost#918).
- ⚠️ **Through `TO(Utility)` REC records on Utility**, where the keys are macros and
  media keys. Recording is built for the one-shot route: Fn + top-left twice.
- **A spotlight of `[]` darkens everything but the ringed key.** On the Intl picker
  step that hid the inverted Ctrl, the only sign that the picker is open.
- **A `key` wait's value is a Point.** `state()` converts it for the control socket;
  keep any new wait value JSON-safe (the simulator runs `json.dumps` on each step).
- **Fixed-layer steps do nothing on split42.** The runner says why in the panel and
  the step ends with Next; write the text so it still makes sense there.
- **Re-run `scripts/export_preview_data.py`** after a firmware change to layers 9..12;
  otherwise the runner points at the old positions. `--check` says whether it is stale.
