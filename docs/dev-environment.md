# Development environment

Moved out of `CLAUDE.md` 2026-09-14. Verbatim.

### Environment

- **Linux HID permissions**: `polyhost/device/99-hid.rules` must be installed as a udev rule for non-root HID access.

- **Venv**: always use `PolyKybdHost/.venv/bin/python` — system `python3` lacks numpy, PyQt5, and other runtime deps. 
  - **Note on multiple venvs**: This project shares a workspace with `qmk_firmware/`. The QMK build uses a separate global venv (`~/.qmk_venv`) installed by the session setup script. The two venvs are **completely isolated and do not interfere** — each has its own Python executable and `site-packages`. When you activate `source .venv/bin/activate` in PolyKybdHost, it activates *this* project's venv; QMK commands via the global alias (e.g., `qmk compile`) still use the separate `~/.qmk_venv` and will not conflict with PolyKybdHost's dependencies.
  - **In a fresh remote/web container the `.venv` does not exist yet** — create it and install the test deps: `python3 -m venv .venv && .venv/bin/pip install numpy pyserial hid platformdirs pyyaml pillow`, plus the hidapi **system** libs `sudo apt-get install -y libhidapi-hidraw0 libhidapi-libusb0` (the `hid` module raises `ImportError: Unable to load any of the following libraries:libhidapi-*` without them). That set is enough to run the device/unit tests (`tests.device.*`); GUI tests additionally need an X server (see below).
  - **To run the WHOLE suite** (not just `tests.device.*` — do this after any change touching
    `core/`, `gui/`, or `cli/`) you also need `requests packaging pynput pvlib geocoder PyQt5 pywinctl`
    (pip) **and** `xvfb x11-xserver-utils` (apt), run under `xvfb-run -a .venv/bin/python -m
    unittest discover -s ./tests -p "*_test.py"`. Without those deps `services/updater`,
    `sunlight_helper`, `langcode_flag`, `win_helper_parse`, and the `host_client`
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

