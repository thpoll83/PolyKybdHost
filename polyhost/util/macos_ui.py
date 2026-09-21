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


def activate_app() -> bool:
    """Make this process the ACTIVE application on macOS.

    ⚠️ **This is the other half of `hide_dock_icon`, and it exists because of
    it.** `NSApplicationActivationPolicyAccessory` is what makes a tray app a
    tray app -- and an accessory application is never promoted to active just
    because it opened a window. Qt's `raise_()`/`activateWindow()` then order
    the window correctly *inside our own process* while the process stays
    behind, so every window the tray opens lands under whatever the user was
    in. Reported from the field for "Log file..." and true of all of them
    (2026-09-21).

    ⚠️ `activateIgnoringOtherApps_(True)`, not `False`: with False macOS only
    promotes an app the user has already brought forward some other way, which
    is exactly the case that is not happening here.

    Returns True if the process was promoted, False otherwise (non-macOS, or
    AppKit unavailable). Safe to call unconditionally.
    """
    if platform.system() != "Darwin":
        return False
    try:
        from AppKit import NSApp, NSApplication
        app = NSApp() if callable(NSApp) else NSApp
        if app is None:
            app = NSApplication.sharedApplication()
        app.activateIgnoringOtherApps_(True)
        return True
    except Exception as exc:  # ImportError or any AppKit hiccup
        # Cosmetic: a window that opens behind is still better than one that
        # does not open, so this never propagates.
        log.debug("Could not bring the application forward: %s", exc)
        return False
