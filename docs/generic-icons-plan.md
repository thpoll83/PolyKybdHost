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

---

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
