"""The SHIPPED `midi: true` entries in `overlay-mapping.poly.yaml`.

* each Web MIDI page matches an entry with `midi: true` and no overlay of its own,
  in Chrome and Firefox on Windows and Chrome on macOS and Linux, and the browser's
  set stays at full strength (nothing is an underlay);
* the site's other pages and a search for it do not;
* the music programs carry `midi: true` on every platform branch.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import UNDERLAYS, find_matching_entry, mapping_key
from polyhost.services.midi_guide import is_midi_entry

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

PAGES = (
    "https://www.bandlab.com/studio?revId=abc",
    "https://musiclab.chromeexperiments.com/Shared-Piano/#room",
    "https://musiclab.chromeexperiments.com/Song-Maker/song/123",
    "https://www.soundtrap.com/studio/",
    "https://www.noteflight.com/scores/view/abc",
    "https://onlinesequencer.net/",
    "https://onlinesequencer.net/12345",
    "https://flat.io/score/abc-my-song",
    "https://www.musictheory.net/exercises/note",
    "https://virtualpiano.net/",
    "https://www.audiotool.com/studio",
    "https://hookpad.hooktheory.com/",
    "https://soundation.com/studio",
    "https://www.teoria.com/en/exercises/ke.php",
    "https://app.flowkey.com/",
    "https://patatap.com/?midi",
    "https://muted.io/piano/",
    "https://recursivearts.com/virtual-piano/",
    "https://app.ampedstudio.com/",
    "https://signalmidi.app/edit",
    "https://learningsynths.ableton.com/en/playground",
    "https://experiments.withgoogle.com/ai/ai-duet/view/",
    "https://sightreading.training/",
)
NOT_PAGES = (
    "https://www.bandlab.com/feed",
    "https://musiclab.chromeexperiments.com/Rhythm/",
    "https://onlinesequencer.net/forum/",
    "https://patatap.com/",
    "https://www.teoria.com/en/tutorials/",
    "https://www.google.com/search?q=onlinesequencer.net",
)
PROGRAMS = ("ableton live 12 suite", "reaper", "fl64", "protools", "musescore4", "soundcraft",
            "bitwig studio", "cubase14", "logic pro", "garageband", "lmms", "ardour")


def _overlay_handler_class():
    try:
        from polyhost.handler.active_window import OverlayHandler
    except SystemExit as e:
        raise unittest.SkipTest(f"window backend exited at import: {e!r}") from e
    except Exception as e:
        if not ((isinstance(e, ModuleNotFoundError)
                 and not (e.name or "").startswith("polyhost"))
                or type(e).__module__.split(".")[0] == "Xlib"):
            raise
        raise unittest.SkipTest(f"active_window needs a display: {e}") from e
    return OverlayHandler


class MidiRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from polyhost.device.command_ids import OsType
        cls.os = OsType
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _match(self, app, os_name, url, title="x"):
        key = mapping_key(app, self.mapping)
        self.assertIsNotNone(key, app)
        return find_matching_entry(title, self.mapping[key], url, self.os[os_name],
                                   title_known=True)

    def test_web_midi_pages(self):
        for app, os_name in (("chrome", "WINDOWS"), ("firefox", "WINDOWS"),
                             ("google chrome", "MACOS"), ("google-chrome", "LINUX")):
            for url in PAGES:
                with self.subTest(app=app, url=url):
                    m = self._match(app, os_name, url)
                    self.assertIsNotNone(m)
                    self.assertTrue(is_midi_entry(m, app))
                    browser = self._match(app, os_name, "https://example.com/")
                    self.assertEqual([str(f) for f in m["overlay"]],
                                     [str(f) for f in browser["overlay"]])
                    self.assertEqual(m.get(UNDERLAYS, ()), ())

    def test_other_pages_are_not_midi(self):
        for url in NOT_PAGES:
            with self.subTest(url=url):
                self.assertFalse(is_midi_entry(self._match("chrome", "WINDOWS", url), "chrome"))

    def test_safari_gets_no_guide(self):
        m = self._match("safari", "MACOS", PAGES[0])
        self.assertFalse(is_midi_entry(m, "safari"))

    def test_music_programs_on_every_platform(self):
        for app in PROGRAMS:
            for os_name in ("WINDOWS", "MACOS", "LINUX"):
                with self.subTest(app=app, os=os_name):
                    m = self._match(app, os_name, None)
                    self.assertTrue(is_midi_entry(m, app), m)


if __name__ == "__main__":
    unittest.main()
