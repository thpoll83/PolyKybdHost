"""macOS AppleScript fallback for reading the focused browser's active-tab URL.

The browser extension (``browser-extension/``) is the cross-platform way to get
the active website; this module is the **zero-install** macOS alternative for
the scriptable browsers. It shells out to ``osascript`` to ask the frontmost
browser for its front window's active-tab URL — reliable and permission-light on
macOS (unlike Windows UI-Automation of the address bar), and it needs no
extension.

Qt-free and import-safe on every platform: the functions simply return ``None``
off macOS or when ``osascript`` isn't usable, so callers can invoke them
unconditionally. AppleScript automation of another app triggers the one-time
macOS "PolyHost wants to control <Browser>" consent prompt; if the user declines,
we get an error and return ``None`` (degrading to title matching), never raising.

Chromium-family browsers (Chrome, Brave, Edge, Vivaldi, Opera, Arc, Chromium)
expose ``URL of active tab of front window``; Safari exposes ``URL of front
document``. **Firefox has no AppleScript URL support** — Firefox users on macOS
need the browser extension.
"""
import platform
import subprocess

# Frontmost app display name (as pywinctl's getAppName() returns it on macOS),
# lower-cased → the AppleScript needed to read its active-tab URL. Chromium
# variants share one script shape; Safari differs; Firefox is absent (no support).
_CHROMIUM_TELL = 'tell application "{app}" to get URL of active tab of front window'

_BROWSER_SCRIPTS = {
    "google chrome": _CHROMIUM_TELL.format(app="Google Chrome"),
    "google chrome canary": _CHROMIUM_TELL.format(app="Google Chrome Canary"),
    "chromium": _CHROMIUM_TELL.format(app="Chromium"),
    "brave browser": _CHROMIUM_TELL.format(app="Brave Browser"),
    "microsoft edge": _CHROMIUM_TELL.format(app="Microsoft Edge"),
    "vivaldi": _CHROMIUM_TELL.format(app="Vivaldi"),
    "opera": _CHROMIUM_TELL.format(app="Opera"),
    "arc": _CHROMIUM_TELL.format(app="Arc"),
    "safari": 'tell application "Safari" to get URL of front document',
    "safari technology preview":
        'tell application "Safari Technology Preview" to get URL of front document',
}

# osascript should answer near-instantly; bound it so a hung/consent-blocked
# call can never stall the window-tracking tick.
_OSASCRIPT_TIMEOUT_S = 1.5


def is_supported() -> bool:
    """True only on macOS (where ``osascript`` exists)."""
    return platform.system() == "Darwin"


def is_scriptable_browser(app_name: str) -> bool:
    """Whether ``app_name`` (a macOS app display name) is a browser we can script.

    False for Firefox (no AppleScript URL support) and every non-browser."""
    return isinstance(app_name, str) and app_name.strip().lower() in _BROWSER_SCRIPTS


def frontmost_url(app_name: str):
    """Return the active-tab URL of browser ``app_name`` via ``osascript``.

    ``None`` off macOS, for a non-scriptable app (incl. Firefox), when the
    browser has no open window, or when automation consent was declined — the
    caller then falls back to window-title matching. Never raises."""
    if not is_supported():
        return None
    script = _BROWSER_SCRIPTS.get((app_name or "").strip().lower())
    if not script:
        return None
    try:
        out = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=_OSASCRIPT_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    url = out.stdout.strip()
    # A browser with no front window returns an empty string (or "missing value").
    if not url or url == "missing value":
        return None
    return url
