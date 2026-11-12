"""`tools/midi_legend_dump.py`: the MIDI legends, compiled from the firmware's C.

The parity test needs a firmware checkout beside this repo and a C compiler; it
skips without either. It checks that the shipped export holds exactly what the
firmware's midi_legend() returns, when the checkout is the firmware the export
came from.
"""
import os
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import midi_legend_dump as mld                      # noqa: E402
from polyhost.services import macro_label as ml      # noqa: E402
from polyhost.services import preview_data as pdata  # noqa: E402


class MidiLegendDumpTest(unittest.TestCase):
    def test_a_tree_without_the_midi_layer_gives_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(mld.midi_legends(tmp))

    def test_no_compiler_gives_none(self):
        pk = pathlib.Path(os.path.dirname(os.path.dirname(ml.default_font_dir())))
        if not (pk / "midi_legend.c").exists():
            self.skipTest("no firmware checkout with midi_legend.c")
        notes = []
        with unittest.mock.patch.object(mld, "_compiler", return_value=None):
            self.assertIsNone(mld.midi_legends(pk, log=notes.append))
        self.assertTrue(notes)

    def test_the_shipped_export_matches_the_firmware(self):
        pk = pathlib.Path(os.path.dirname(os.path.dirname(ml.default_font_dir())))
        if not (pk / "midi_legend.c").exists():
            self.skipTest("no firmware checkout with midi_legend.c")
        if mld._compiler() is None:
            self.skipTest("no C compiler")
        shipped = pdata.PreviewData()
        self.assertTrue(shipped.load(), shipped.reason)
        import re
        m = re.search(r'#define\s+FW_VERSION\s+"([^"]+)"',
                      (pk / "config.h").read_text(encoding="utf-8", errors="ignore"))
        if not m or m.group(1) != shipped.fw_version:
            self.skipTest("the checkout is not the firmware the export came from")
        live = mld.midi_legends(pk)
        self.assertEqual(len(live), 144)
        self.assertEqual({k: v for k, v in shipped.legends.items() if k.startswith("QK_MIDI_")},
                         live)


if __name__ == "__main__":
    unittest.main()
