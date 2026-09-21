"""The SHIPPED overlay mapping routes the host-process apps correctly.

⚠️ This drives `polyhost/res/overlay-mapping.poly.yaml` itself, not a fixture.
The rules it pins are properties of that FILE, and each of them is a mistake that
is easy to make and invisible once made:

* `ApplicationFrameHost.exe` and `ONENOTE.EXE` are HOSTS -- one process, many
  apps -- so a title branch that stops matching does not fail loudly, it just
  leaves the app with no overlay (which is what it had before, and reads as
  nothing having changed).
* A hosted app that gained keycaps but not an `icon:` draws whatever the HOST
  process name resolves to. For OneNote that is a real logo, so the failure is a
  confidently wrong picture rather than a blank.
* The parent entry must keep an `overlay:` of its own or none of its branches are
  reachable at all -- `find_matching_entry` returns None for an entry carrying
  neither `overlay:` nor `remote:` BEFORE it looks at any sub-map.
"""

import unittest
from pathlib import Path

import yaml

try:
    from polyhost.handler.active_window import OverlayHandler
    _IMPORT_ERR = None
except Exception as e:
    # ⚠️ NARROW ON PURPOSE. `active_window` imports pywinctl/Xlib at module load,
    # which needs a display -- so headless CI has to skip. But a blanket
    # `except Exception` also swallows a SyntaxError, a renamed `OverlayHandler`
    # or any other real regression and turns it into a permanent skip, which
    # reads as coverage. That is the exact trap CLAUDE.md records for the
    # forwarder suite, so only two things are tolerated here: the dependency
    # being absent, and Xlib refusing a missing display
    # (`Xlib.error.DisplayNameError: Bad display name ""`). Everything else
    # re-raises and fails the run.
    if not (isinstance(e, ModuleNotFoundError)
            or type(e).__module__.split(".")[0] == "Xlib"):
        raise
    _IMPORT_ERR = e

MAPPING = Path(__file__).resolve().parents[2] / "polyhost" / "res" / "overlay-mapping.poly.yaml"


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class HostedAppRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def _match(self, app, title):
        """(overlay, icon) the SHIPPED mapping resolves, or (None, None)."""
        handler = OverlayHandler(yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        entry = handler.mapping.get(app)
        if entry is None:
            return None, None
        handler.title = title
        matched, _cmd = handler.try_to_match_window(app, entry)
        if not matched:
            return None, None
        found = handler.current_entry
        overlay = found.get("overlay")
        if isinstance(overlay, list):
            overlay = overlay[0]
        return overlay, found.get("icon")

    # ------------------------------------------------------------------

    def test_the_frame_host_routes_each_title_to_its_OWN_app(self):
        calc, _ = self._match("applicationframehost", "Calculator")
        rec, _ = self._match("applicationframehost", "Sound Recorder")
        self.assertIn("calc_template", calc or "")
        self.assertIn("soundrecorder_template", rec or "")
        self.assertNotEqual(calc, rec)

    def test_a_hosted_app_we_do_NOT_name_falls_through(self):
        """The parent's `^Calculator` gate is what stops Clock or Weather being
        handed calculator keycaps. Without it every packaged app on the machine
        would match the first branch that happens to be there."""
        for title in ("Weather", "Clock", "Xbox", "Photos Legacy"):
            overlay, _ = self._match("applicationframehost", title)
            self.assertIsNone(overlay, f"{title!r} matched {overlay}")

    def test_sticky_notes_matches_but_REAL_onenote_does_not(self):
        """`ONENOTE.EXE` hosts Sticky Notes, so the entry is about Sticky Notes.
        A real OneNote window must fall through rather than get note keycaps."""
        sticky, _ = self._match("onenote", "Sticky Notes (new)")
        self.assertIn("stickynotes_template", sticky or "")
        real, _ = self._match("onenote", "My Notebook - OneNote")
        self.assertIsNone(real)

    def test_every_HOSTED_entry_names_its_own_mark(self):
        """A hosted app without `icon:` resolves the mark from the HOST process
        name -- which for onenote is a real OneNote logo, i.e. a confidently
        wrong picture rather than a blank one."""
        for app, title in (("applicationframehost", "Calculator"),
                           ("applicationframehost", "Sound Recorder"),
                           ("onenote", "Sticky Notes (new)")):
            overlay, icon = self._match(app, title)
            self.assertIsNotNone(overlay, f"{title!r} stopped matching")
            self.assertTrue(icon, f"{title!r} names no icon: the mark would come "
                                  f"from the host process name {app!r}")

    def test_photos_is_NOT_hosted_and_needs_no_icon_of_its_own(self):
        """It really is its own `Photos.exe`, so `app_icons.yaml`'s curated
        generic resolves -- and a baked/named mark would WIN over it and stop the
        generic ever uploading."""
        overlay, icon = self._match("photos", "Photos")
        self.assertIn("photos_template", overlay or "")
        self.assertIsNone(icon)

    def test_the_frame_host_parent_KEEPS_an_overlay_of_its_own(self):
        """`find_matching_entry` returns None for an entry carrying neither
        `overlay:` nor `remote:` BEFORE it looks at any sub-map, so a parent
        reduced to title branches alone makes every branch unreachable. That
        failure is silent: the apps simply stop matching."""
        parent = self.raw["applicationframehost"]
        self.assertIn("overlay", parent)
        self.assertIn("titles-startswith", parent)

    def test_every_overlay_the_mapping_names_EXISTS(self):
        """A template renamed without its mapping entry costs the app its
        keycaps, and nothing else in the suite would notice."""
        overlays = MAPPING.parent / "overlays"
        missing = []

        def walk(node):
            if isinstance(node, dict):
                value = node.get("overlay")
                for name in ([value] if isinstance(value, str) else (value or [])):
                    if not (overlays / name).exists():
                        missing.append(name)
                for key, sub in node.items():
                    if key != "overlay":
                        walk(sub)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(self.raw)
        self.assertEqual(missing, [])


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class MacOSNamesAndTitlesTest(unittest.TestCase):
    """⚠️ Two macOS conventions the SHIPPED mapping was written without, each of
    which ends in a silent "No match" rather than anything that looks wrong.

    * **macOS reports an app's DISPLAY name.** Windows gives the executable
      (`chrome.exe` -> `chrome`) and Linux the `.desktop` id (`google-chrome`);
      macOS gives `Google Chrome`, lowercased to `google chrome`. The lookup is
      an exact dict hit, so a hyphenated key cannot match a Mac.
    * **A macOS window title does not carry the application name.** VS Code
      titles a window `Welcome — PolyKybdHost`, where the other two platforms
      append ` - Visual Studio Code`. The `os: macos` branch repeated that
      regex, so it matched nothing on the platform it was written for.

    Both measured from a field log on Darwin 22.6.0 (2026-09-21), on which
    Chrome and VS Code each reported `No match` on every focus change.
    """

    @classmethod
    def setUpClass(cls):
        cls.handler = OverlayHandler(yaml.safe_load(MAPPING.read_text(encoding="utf-8")))

    def test_the_macOS_DISPLAY_names_are_keys(self):
        for name in ("google chrome", "brave browser", "microsoft edge"):
            self.assertIn(name, self.handler.mapping, name)

    def test_the_other_platforms_keep_THEIR_spellings(self):
        """The spaced names are an ADDITION. Replacing the hyphenated ones would
        trade a broken Mac for a broken Linux."""
        for name in ("chrome", "google-chrome", "brave-browser", "microsoft-edge"):
            self.assertIn(name, self.handler.mapping, name)

    def _code(self, os_name, title):
        from polyhost.handler.common import find_matching_entry
        hit = find_matching_entry(title, self.handler.mapping["code"], None, os_name)
        return (hit or {}).get("overlay")

    def test_VS_Code_matches_a_REAL_macOS_title(self):
        overlay = self._code("macos", "Welcome — PolyKybdHost")
        self.assertTrue(overlay, "the macOS branch matched nothing")
        self.assertIn("vscode_mac_template.mods.png", overlay)

    def test_Windows_and_Linux_still_REQUIRE_the_app_name_in_the_title(self):
        """⚠️ The constraint is dropped for macOS ONLY. Dropping it everywhere
        would hand VS Code's keycaps to any window of a process called `code`."""
        real = "app.py - PolyKybdHost - Visual Studio Code"
        self.assertIn("vscode_template.mods.png", self._code("windows", real))
        self.assertIn("vscode_linux_template.mods.png", self._code("linux", real))
        self.assertIsNone(self._code("windows", "Welcome — PolyKybdHost"))
        self.assertIsNone(self._code("linux", "Welcome — PolyKybdHost"))


if __name__ == "__main__":
    unittest.main()
