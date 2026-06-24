"""macOS-specific UI tweaks for the tray apps.

Kept tiny and import-safe on every platform: the functions here no-op off
macOS and swallow import/runtime errors, so callers can invoke them
unconditionally right after constructing the QApplication.
"""
import logging
import platform

log = logging.getLogger(__name__)

# NSApplicationActivationPolicyAccessory — the app runs without a Dock icon and
# without a menu bar, the runtime equivalent of Info.plist's LSUIElement=1. This
# is what turns a plain QApplication into a proper "tray/menu-bar only" agent
# app. (Regular=0, Accessory=1, Prohibited=2.)
_NS_ACCESSORY = 1


def hide_dock_icon() -> bool:
    """Make this process a background/accessory app on macOS (no Dock icon).

    Returns True if the policy was applied, False otherwise (non-macOS, or
    AppKit/PyObjC unavailable). Safe to call unconditionally.
    """
    if platform.system() != "Darwin":
        return False
    try:
        # PyObjC ships transitively on macOS (PyWinCtl depends on it), but guard
        # anyway so a missing AppKit never stops the tray from coming up.
        from AppKit import NSApp, NSApplication
        app = NSApp() if callable(NSApp) else NSApp
        if app is None:
            app = NSApplication.sharedApplication()
        app.setActivationPolicy_(_NS_ACCESSORY)
        return True
    except Exception as exc:  # ImportError or any AppKit hiccup
        log.debug("Could not set macOS accessory activation policy: %s", exc)
        return False
