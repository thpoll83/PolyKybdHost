---
name: polykybd-kofi-post
description: Write a ko-fi / supporter post announcing a PolyKybd feature that has landed, together with its visuals — an animated GIF of the mechanism and a composed hero still — all rendered from the real firmware sources rather than mocked up. Use when asked to "write a ko-fi post", "prepare a post about <feature>", "announce this", "make a post + gif for the new X", or after a feature PR merges and the change is worth telling supporters about. NOT for GitHub release notes (that's polykybd-release-notes), NOT for the documentation site (that's update-polykybd-docs), and NOT for a feature that is still unmerged or untested on hardware.
---

# Ko-fi post for a landed feature

Three deliverables, in this order: the **post**, an **animated GIF** of the
mechanism, and a **hero still** for the top of the post (and for anywhere that
shows a preview image rather than playing a GIF).

The house rule for every visual: **render it from the firmware sources**. Board
geometry from the KLE, glyphs from the generated fonts/tables via the demo
pipeline in `tools/`. A hand-drawn mock drifts the moment a keymap moves, and it
misrepresents the product in the one place people look closely.

## 0. Establish what actually landed

Never write from the branch you were working on — write from what merged.

```bash
cd /home/user/qmk_firmware && git log --oneline -1 && git status --short
gh_pr=<N>   # the merged PR
```

Read the merged PR body and the commit messages. Two things to pin down, because
the post lives or dies on them:

- **The problem the feature solves**, stated concretely. ("French wants è é ê at
  once, and the picker can only give one accent per key.")
- **The exact gesture**, in the order a user performs it.

Confirm the feature was tested on hardware. If it wasn't, stop and say so — a
supporter post about something unverified is the wrong thing to ship.

## 1. Draft the post

Established shape (see the Intl picker and Intl remap posts):

1. **Title** — concrete, not a feature name. "Three accents, three keys — the
   Intl layer learns to rearrange itself".
2. **Hero image** immediately under the title.
3. **What you could already do**, in two or three sentences, so the new thing has
   something to be new *against*.
4. **"Which was fine until …"** — the specific case that broke. Name a real
   language, app or workflow.
5. **The gesture**, plainly. Bold the keys.
6. **The GIF**, with alt text that describes what it shows.
7. **Edge cases worth knowing** — what is *not* covered, per-variant differences,
   how to undo it. Users hit these first.
8. **`---` then "under the hood"** — one or two genuinely interesting mechanisms,
   named at the level of "what and why", not code. Near-misses are good material
   (a silent buffer ceiling, a byte that reads 0x00 where you expected 0xFF).
9. Close with where the code lives, and `☕`.

Voice: informative over funny, specific over sweeping. Real numbers (549
variations, 12 punctuation keycodes, 24 bytes of `.bss`). No marketing adjectives.
Never claim a capability the firmware doesn't have.

Write to a scratch file — the post is not committed to any repo.

## 2. The animated GIF

Check whether a demo driver already exists for the layer before writing one:

```bash
ls /home/user/PolyKybdHost/tools/*_demo.py
```

`intl_picker_demo.py`, `intl_remap_demo.py`, `emoji_demo.py`, `lang_demo.py`,
`glyph_script_demo.py` cover most layers. Re-run the relevant one — it reads the
keymap, so a new key appears without a code change:

```bash
cd /home/user/PolyKybdHost
.venv/bin/python tools/intl_remap_demo.py --still     # → tools/out/
```

If the feature needs a new driver, model it on `intl_remap_demo.py` and mirror
`render_key()`'s rules exactly — which keys blank, which stay lit, what inverts.
Inversion is **rendered**, never `kdisp_invert()`.

**Look at the output.** Open the GIF's key frames and check them against what the
firmware does; do not infer from the code you just wrote.

## 3. The hero still

`tools/intl_remap_hero.py` is the pattern — see **Composed stills** in
`tools/README.md` for the full set of composition gotchas (keying out the board
background, 3× supersampling for curves, glyphs sitting left in the panel, fonts
available on the box).

What makes a hero still work rather than being a second copy of the GIF:

- **Show the outcome, not the mechanism.** The GIF already shows the gesture.
- **Anchor it in real use** — a sentence someone would actually type, a real app.
- **Connect the abstract to the hardware.** Colour-matching a letter to its keycap
  and drawing a curve between them is what makes it readable at thumbnail size.
- **Assert the content against the generated tables** so the image cannot drift.

## 4. Deliver

Send the post file and the images with `SendUserFile`. State plainly:

- which parts are firmware-rendered and which are composed typography
- what you verified by looking versus by reading
- that the images are scratch unless the generator was committed

## Pitfalls

- **Don't change more than asked on a visual.** If a requested change (say, a
  cursive subline) *needs* compensating changes (larger, brighter, more canvas),
  make them a separate, named option rather than folding them in silently — a
  `--style` preset with the compensation isolated lets the user choose. This cost
  a round on the Intl remap hero.
- **Don't commit generated images into `tools/out/`** — it is git-ignored, and
  post assets belong wherever the post is published. GIFs that the *docs site*
  uses are a different case: those are committed to `polykybd-docs/public/`.
- **A ko-fi post is not release notes.** Release notes enumerate every change in a
  version; this covers one feature narratively. Don't merge the two jobs.
- **Don't reuse a stale GIF.** If the feature added a key, the old GIF renders the
  board without it — regenerate every animation the post shows, not just the new one.
- **The docs site is a separate deliverable.** A post is not documentation; run
  `update-polykybd-docs` as well if the feature is user-facing.
