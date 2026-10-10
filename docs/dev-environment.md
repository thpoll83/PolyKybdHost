# Development environment

Extracted from `CLAUDE.md` 2026-09-14. The prose is unchanged; only heading levels
and relative links were adjusted to suit a standalone file.

## Environment

- **Linux HID permissions**: `polyhost/device/99-hid.rules` must be installed as a udev rule for non-root HID access.

- **Venv**: always use `PolyKybdHost/.venv/bin/python` — system `python3` lacks numpy, PyQt5, and other runtime deps. 
  - **Note on multiple venvs**: This project shares a workspace with `qmk_firmware/`. The QMK build uses a separate global venv (`~/.qmk_venv`) installed by the session setup script. The two venvs are **completely isolated and do not interfere** — each has its own Python executable and `site-packages`. When you activate `source .venv/bin/activate` in PolyKybdHost, it activates *this* project's venv; QMK commands via the global alias (e.g., `qmk compile`) still use the separate `~/.qmk_venv` and will not conflict with PolyKybdHost's dependencies.
  - **In a fresh remote/web container the `.venv` does not exist yet** — create it and install the test deps: `python3 -m venv .venv && .venv/bin/pip install numpy pyserial hid platformdirs pyyaml pillow`, plus the hidapi **system** libs `sudo apt-get install -y libhidapi-hidraw0 libhidapi-libusb0` (the `hid` module raises `ImportError: Unable to load any of the following libraries:libhidapi-*` without them). That set is enough to run the device/unit tests (`tests.device.*`); GUI tests additionally need an X server (see below).
  - **To run the WHOLE suite** (not just `tests.device.*` — do this after any change touching
    `core/`, `gui/`, or `cli/`) you also need `requests packaging pynput pvlib geocoder PyQt5 pywinctl cairosvg`
    (pip) **and** `xvfb x11-xserver-utils` (apt), plus `pip install -r tools/requirements.txt` for
    `scripts/export_preview_data.py` and the preview tools (it needs `openpyxl`, which is a dev
    dependency and not in `requirements.txt` — the export dies with `ModuleNotFoundError:
    openpyxl` without it; measured 2026-09-27 on a freshly reset container), run under `xvfb-run -a .venv/bin/python -m
    unittest discover -s ./tests -p "*_test.py"`. Without those deps `services/updater`,
    `sunlight_helper`, `langcode_flag`, `win_helper_parse`, `res/icon_fetch` (cairosvg,
    added to the list 2026-09-23 after it cost a full run 8 tests; `openpyxl` from `tools/requirements.txt`, 2026-09-27: without it the keycap
    previews lose their letter legends and 10 preview/editor tests fail) and the `host_client`
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

## Environment (the CLAUDE.md summary)

_Moved verbatim from `CLAUDE.md` on 2026-10-10. CLAUDE.md keeps a short pointer._


- **Linux HID permissions**: `polyhost/device/99-hid.rules` must be installed as a udev
  rule for non-root HID access.
- **Venv**: always use `PolyKybdHost/.venv/bin/python` — system `python3` lacks numpy,
  PyQt5 and other deps. Creating it in a fresh container, the apt packages the `hid`
  module needs, and the extra deps + `xvfb` the GUI half of the suite requires are in
  [`docs/dev-environment.md`](dev-environment.md).
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

