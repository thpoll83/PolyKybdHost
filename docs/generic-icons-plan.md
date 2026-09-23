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

## ⚠️ A floor must not decide a contest (2026-09-23, from hardware)

`icon_binarise.MIN_SCORE` (0.08) answers one question: *may we draw this when
there is nothing else?* For a while it also **ended** resolution — the OS icon
was read first and clearing the floor returned it immediately.

On macOS that meant the catalogs and the shipped marks were **unreachable**.
Every system `.icns` clears 0.08 comfortably while still reading as mush on the
panel: a representative rounded plate measures **0.117**. Four new marks were
drawn, previewed, reviewed, merged and flashed, and the keyboard looked
identical — the change was inert, and only a hardware round said so.

`program_overlay` now ranks every candidate, the OS icon included, and the floor
only gates usability. Two things that fall out of it:

- **Ranking by score alone is still not enough.** `score()` rates a majority-ink
  mark by its *holes*, and rates them well: `si:safari` scores **0.610** read
  inside-out against `mdi:apple-safari`'s **0.532** compass read normally, so
  score-ranking picks the solid disc. The sort key is
  `(read_the_right_way_up, score)` — polarity outranks score, as a preference
  rather than a veto, so an inverted mark still wins when it is the only one.
- ⚠️ **This module carries TWO crop conventions and they are not comparable.**
  `choose()` scores a mask fitted to its ink; the SVG silhouette path scores a
  padded panel slice. `si:safari` reads **0.192 padded / 0.610 tight**, because
  the padding drops it under `MAX_LIT` so `score()` stops inverting it. Any
  cross-source comparison must re-score through one of them (`mark_score`).

⚠️ **Measured and REFUTED — do not re-propose:** that a dark plate's inverse
stays clear of the bounding-box border while a filled silhouette's does not.
A dark circular plate with a glyph knocked out (lit 0.723 / enclosed 0.200 /
border 0.800) and a filled disc with a hole (0.737 / 0.158 / 0.842) are the
**same picture**, with `si-safari` between them at 0.727 / 0.188 / 0.812. No
geometric measure separates them, because semantically there is nothing to
separate.


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

### B.2 The OS knows the display name — measured, 14 of 16

This is the finding that makes the no-config rule achievable rather than a
sacrifice. On every platform, the same file the icon comes from **also carries
the application's human-readable name**:

| platform | file already parsed for the icon | the key we do not read yet |
|---|---|---|
| Linux | the `.desktop` entry (`_parse_desktop` returns the whole `[Desktop Entry]` dict) | **`Name=`** |
| Windows | the executable's PE resource table (`_resource_blob` is generic over `type_id`) | **`RT_VERSION` (16)** → `StringFileInfo` → `ProductName` / `FileDescription` |
| macOS | the bundle's `Info.plist` | **`CFBundleDisplayName`** / `CFBundleName` |

**The mechanism is that a display name kebabs straight onto mdi's own spelling.**
`kebab("Microsoft Word")` is `microsoft-word`; `winword` never could be. Measured
against both CDNs, 2026-09-15, using the *display* name only and no map:

| exe | display name | resolved |
|---|---|---|
| `WINWORD.EXE` `EXCEL.EXE` `POWERPNT.EXE` `OUTLOOK.EXE` `ONENOTE.EXE` | Microsoft Word / Excel / PowerPoint / Outlook / OneNote | `mdi:microsoft-*` |
| `msedge.exe` `Teams.exe` `devenv.exe` | Microsoft Edge / Teams / Visual Studio | `mdi:microsoft-*` |
| `Code.exe` | Visual Studio Code | `mdi:visual-studio-code` |
| `pwsh.exe` | PowerShell | `mdi:powershell` |
| `soffice.bin` `vlc.exe` `obs64.exe` | LibreOffice / VLC media player / OBS Studio | `si:*` |
| `Acrobat.exe` | Adobe Acrobat | `mdi:adobe-acrobat` |
| `Photoshop.exe` `AfterFX.exe` | Adobe Photoshop / After Effects | **nothing** |

**14 of 16** — and that set is precisely what `app_icons.yaml`'s 70 entries
existed to cover. Adobe beyond Acrobat stays uncovered either way (mdi holds only
`adobe` and `adobe-acrobat`, as v1 measured), so Photoshop depends on the OS icon.

Cost: `_parse_desktop` already returns the name (zero work); the PE side is one
more `_resource_blob` call plus a `StringFileInfo` walk, with the parser that
exists and no new dependency; macOS is one more plist key.

#### ⚠️ A display name is as often a GENERIC PHRASE as a brand

Measured over this container's 15 `.desktop` entries, the Linux `Name=` is not
uniformly better than the exec stem — it fails in the opposite direction:

| exec stem | `Name=` | |
|---|---|---|
| `yelp` | **Help** | generic |
| `xdg-desktop-portal-gtk` | **Portal** | generic |
| `gnome-text-editor` | **Text Editor** | generic |
| `python3.11` | **Python (v3.11)** | worse — `normalise` does not strip `(v3.11)` |
| `libreoffice` `vim` `zenity` `mousepad` | LibreOffice / Vim / Zenity / Mousepad | fine |

And a generic phrase **does** resolve: `mdi:help` and `mdi:settings` both return
200. So matching a display name against bare mdi would put a question mark on
GNOME Help and a gear on anything called "Settings" — a wrong icon, with no
config left to stop it.

⚠️ **`candidates()` does NOT produce the winning name today, and the reason is
easy to miss.** It appends the `microsoft-` / `adobe-` prefixes to whatever it is
given, so a display name that already carries the prefix comes out doubled:
`candidates("Microsoft Word")` → `mdi:microsoft-microsoft-word`. The measured win
above used `kebab()` directly. **A display name needs the BARE mdi form**, which
is exactly the form the module's existing rule refuses.

✅ **The rule that admits it without the generic trap is "multi-segment only":
take the bare mdi name only when `kebab()` yields a hyphenated one.** Measured,
2026-09-15, over 14 real display names and 10 generic ones:

| | result |
|---|---|
| wins resolved | **13 / 14** — every `microsoft-*`, `visual-studio-code`, `adobe-acrobat`, plus LibreOffice / VLC / OBS via Simple Icons |
| generic names that resolved to a wrong icon | **1 / 10** |

The one loss is **PowerShell**: `si:powershell` is 404 and `mdi:powershell` has no
hyphen, so it is refused. It costs nothing in practice — `pwsh.exe` has an icon
resource, and the OS icon is the FIRST source.

⚠️ **The one leak falsifies a claim made earlier in this document.** "Simple Icons
is brand-only, so it rejects generic words by construction" is **not true**:
`si:help`, `si:portal` and `si:texteditor` are 404, but **`si:files` is 200**, so
GNOME Files would get some unrelated brand's mark. Brand-only is a strong
tendency, not a guarantee, and no hyphen rule can help — the leak is on the
Simple Icons side. Treat it as residual risk to measure again with a wider
generic sample, not as a solved problem.

### B.3 The resolution order

```
built-in PolyKybd mark                 only for PolyHost's own windows
  ↓ (any other app)
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

The first rung is not per-application config in the sense of the rule above:
it covers exactly one app, ours, whose OS icon is by construction the Python
interpreter's. `handler/own_process.py` decides which windows are ours from the
process command line (`-m polyhost`), and `app_icons.POLYKYBD_KEYS` draws the
mark from the tray icon's key grid, checked against `res/icons/pcolor.svg` by
`tests/services/app_icons_test.py`.

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

Everything below lives on **`feature/stoic-shannon-ofkjo9`** (PR
[#235](https://github.com/thpoll83/PolyKybdHost/pull/235), head `7798124`), which
stays open and untouched as the source to port from. Measured against
`origin/main`: 51 files, 10,721 insertions.

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

## Part D.1 — one Win32 binding, not two

⚠️ **`services/os_app_icon._windows_exe()` and `handler/win_process.py`
independently bind the same three Win32 calls** — `OpenProcess`,
`QueryFullProcessImageNameW`, `CloseHandle` — with the same
`PROCESS_QUERY_LIMITED_INFORMATION` constant and the same 32768 buffer. They
differ only at the ends: `win_process` starts from an HWND and returns the
basename, `os_app_icon` starts from a PID and returns the full path. The shared
middle is "PID → full image path".

`win_process.py` arrived on `main` with PR #238 (`fix(windows): resolve the
focused app's name without WMI`), after this branch was cut, so this is a
collision neither side could have seen. **It caught a real defect here**: the
copy in `os_app_icon` set no `argtypes`/`restypes`, so ctypes returned
`OpenProcess`'s HANDLE as `c_int` and truncated it on 64-bit. Fixed in place,
and pinned by a test that fails when the `restype` is removed.

⚠️ **Fixing the duplication is NOT part of this PR.** Unifying them means moving
the loader somewhere a service and a handler may both import, and a service
importing a handler is backwards. That is a change to code this branch does not
own, on a layering question worth deciding on its own. Do it separately — and
note the repo has been bitten by exactly this before: five pieces of plumbing
are shared implementations *because* a hand-written copy had already drifted.

---

## Part E — work breakdown

Each phase ends with something demonstrable; nothing depends on hardware until E4.

* **E0 — branch.** ✅ Done. `feature/generic-icons-no-config`, cut fresh from
  `origin/main`, this plan as commit 1. PR #235 is left open and untouched, so
  the old work is never at risk and is the thing E4 ports from. (The git proxy
  refuses `refs/tags/*` from a web session, so an open branch is the only safety
  net available.)
* **E1 — the OS display name.** ✅ Done. `AppIdentity(icon, icon_path, names)`
  from one resolution per platform, so the mark and the caption cannot describe
  two different applications; `version_strings()` / `names_from_pe()` reach
  `RT_VERSION` with the resource walker that already existed. `os_icon_probe.py`
  prints the names and what each would resolve to. 17 tests where the module had
  none, mutation-swept 8/8.
  * ⚠️ **Found while doing it: `_linux_icon_name` picked the WRONG desktop entry
    for Mousepad.** `org.xfce.mousepad.desktop` and
    `org.xfce.mousepad-settings.desktop` share an `Exec` stem *and* an `Icon=`,
    so readdir order decided and the settings dialog won — invisible for as long
    as only the icon was read. Fixed with a reverse-DNS rank above the `Exec`
    one, which also resolves `org.gnome.gedit` for a window calling itself
    `gedit` with no `/proc` lookup at all.
  * ⚠️ **Still unverified: the Windows and macOS READS.** The parse is tested
    against a synthetic linker-shaped blob; whether a real `WINWORD.EXE` carries
    a usable `FileDescription` is what the probe is for.
* **E2 — resolution order (B.3).** ✅ Done. `program_overlay` reads the OS icon
  first and falls through to the catalog only when there is none or it scores
  below `MIN_SCORE`; the catalog is keyed on the display names, then on the
  executable name. `app_icons.yaml` was never ported to this branch and
  `slug_map_path` / `load_slug_map` / `slug_for` are gone, so the two paths never
  coexisted. 11 tests, mutation-swept 8/8 (including the order reversal itself
  and the `MIN_SCORE` gate).
  * **It takes an `AppIdentity`, not a pid**, which is what makes E1's "one
    resolution" real: `program_overlay(app_name, identity, …)` reads the icon and
    the display names out of the same lookup, so the mark and whatever captions
    it cannot describe two applications — and on Windows that lookup opens the
    process and parses its resources, which is not a thing to do twice per window
    change. `identity=None` degrades to the executable name alone.
  * **Driven end to end on this container**: `mousepad` resolves `os:org.xfce.
    mousepad.png` (206 ink px — the E1 desktop-entry fix holding), `gedit`'s OS
    icon scores under the gate and falls through as designed, and
    `libreoffice-writer` reaches `si:libreofficewriter` (1019 px) with no map
    entry of any kind.
* **E3 — ESC on all nine variants (Part C).** Device-layer modifier-invariance
  first, then the converter. A test that asserts one pool slot and nine mappings.
* **E4 — port the shortcut half** from the tag, unchanged.
* **E5 — the fifth binarisation candidate** (FS over black). ✅ Done, and the
  answer is **NO — do not add it.** It was implemented, scored and rendered
  against every real icon on the dev container (9 LibreOffice marks, Mousepad,
  the Debian spiral, the Ubuntu wordmark), and the measurement refutes the
  proposal outright. Evidence sheet: [`images/binarise.png`](images/binarise.png).
  * **It wins on score and loses on sight, which is the mousepad failure
    repeated six times.** `dither_black` takes the top score on six icons —
    math 0.879, base 0.829, writer 0.827, impress 0.715, calc 0.582, debian
    0.633 — and on five of those the render it replaces is *clean line art*
    (`adaptive`: math's crisp √x, writer's ruled lines, calc's spreadsheet
    grid). What `dither_black` draws instead is a halftone field. Shipping it
    would trade five good renders for speckle and gain nothing; debian is a wash.
  * ⚠️ **It does NOT fix mousepad**, which is the thing E5 was for. `dither`
    still wins there at 0.669 against `adaptive`'s 0.386, unchanged, and
    `adaptive` is still visibly the better render. telegram and firefox are not
    installed here, so their half is still unmeasured — but the proposal's
    premise is already dead on the icons that ARE measurable.
  * **The real defect is `score()`, and the obvious repair was TRIED and
    refuted.** `detail = edges/lit` is near 1.0 for a dither field, because
    every lit pixel in a halftone touches an unlit one — the term meant to
    reward line art is maximised by texture. The separating term that suggests
    itself is *cohesion* (the share of lit pixels with a lit 4-neighbour), on
    the theory that a halftone is isolated pixels. **Measured: it does not
    separate them** — 0.78–1.0 across every conversion and every icon, because
    a Floyd–Steinberg field at ~50% density is not a checkerboard and its
    pixels do touch. No term was shipped.
  * **So the open question is unchanged and better stated**: `score()` cannot
    tell halftone texture from detail, and the fix is not a fifth candidate and
    not cohesion. ⚠️ Per `score()`'s own docstring, extend it by finding an icon
    it gets wrong and adding the term that separates *that* — do not tune the
    constants. The pixel pitch of the real panel is still in none of the four
    repos, so whether a halftone reads as gray or as speckle on hardware
    remains the one thing that would settle whether `dither` deserves its wins
    at all.
* **E6 — Windows + macOS.** ⚠️ **Only you can close this**, and it is the last
  thing standing between this branch and "measured on every platform". Two of
  three OS backends have never executed against a live application: the parse is
  tested against a synthetic linker-shaped blob, which proves the arithmetic and
  nothing about what a real `WINWORD.EXE` carries.

  The probe is ready and the whole run is one command per app. **On Windows:**

  ```
  python tools/os_icon_probe.py "C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"
  python tools/os_icon_probe.py "C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE"
  python tools/os_icon_probe.py "C:\Windows\System32\notepad.exe"
  python tools/os_icon_probe.py <pid-of-a-running-app>          # the live path
  ```

  **On macOS:**

  ```
  python tools/os_icon_probe.py /Applications/Safari.app
  python tools/os_icon_probe.py <pid-of-a-running-app>
  ```

  **What decides it is the `names:` line, not the picture.** B.2's resolution
  half is measured (14/16 — given "Microsoft Word" the catalogs answer); its READ
  half is the assumption. So:

  * `names:` holding a **product name** ("Microsoft Word") ⇒ B.2 holds, and the
    `catalog order:` block below it will show `mdi:microsoft-word`;
  * `names:` holding a **sentence** (`Notepad++ : a free (GNU) source code
    editor`) or the bare exe name (`pwsh`) ⇒ the documented reason both
    `FileDescription` and `ProductName` are offered and the catalog's 404 does
    the rejecting;
  * `names: (none)` ⇒ B.2 does not hold on Windows and the feature falls back to
    the executable name, which is the treadmill this exercise removed. That is
    the one result that would change the design.

  The last line says what the running app would do (`=> the keycap would ...`),
  which is the answer in one line if the rest is too much.

  ⚠️ **A `REJECTED (too low)` verdict is NOT a failure** — since E2 the OS icon
  is tried first and the `MIN_SCORE` gate falling through to the catalog is the
  gate working. The failure case is `names: (none)`.

  ⚠️ **The probe itself had a defect until this commit, and it was the one that
  matters here**: it called `candidates()` once per display name with the name in
  the *executable* slot, which yields `mdi:microsoft-microsoft-word` and never
  `mdi:microsoft-word` — so it would have reported Word as unresolvable while the
  running app resolves it fine. The instrument was under-reporting the mechanism
  it exists to measure. It now makes the single call `app_icon_fetcher` makes.

* **E7 — `score()` picks the wrong conversion.** ✅ Done. Reported from the field
  as *"video which looked quite bad and I'm sure her dithering would have
  worked"*, and it is the defect `KnownWeaknessTest` had pinned since E5:
  `detail` is `edges/lit`, and every lit pixel of a dither field touches an unlit
  one, so the term meant to reward line art was **maximised by texture**.

  **Measured, not argued.** Extracted the real `yaru-theme-icon` package (235
  icons, 88 distinct arts) and judged 22 by eye against the four conversions. The
  old scorer picked the render a human would pick **8 times out of 22**; 13 of
  the 14 misses were "`dither` or `luma` won, `adaptive` was cleaner". The
  rewrite picks it 16 times, and over the 88 distinct arts **34 winners change:
  ~26 better, 4 worse, 4 a wash**.

  What shipped: `detail` at a **quarter power** (kept — it still orders two
  otherwise-equal readings — but no longer decides everything), a new
  **`survives`** term (variance of the 2×2 block means over what a uniform field
  of that density would give: ~1 for ink that is still ink after a blur, ~0 for a
  halftone that reads as grey), **`MAX_FILL`** rejecting ink that fills its own
  bounding box, and **`MAX_LIT` 0.80 → 0.70** (free: no winning render among 116
  real icons exceeds 0.623 lit). `MIN_SCORE` re-derived 0.25 → **0.08**, where the
  data separates on the new scale.

  ⚠️ **Four repairs were measured and REFUTED first, and they are pinned as tests
  so they are not re-proposed**: a detail *ceiling* (the corpus's best render,
  Power Statistics' dithered waveform, sits at detail 0.996), **cohesion**,
  **stroke neighbourhood** (both read 0.78–1.0 for halftone *and* line art —
  only a perfect checkerboard separates, which is why testing the idea
  synthetically MISLEADS), and bbox fill as a scoring *term* rather than a
  rejection.

  ⚠️ **The honest cost**: `survives` cannot tell a 1px stroke from a halftone at
  2×2, so sparse line art scores much lower — the `_line_art` fixture went
  0.319 → 0.104. The *order* is still right, but the bottom of the scale is
  compressed, which is why `MIN_SCORE` moved with it and now sits where the data
  separates rather than mid-range. The gate is weaker than the number it
  replaced; what refuses a blob now is `MAX_FILL`, a statement about the shape,
  which is a better guard than a float that worked by accident.

  ⚠️ **The blob fixture and GNOME Totem's play triangle are statistically
  near-identical** (lit 0.62 vs 0.55, detail 0.13 vs 0.15). Anything that rejects
  one rejects the other — so the old `test_a_SOLID_BLOB_scores_near_zero` was, in
  effect, what made Totem draw a scribble. Accepting large solid marks is a
  decision, and on a keycap it is the right one: a solid play triangle is the most
  legible thing in the corpus.

  22 tests where there were 13, mutation-swept 8/8. ⚠️ The first sweep reported
  all 8 "caught" and was a **fail-open** — a quoting bug passed the literal `$S`
  to `unittest`, which errors, which reads as caught. Read the *caught-by* names,
  never the verdict alone.

* **E8 — a dither is PREFERRED, and there are three of them.** ✅ Done. Owner's
  call after reviewing the tuning sheets: *"with a very very few exceptions dither
  always looks better. So yes add 2 or 3 dither candidates and make them the first
  choice as long as it is more than just snowflakes."*

  **Gamma is the knob, and it points OPPOSITE ways per icon** — Totem, Text Editor,
  Weather and Camera want 1.4–2.0; the Calculator wants 0.5. So the three tunings
  are scored candidates rather than one tuned default. The set
  (`dither-lo` 0.5/2.5, `dither` 1.0/2.5, `dither-hi` 2.0/3.5) is **chosen by
  measurement**: of every 3-combination from a 12-point grid it maximises the mean
  best-dither score over the 88 distinct Yaru arts (0.317 against 0.225 for the
  shipped tuning alone) and puts the best dither ahead of the best threshold read
  on 36 of 88 rather than 21.

  `choose()` now splits the candidates and takes the best dither unless it scores
  below `DITHER_PREFERENCE` (0.50) of the best threshold read. That lifts a dither
  from 36 of 88 picks to **74**, and changes 67 of the 88 picks.

  ⚠️ **A "SNOWFLAKE DETECTOR" WAS ATTEMPTED AND COULD NOT BE BUILT — this is the
  fifth refuted repair in this area and the most instructive.** 29 renders were
  hand-labelled picture vs noise and every candidate feature OVERLAPPED:
  isolated-pixel share, 2×2/3×3/4×4 grain share, full-block share, blur survival
  and lit, the best single split reaching 23 of 29. The reason is not a missing
  feature: what makes Shotwell's tree or gparted's disc read as noise is that the
  **subject** is intricate, not that the dither is bad. `DITHER_PREFERENCE` is
  therefore a blunt relative floor and is documented as one.

  **0.50 is measured against a hand-judged set and the trade is about one for
  one.** Of 25 arts judged by eye (17 clear dither wins, 8 clear losses) it keeps
  all 17 wins and refuses 2 of the 8 losses; 0.55 refuses a third loss but takes
  two wins with it; below 0.40 nothing is refused.

  ⚠️ **The cost is real and is NOT "a very few exceptions".** Reading all 88
  before/after by eye: roughly 30 better, 25 worse, 30 unchanged. The losses
  cluster on clean line-art marks — the whole LibreOffice family, GNOME Music,
  Mines, Livepatch, gparted, app-center — which come back at
  `DITHER_PREFERENCE` 0.70 at the cost of Totem, cpu-x, audio-recorder,
  address-book and clock-app. One constant moves the whole trade; the sheets to
  judge it from are in the session, and the owner's stated preference is what
  0.50 encodes.

  Also: `test_a_monochrome_svg_reads_IDENTICALLY_either_way` had to widen. A flat
  single-path mark now comes back from `dither-hi`, which reproduces the shape
  exactly in its interior and differs on **20 anti-aliased edge pixels of 1444**;
  the exact half is pinned separately against the non-diffusing conversion.

  28 tests in the module (13 before E7), mutation-swept 8/8 twice. ⚠️ Three of the
  eight escaped on the first pass and each escape was a FIXTURE fault, not a
  missing test: the "dither wins while scoring lower" case handed the dither slot
  the *higher*-scoring mask (so it passed under a plain argmax too), the
  "unusable dither" case put -1.0 on both sides (where the comparison is false
  either way), and nothing asserted the gamma reached `dither_ink` at all.

* **E9 — the metric never looked at the ORIGINAL, and that was the real defect.**
  ✅ Done. Owner's diagnosis, and it is correct: *"I think the proportions and
  dimension of the original icons play a bigger role than just a clear icon and
  that is where your metric lacks behind — vs my subjective recognizability
  measure."*

  Every term in `score()` is a property of the MASK ALONE — edges, grain, ink
  balance, spread. It can say a render is crisp and it cannot say it is the right
  picture. So it ranked clean threshold line art above a dither that kept the
  artwork's layout, and E8 papered over that with a tuned `DITHER_PREFERENCE`
  constant that forced a dither to the front because a human kept choosing one.
  **The preference was a symptom.**

  `fidelity(mask, image)` is the missing measure: |Pearson r| between the render's
  and the source's 4×4 block fields. `choose()` now uses `score()` as a GATE
  (usable at all) and fidelity as the RANKING (which usable render is the right
  picture). **A dither wins 65 of 87 distinct Yaru arts on its own merits, against
  36 under score-argmax** — so the thumb could be deleted, not retuned.

  ⚠️ **1 - MAE was the obvious form and is DEGENERATE.** Most icon sources are
  mostly light, so a BLANK render matches the mean and scores ~0.9: it picked an
  empty mask for baobab, empathy, engrampa and eog. Correlation is invariant to
  offset and scale, so a constant render has no variance and scores nothing.

  ⚠️ **ABSOLUTE value, because an inverted render is equally faithful in SHAPE.**
  A dark-plate icon (Terminal, Dictionary, Backups) reads correctly either way
  round. Signed correlation refuses seven of the 87 for nothing but the sign.

  ⚠️ **The reference is cropped to its ink bbox**, because a render is. Measured on
  a small shape in a large transparent canvas: cropped 0.87, uncropped 0.10 — and
  invisible on an icon that fills its frame, which is most of them.

  **What it repaired**, judged on the same sheets that condemned E8: GNOME
  Weather, gparted, Extensions, Mahjongg and Aisleriot go back to clean `adaptive`
  reads, LibreOffice Base/Impress/Writer back to `luma`, while Totem keeps the
  dithered film-strip plate with the play triangle knocked out of it (fidelity
  0.93) and Text Editor, Camera, Calculator and the Game Boy keep their gains.
  `FIDELITY_BLOCK` is 4 because that is where the corpus separates: at 2 the
  measure grades the dither's texture (a dither wins only 56 of 87) and at 6 it
  stops telling the gammas apart.

  22 tests, mutation-swept 8/8. ⚠️ Two escaped first: the gate test used a fixture
  where the sub-gate render was ALSO the less faithful one, so deleting the gate
  changed nothing, and nothing asserted the reference is cropped — both needed a
  fixture built to make the deleted line matter, not a new assertion.

---

### E10 — the ranker could not see a colour, and the gate could not see an inverted picture

Two defects, both reported from hardware on the same run: *"the icon for gnome
text edit, nautilus are not great, calc degraded as the right side became
invisible"*.

**The reference measured DARKNESS.** `_source_ink` built its comparison map as
`1 - luma`, and luma weights green ×0.72 and blue ×0.07 — so a saturated colour
on white reads as almost nothing. GNOME Calculator is a grey panel beside a
yellow one; the yellow half measured **0.234** against the grey half's 0.623,
i.e. the reference said the right side was nearly blank. The render that dropped
that panel *entirely* therefore scored **0.983**, higher than every render that
drew both. Distance from the page in RGB puts the same panel at **0.481**.

**Correlation cannot see a dropped panel at all.** It is invariant to scale, so
a render that blanks a whole region still correlates ~1 as long as what it does
draw lines up. `coverage` — of the blocks the source fills, how many did the
render put anything into — is what separates them: Calculator's `adaptive`
reading goes 0.983 → **0.462** against the dither's **0.648**. Coverage is read
on whichever polarity correlated, or every dark-plate icon is refused for
drawing its ink where the source is light.

**The lit gate assumed ink is the minority.** `MAX_LIT` refused any render over
70% lit, which is the right rule for a filled silhouette and the wrong one for a
terminal plate with a `>_` knocked out of it — the same picture, polarity
flipped, which `fidelity()` already accepted (it takes the *absolute*
correlation for exactly this reason). Measured over the 87 distinct Yaru arts,
**9 winners change**, every one a dark-plate icon that had been shipping a
fragment of its own lit background: `bash` and the root terminal drew a bare
`>`; Calls, Music and Snap Store drew their glyph in a noise field. The winning
lit range opens from 0.055–0.623 to 0.055–**0.839**, the top of which *is* the
plate.

⚠️ **The flip is gated on an ENCLOSED HOLE, and without that gate it readmits
the one thing `MAX_LIT` exists for.** A filled silhouette's inverse is the page
around it, which has structure of its own: a flat disc scored **0.43** — past
`MIN_SCORE`, i.e. a confident offer to draw a blob on the ESC keycap, and two
existing tests caught it. `_enclosed_share` floods the unlit region inward from
the border and asks what the flood cannot reach. The data separates at **zero**:
all 13 silhouettes tried (a flat disc, a plain rounded rect, and the `alpha`
reading of 11 real icons) enclose exactly 0.000, while all 20 real plate renders
enclose 0.098–0.555. Neither lit fraction nor bounding-box fill tells them apart.

**Net:** 19 of 87 picks change from the colour/coverage reference and 9 more
from the polarity gate; `luma` all but disappears as a winner and `alpha` wins
nothing. Calculator gets its `=` panel back, Text Editor gets the page's ruled
lines back instead of a bare pencil.

⚠️ **Nautilus is NOT fixed and is not pretended to be.** Its source is a flat
mid-grey slab with one white handle; there is no internal structure to render,
so every candidate is either a noise field or an empty outline. `dither-hi`
draws a solid folder with the handle knocked out and reads best to a human, but
its correlation against a flat source is 0.32 against the dither's 0.84, so the
measure does not pick it. A flat-source case needs a different answer than a
better reference.

8 mutations, 8 caught by the intended test.

### E11 — the shortcut half, wired

E4 ported `shortcut_overlays` / `shortcut_fetcher` / `shortcut_source` with their
117 tests and **nothing in the running app imported any of them** — a keyboard on
this branch showed the program mark on ESC and no shortcut icons at all. This
wires them into the same tick the mark already runs on.

⚠️ **ONE send, not two, and that is forced rather than tidy.**
`send_overlays_mru` calls `prepare_for_mru_send()`, which RESETS the firmware's
whole display→pool mapping, and then commits the mapping it built from the
filenames it was handed. A second call does not add to the first — it replaces
it. So sending the mark and then the shortcut icons would leave only the icons,
with the mark's upload wasted. `_maybe_send_program_mark` is therefore
`_maybe_send_generic_overlays`, and both sources go into one `filenames` list.

**The mark goes first in that list, so it keeps ESC.** Both sources are synthetic
and `send_overlays_mru` gives an earlier synthetic source the key. The mark is
the one keycap that means the same thing in every application, so a shortcut
concept landing on Escape must not displace it; the loser is logged as deferred,
exactly like a template deferral.

⚠️ **The dedupe signature carries the KEYS, not just the source names.** Two
applications routinely resolve the same concepts — Save, Copy, Paste — while
binding them to different chords, so a name-only signature would report the
second app as already on the device and its icons would land on the first app's
keys or nowhere. This is the **opposite** of the MRU cache key, which is the
concept alone and correct there for exactly the inverse reason: the *pixels* do
not depend on the key, so `save` is one pool slot board-wide.

⚠️ **A latent bug the mark already had, and which the shortcut half makes ~20×
worse: a reconnect did not clear the signature.** `reset_all_caches()` empties
the MRU and the keyboard's pool is cleared right after, so nothing generic is on
the device — but the dedupe still claimed it was, and the tick never re-sent.
The keycaps stayed blank until the user switched application.

**Settings.** `shortcut_icons_enabled` and `shortcut_icon_auto_fetch` are now in
the defaults, so the settings dialog can show them. Two switches because they
answer different questions: the first governs whether another process's
accessibility tree is **read at all** — the question on a locked-down machine —
and the second only whether the icon catalog may be **fetched over the network**.
`note_settings_changed` forgets both caches *and* the device signature, because
each alone leaves the change invisible: a height change alters the pixels while
the source names may be identical.

**Driven end to end, not only through the suite.** On this container the harvest
correctly reports *"no accessibility backend on this platform"* (no AT-SPI bus),
so the chain downstream of it was driven with real parsed accelerators: 16
harvested → 16 concepts planned → a 4.8 KB catalog subset fetched → 16 masks
rendered → 16 converters built, and the real tick path sends
`['@prog:os:org.xfce.mousepad.png']` with 16 modifier variants from one upload.

9 mutations, 9 caught by the intended test.

### E12 — the generic set was overwriting the template one tick later

Reported from hardware: *"we also said that icons where we have overlays take
priority, which is not the case right now."* Correct, and the design note it
refers to was the one being violated — *"template always wins; this runs only on
the branch where the matcher found nothing."*

**`handle_active_window` returns the template filenames ONLY on the tick the
window CHANGES.** Every tick after that it answers `(None, NONE)` for the same
window. The tick's branch was `if data and cmd == OFF_ON: … else: <generic>`, so
one tick after a template landed the `else` fired, `send_overlays_mru` called
`prepare_for_mru_send()` — which resets the firmware's whole display→pool
mapping — and committed a mapping containing only the generic sources. Every
hand-made keycap went blank about a second after it appeared.

⚠️ **The tell that it is a STATE question and not a DATA question.** `data` says
*a template was just sent*; only the handler knows *a template is still active*.
`covered_by_template()` answers from `get_overlay_data()` rather than from
`current_entry`, so it cannot disagree with what a send would actually carry — a
matched entry with no overlay flag, and a remote entry whose forwarder has no
overlay, are both "not covered".

**It predates the shortcut half.** The program mark alone has been doing this
since E3; it was one keycap winning over the template's whole set, which is
already wrong and is much louder now that the generic side is ~20 keycaps.

**Not "skip the send" — skip the FETCH too.** A template-covered app must not
walk another process's accessibility tree either, so the gate sits above both
`overlay_for` and `overlays_for`.

⚠️ **The mixed send was NOT chosen, deliberately.** `send_overlays_mru` already
has the machinery for it (`covered` makes a synthetic source defer a key a real
template draws, and logs it as *"deferred to the template"*), so template and
generic could ride one send with the generic filling the template's gaps. That is
a bigger change than the report asks for and it would alter the look of every
templated app, so it is left as a question rather than taken. The machinery is
reachable today only from a direct API call.

5 mutations, 5 caught by the intended test.

### E13 — the "no backend" message named the wrong cause

Reported from the probe: `AT-SPI unavailable: No module named 'gi'` followed by
*"Needs python3-gi + gir1.2-atspi-2.0, and the a11y bus running"* — advice to
install two packages that were **already installed**.

**PyGObject is a distro package**, in `/usr/lib/python3/dist-packages`. A
virtualenv built without `--system-site-packages` cannot import it however
thoroughly it is installed, and `pip install PyGObject` builds from source and
needs the gobject-introspection headers — so on a managed machine the answer is
to let the venv see the system packages, or to run a different interpreter.
Neither is "install python3-gi".

`available()` swallowed every exception, so **three causes needing opposite
fixes collapsed into one sentence** — and the app's own log line said *"no
accessibility backend on this platform"*, which is true on macOS and actively
denies the commonest cause. `unavailable_reason()` separates them:

| cause | what it now says | the fix |
|---|---|---|
| venv without system site-packages | *"this virtualenv (…/pyvenv.cfg) cannot see the system PyGObject"* | one line in `pyvenv.cfg`, or another interpreter |
| PyGObject built for another Python | *"installed for a DIFFERENT Python than …"* | run the interpreter it was built for |
| genuinely absent | *"PyGObject is not installed"* | `python3-gi` |
| typelib absent | *"the Atspi typelib is missing"* | `gir1.2-atspi-2.0` |
| bus down | *"the accessibility bus is not running"* | start it |
| macOS | *"this platform has no accessibility backend"* | nothing; not built |

⚠️ **Saying "not installed" about a package that is on disk for a different
interpreter would reproduce the same defect one level down**, so the reason
looks before it says it (`glob` over `dist-packages`/`site-packages`).

The **probe additionally goes and finds a working interpreter** and prints the
command — a CLI a human runs once, so a handful of subprocesses is the right
price for turning "it does not work" into a line that does. The app never does
that: `unavailable_reason()` stays pure, because it runs on the harvest path.

7 mutations, 7 caught by the intended test.

### E14 — a venv is the standard way to run this app, and PyGObject cannot go in one

Follow-up to E13, from *"I do use a .venv — maybe different from the app?"*.
Same venv, and that is the point: the app runs from the same interpreter the
probe does, so the diagnostic E13 added would have told the user the truth and
left them stuck.

**PyGObject cannot be installed into a venv.** It is a distro package
(`python3-gi`, in `/usr/lib/python3/dist-packages`) and `pip install PyGObject`
builds from source against the gobject-introspection headers, which a managed
machine will not have. So `python -m venv .venv` silently costs the whole
shortcut feature and the only remedy was knowing to edit `pyvenv.cfg`.

`_import_gi()` now falls back to the distro directory when the plain import
fails. ⚠️ **Guarded on the ABI TAG, and that guard is the entire safety
argument**: `gi` is a compiled extension built for one Python minor version, so
the directory is taken only when it holds a `_gi` built for *exactly* this
interpreter — true precisely when the venv was made from the system python3,
which is the case worth rescuing. The path goes on `sys.path` for that one
import and comes off again, so a venv's own packages are never shadowed.

Verified in both directions in a real venv built from `python3.12` with
`include-system-site-packages = false`: plain `import gi` fails, the rescue
imports it from `/usr/lib/python3/dist-packages`, `sys.path` is unchanged
afterwards — and with the a11y bus up, `available()` is True and `harvest()`
runs. On an ABI mismatch (this container: system `gi` is cpython-312, the
interpreter is 3.11) the rescue correctly declines.

⚠️ **THE RESCUE EXPOSED A LATENT PROCESS-KILLER, and the two had to land
together.** `Atspi.get_desktop()` does not raise when the bus is down — it
`g_error()`s, which calls `abort()`. **SIGTRAP, exit 133, and no Python
exception to catch.** It runs on the fetcher's background thread inside the
user's tray app. The hazard predates all of this and was simply unreachable:
in a venv `import gi` failed long before anything reached AT-SPI, and the
rescue is exactly what makes it reachable. `Atspi.init()` is the probe that
does *not* abort — it returns 0 / 1 / 2 — so the bus is asked that way and the
desktop is touched only after it says yes.

⚠️ **`Atspi.init()` is not idempotent as a probe**, which is a second trap in
the same place: the first call returns 2 when the bus is unreachable and a
*second* returns 1 ("already initialised") even though it failed, so re-probing
reports success and the next `get_desktop()` kills the process. Measured — the
first `unavailable_reason()` answered correctly and the call right after it died
with SIGTRAP. The verdict is cached per process.

**The `include-system-site-packages` advice is gone from the message**, because
the code now covers that case: reaching `_no_pygobject_reason()` means either
PyGObject is absent entirely, or it is present and built for a different Python
— which that advice would not have fixed. The message names both versions
(*"built for 3.12, this is 3.11"*).

8 mutations, 8 caught by the intended test. ⚠️ **Two escaped first**, and one of
them was the crash guard: nothing asserted that `get_desktop` is unreachable
when the bus is down. The other was a **vacuous fixture** — the sys.path test
used `/usr/lib/python3/dist-packages`, which is already on `sys.path` in this
container, so it compared a path against itself and passed with the cleanup
deleted. It now uses a marker directory and asserts it is absent first.

## Part F — what could still fail

* **B.2's RESOLUTION half is measured (14/16); its READ half is not.** What is
  proven is that *given* "Microsoft Word" the catalogs answer. What is assumed is
  that `RT_VERSION` → `ProductName` actually holds "Microsoft Word" on a real
  install, and that macOS `CFBundleDisplayName` behaves. The Linux read is
  verified here and shows the failure mode to expect: a generic phrase rather
  than a missing one. E1 is first and cheap for exactly this reason.
* **A name read that returns a generic phrase is the wrong-icon risk**, not a
  missing-icon one. The Simple-Icons-and-prefixed-mdi rule (B.2) is what contains
  it; do not relax it to "try the bare mdi name too" for coverage.
* **The catalogs still carry no Microsoft or Adobe** (measured: zero of Simple
  Icons' 3383 entries). A good display name only helps where a mark exists, so
  Office and Photoshop depend entirely on the OS icon path.
* **A.3 caps the whole feature** far below anything the icon work can reach.
* **A fuzzy match is a wrong-logo risk.** Require a high threshold and let the
  catalog's own 404 reject, exactly as v1's slug guessing did.
