# Generic keycap icons — plan v2

**Supersedes [`shortcut-icons-plan.md`](shortcut-icons-plan.md).** That plan is
kept as the record of what was built and measured; its decision **E.3 "curate
`app_icons.yaml` from the misses"** is REVERSED here, and with it most of Part A.1.

---

## The goal, and the one rule it implies

> Shortcut icons reach the keyboard automatically, for any application, with
> **no per-application configuration**.

Two dictionaries are in scope, and nothing else is:

| allowed | what it maps | where it lives today |
|---|---|---|
| the **accelerator** dictionary | an OS accelerator string → our modifier + keycode, fuzzily | `services/shortcut_source/model.py` (`MOD_TOKENS`, `WIN_MOD_TOKENS`, `parse_accel`, `parse_win_accel`) |
| the **label** dictionary | a menu label → an icon concept, and only once shortcuts have been found | `services/shortcut_icons.py` (`LEXICON`, 48 concepts) + `res/shortcut_hints.yaml` |

Everything else must be derived at runtime. **`polyhost/res/app_icons.yaml` —
70 hand-written app-name → catalog-slug entries — is the thing this rule
excludes.** It is not a bad file; it is the wrong shape for the goal, and the
session that produced this document spent hours grooming it before noticing.

⚠️ **The test for any future addition: could a user install an application we
have never heard of and get icons?** If the answer needs a file edit, it is
config and it does not belong.

---

## What changed from v1, and why

v1 treated the program mark's coverage problem as a curation problem: the
catalogs do not carry Microsoft or Adobe, executables are not named after
brands, so a map closes the gap. That is true and it is a treadmill — 70 entries
bought 73% coverage over 151 probed names, and every new application is a 71st
entry.

v2 keeps the program mark but requires it to earn its place with no map. Three
sources, in order, and the order is now the design rather than an accident:

1. **The OS's own icon for the running process.** Exact by construction, needs
   no catalog and no name matching at all.
2. **A catalog match on the app's OS-reported DISPLAY NAME** (see B.2), fuzzy.
3. Nothing. A missing mark is self-evident; a wrong one is a bug nobody can
   explain.

---

## Part A — settled and measured, carried forward

Facts that cost real work to establish and remain true under the new rule.

### A.1 The transport needs no firmware change

`PolyKybd.send_overlays_mru()` takes duck-typed converters: anything exposing
`extract_overlays(modifier) -> {keycode: OverlayData}` plugs in, so a *synthetic*
source built from fetched images rides the existing MRU cache, pool allocation,
ROI/RLE encoders and mapping commit. `device/synthetic_overlay.py` is that seam
and it works.

**A real template always wins** a (modifier, keycode) a synthetic source also
offers — the device layer defers the synthetic one before the upload, so
coverage needs no computation in the core.

⚠️ **A synthetic name whose converter came back `None` must be dropped from the
file list before `send_overlays_mru` sees it**, or `ImageConverter.open()`
returns False for the *whole* send — one undrawable icon costs every hand-made
overlay on the keyboard.

⚠️ **Anything that changes the pixels belongs in the pseudo-filename**, because
`overlay_cache.get_or_allocate` returns an exact key hit **without comparing
bytes**.

### A.2 The 38×38 box on ESC is arithmetic

ESC (U+238B) inks x 2..27, and `copy_overlay_to_buffer` clears a Chebyshev-3
courtyard around the overlay's ink, so the icon's ink must start at x ≥ 31 →
40 is the hard ceiling. **38 ships**, because at 40 a square mark inks the panel
edge to edge and reads as a picture cropped to the keycap (reported from
hardware, 2026-09-14). Left 34 px stay the legend's.

### A.3 The harvest ceiling is measured, not a bug

Linux AT-SPI reaches **classic-menubar applications only** — GTK4 answers
`<VoidSymbol>` for every keybinding it has. The Windows UIA backend is built and
has **never run against a live application**. macOS has no backend. All three
degrade to drawing nothing and logging which it was.

⚠️ This is the real coverage ceiling of the whole feature, and it is far below
the catalog's. Effort spent on name matching is effort not spent here.

### A.4 Binarisation: error diffusion over white

`services/icon_binarise.py` chooses a 1-bit reading per icon from four
conversions and scores them (edge × balance × spread, `MIN_SCORE = 0.30`). The
one to use for OS icons is **`dither_ink`** — Floyd–Steinberg over a **white**
composite, `normalize + sharpness 2.5 + contrast 2.5`, dithered **at the target
size**.

⚠️ **The dither must run at the target size.** Dithering at source and then
downscaling averages the diffusion back into gray.

⚠️ `fontgen_dither` is the existing faithful port of `fontconvert`'s `dither.c`;
go through its public `dither()` entry point, not `_fs`.

Known open regression: **mousepad** scores better under `dither` (0.669) than
under `adaptive` (0.386) and renders worse. A fifth candidate — FS over
**black** — was proposed and not tried; it would also lift `telegram` and
possibly `firefox` back above `MIN_SCORE`.

⚠️ **The per-keycap OLED pixel pitch is in none of the four repos**, so whether a
halftone reads as gray or as speckle cannot be settled here. It needs hardware.

---

## Part B — the problem the no-config rule creates

### B.1 Fuzzy matching cannot bridge the gap the map was closing

The tempting reading of "get fuzzy matches with our icon databases" is that
fuzzy string matching replaces `app_icons.yaml`. It does not, and it is worth
being precise about why, because the two failure modes look alike:

| the map entry | what is wrong with the name | fuzzy fixes it? |
|---|---|---|
| `Sublime_Text` → `sublimetext` | punctuation and case | **yes** — and `normalise()` already does it with no fuzziness at all |
| `gimp-2.0` → `gimp` | a version suffix | **yes**, already handled |
| `winword` → Microsoft Word | a *different word* | **no** |
| `soffice` → LibreOffice | a different word | **no** |
| `pwsh` → PowerShell | an abbreviation | **no** |
| `afterfx` → After Effects | a different word | **no** |

Edit distance between `winword` and `microsoft-word` is not small, and any
threshold loose enough to join them also joins `winword` to `wordpress`. **A
wrong logo is worse than a missing one**, so loosening the threshold is not an
option.

### B.2 The OS knows the display name, and we already parse the files that carry it

This is the finding that makes the no-config rule achievable rather than a
sacrifice. On every platform, the same file the icon comes from **also carries
the application's human-readable name**:

| platform | file already parsed for the icon | the key we do not read yet |
|---|---|---|
| Linux | the `.desktop` entry (`_parse_desktop` returns the whole `[Desktop Entry]` dict) | **`Name=`** |
| Windows | the executable's PE resource table (`_resource_blob` is generic over `type_id`) | **`RT_VERSION` (16)** → `StringFileInfo` → `ProductName` / `FileDescription` |
| macOS | the bundle's `Info.plist` | **`CFBundleDisplayName`** / `CFBundleName` |

So `WINWORD.EXE` yields *"Microsoft Word"*, `soffice` yields *"LibreOffice
Writer"*, `pwsh` yields *"PowerShell"* — from the machine, at runtime, for an
application nobody has heard of. **That string is what to fuzzy-match against the
catalogs**, and it is a far better key than the executable name because it is the
same string the catalog's own `title` field holds.

Cost: `_parse_desktop` already returns it (zero work); the PE side is one more
`_resource_blob` call plus a `StringFileInfo` walk, with the parser that exists
and no new dependency; macOS is one more plist key.

⚠️ **Unverified.** The Linux path is checkable here. The Windows and macOS
backends have never run live at all — `tools/os_icon_probe.py` exists so that is
testable rather than assumed, and it must be extended to print the name it found
beside the icon.

### B.3 The resolution order

```
OS icon for the pid                    exact, no matching, no network
  ↓ (no icon, or it binarises below MIN_SCORE)
catalog match on the OS display name   fuzzy, network, cached
  ↓
nothing                                logged, not guessed
```

⚠️ **The catalog is demoted, not deleted.** v1 asked it first because catalog art
is monochrome by design while an OS icon must survive thresholding. That
reasoning still holds for *legibility* — so the OS icon going first is only
correct because `icon_binarise` can now refuse a bad reading and fall through.
The `MIN_SCORE` gate is what makes the reordering safe; do not remove it.

---

## Part C — the ESC mark must be drawn on ALL modifier variants

Today `program_converter()` returns
`SyntheticConverter({Modifier.NO_MOD: {keycode: data}})` — **one variant**. The
baked overlays put `program_icon:` on every channel of both PNGs, so on a
template-covered app the mark is on ESC under every modifier, and on a
generic app it vanishes the moment you hold Ctrl. That is a visible
inconsistency and it is a bug.

**Fix:** offer the mark on all nine variants. Two things make this nearly free,
both verified against the device layer:

* the mapping is **display → pool**, written per (keycode, modifier) as
  `display_to_pool[display_flat_idx(keycode, modifier)] = pool_slot`, so nine
  display indices may point at **one** pool slot;
* a cache **hit** reuses the slot and uploads nothing.

So the cost is 1 upload and 9 mapping entries, **not** 9 uploads — provided the
program mark's `content_key` is made modifier-independent. Today
`send_overlays_mru` builds it as `(basename, modifier.value, keycode)`
unconditionally, so this needs a small, explicit device-layer change: let a
synthetic source declare its image modifier-invariant.

⚠️ Do not get this by allocating nine slots. The pool holds 600 and one menubar
app already takes ~20 for its shortcuts.

---

## Part D — code inventory

Measured against `origin/main`: 51 files, 10,721 insertions.

### Keep verbatim — this is the feature

| file | why |
|---|---|
| `services/shortcut_source/{__init__,atspi,uia,model}.py` | the harvest, and the accelerator dictionary the goal allows |
| `services/shortcut_icons.py` | the label dictionary + `derive_names()`; resolved **46 of 46** sample labels with no table entry |
| `services/shortcut_overlays.py`, `services/shortcut_fetcher.py` | concept → mask → keys, off the main thread |
| `services/icon_catalog.py` | Material Symbols, subsetted server-side (4.8 KB for 12 names vs a 10.6 MB font) |
| `device/synthetic_overlay.py` | the transport seam (A.1) |
| `services/svg_raster.py`, `services/icon_binarise.py` | rasterise + 1-bit (A.4) |
| `res/shortcut_hints.yaml` | 20 lines, label→concept — an allowed dictionary |
| `tools/shortcut_probe.py`, `tools/os_icon_probe.py` | the only way any of this is checkable off-hardware |

### Rework

| file | change |
|---|---|
| `services/os_app_icon.py` | add the display-name read (B.2) on all three platforms; it becomes the **first** source, not the last |
| `services/app_icons.py` | keep the catalog fetch + render; **drop** the slug map, `candidates()`'s map lookup and the `MDI_PREFIXES` guessing. Key on the OS display name, fuzzily |
| `device/synthetic_overlay.py` | `program_converter` → all nine modifier variants (Part C) |
| `device/poly_kybd.py` | let a synthetic source declare a modifier-invariant image, so Part C costs one upload |

### Drop

| file | why |
|---|---|
| `res/app_icons.yaml` | 70 per-app entries — the thing the rule excludes |
| the `app_icons` half of `res/overlay-mapping.md` and `docs/overlay-fallbacks.md` | describes the map |
| `tests/services/app_icons_test.py` | the map half; the fetch/render tests survive |

### Out of scope, and NOT to be re-litigated on this branch

* **`overlay-mapping.poly.yaml`** — the hand-made overlay set. It predates this
  feature, it is deliberately configured, and a template always wins. The only
  thing worth doing there is a separate bug fix: the LibreOffice group is keyed
  `soffice, soffice.bin, libreoffice, startcenter`, so a desktop that reports
  `writer` / `calc` / `impress` matches nothing and loads **no template at all**.
  That is a missing mapping key, not an icon question. **Its own PR.**

---

## Part E — work breakdown

Each phase ends with something demonstrable; nothing depends on hardware until E4.

* **E0 — branch.** Tag the current head so nothing is lost, reset the branch to
  `origin/main`, land this plan as commit 1.
* **E1 — the OS display name.** `_desktop_name()`, `name_from_pe()`,
  `_macos_name()`; `os_app_icon.app_identity(pid, name) -> (icon_bytes, display_name)`.
  Extend `tools/os_icon_probe.py` to print both. **Checkable on Linux here.**
* **E2 — resolution order (B.3).** OS icon first, catalog on the display name
  second, nothing third. Delete `app_icons.yaml` and the slug map in the same
  commit, so there is never a state where both paths exist.
* **E3 — ESC on all nine variants (Part C).** Device-layer modifier-invariance
  first, then the converter. A test that asserts one pool slot and nine mappings.
* **E4 — port the shortcut half** from the tag, unchanged.
* **E5 — the fifth binarisation candidate** (FS over black) and re-score
  mousepad / telegram / firefox.
* **E6 — Windows + macOS.** `os_icon_probe` on a real machine. Until this runs,
  two of three platforms are untested and the docs must say so.

---

## Part F — what could still fail

* **B.2 is unverified on Windows and macOS.** If `ProductName` turns out to be
  absent or useless on the applications that matter, the no-config rule costs
  coverage rather than buying it. E1 is deliberately first and cheap for exactly
  this reason — measure before porting anything else.
* **The catalogs still carry no Microsoft or Adobe** (measured: zero of Simple
  Icons' 3383 entries). A good display name only helps where a mark exists, so
  Office and Photoshop depend entirely on the OS icon path.
* **A.3 caps the whole feature** far below anything the icon work can reach.
* **A fuzzy match is a wrong-logo risk.** Require a high threshold and let the
  catalog's own 404 reject, exactly as v1's slug guessing did.
