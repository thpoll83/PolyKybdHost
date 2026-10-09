"""Protocol v23: cmd 33's DIM flag for a browser's icons under a website's overlay.

`send_overlays_mru` against a fake keyboard and against the emulated firmware. A
position whose last source is an Underlay travels in a report flagged 0x80, every
other position in a plain one; a site cell on the same key takes the position back
to full strength; and below v23 nothing carries the flag.
"""
import os
import tempfile
import unittest

import numpy as np

from polyhost.device.bit_packing import pairs_per_report
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.poly_kybd import (MAPPING_DIM_MIN_PROTOCOL, MAPPING_FLAG_DIM,
                                       MAPPING_FLAG_RESET, MAPPING_FLAG_SHOW,
                                       protocol_supports)
from polyhost.handler.common import Underlay
from tests.device.mapping_flags_test import _keeb, _reports, MAPPING_W
from tests.device.mock_firmware_test import _keyboard

A, B, C = KeyCode.KC_A.value, KeyCode.KC_B.value, KeyCode.KC_C.value


def _mask(i):
    m = np.zeros((40, 72), dtype=np.uint8)
    m[5 + i:25 + i:3, 38:66:2 + i] = 255
    return m


def _template(tmp, name, keys, offset):
    """A real 10x9 template (a plain PNG is read as the unmodified layer), so the
    sources go through the last-one-wins path the shipped templates take. Synthetic
    sources would not: one of those skips a key an earlier source already drew."""
    from PIL import Image
    grid = np.zeros((40 * 9, 72 * 10), dtype=np.uint8)
    for n, kc in enumerate(keys):
        y, x = divmod(kc - A, 10)              # A..Z are slots 0..25, row-major
        grid[y * 40:(y + 1) * 40, x * 72:(x + 1) * 72] = _mask(offset + n)
    path = os.path.join(tmp, name)
    Image.fromarray(grid).convert("RGB").save(path)
    return path


def _send(keeb, cache, marked=True):
    """A browser drawing A and B under a site drawing B and C."""
    with tempfile.TemporaryDirectory() as tmp:
        browser = _template(tmp, "browser.png", [A, B], 0)
        site = _template(tmp, "site.png", [B, C], 5)
        return keeb.send_overlays_mru([Underlay(browser) if marked else browser, site], cache)


def _mapping_reports(dev):
    return [r for r in _reports(dev) if r[1] == MAPPING_W]


def _froms(report):
    """The `from` values of a cmd 33 report (padding repeats the last pair)."""
    width = report[2] & 0x1F
    data = report[3:]
    bits = int.from_bytes(data, "big")
    total = len(data) * 8
    values = [(bits >> (total - (i + 1) * width)) & ((1 << width) - 1)
              for i in range(total // width)]
    return values[0::2][:pairs_per_report(len(data), width)]


def _idx(cache, kc):
    return cache.display_flat_idx(kc, Modifier.NO_MOD)


class MappingDimTest(unittest.TestCase):

    def test_the_gate_is_protocol_23(self):
        self.assertEqual(MAPPING_DIM_MIN_PROTOCOL, 23)
        self.assertEqual(MAPPING_FLAG_DIM, 0x80)
        self.assertTrue(protocol_supports(23, "mapping_dim"))
        self.assertFalse(protocol_supports(22, "mapping_dim"))
        # Disjoint from the v21 flags and from every width the firmware accepts (8..16).
        self.assertEqual(MAPPING_FLAG_DIM & (MAPPING_FLAG_RESET | MAPPING_FLAG_SHOW | 0x1F), 0)

    def test_the_browsers_own_cell_goes_out_dimmed_and_the_site_wins_its_key(self):
        keeb, dev = _keeb()
        cache = OverlayMRUCache(600)
        self.assertTrue(_send(keeb, cache))
        reports = _mapping_reports(dev)
        dimmed = [r for r in reports if r[2] & MAPPING_FLAG_DIM]
        plain = [r for r in reports if not r[2] & MAPPING_FLAG_DIM]
        self.assertEqual((len(dimmed), len(plain)), (1, 1), [r[:3].hex() for r in reports])
        # Show rides on the LAST report, whichever kind it is.
        self.assertTrue(reports[-1][2] & MAPPING_FLAG_SHOW)
        self.assertFalse(reports[0][2] & MAPPING_FLAG_SHOW)
        self.assertEqual(set(_froms(dimmed[0])), {_idx(cache, A)})                    # browser only
        self.assertEqual(set(_froms(plain[0])), {_idx(cache, B), _idx(cache, C)})     # B is the site's

    def test_the_program_mark_on_ESC_is_never_dimmed(self):
        # ESC names the app on the board; a browser drawing it under a site
        # still draws it full.
        esc = KeyCode.KC_ESCAPE.value
        keeb, dev = _keeb()
        cache = OverlayMRUCache(600)
        with tempfile.TemporaryDirectory() as tmp:
            browser = _template(tmp, "browser.png", [A, esc], 0)
            site = _template(tmp, "site.png", [C], 5)
            self.assertTrue(keeb.send_overlays_mru([Underlay(browser), site], cache))
        dimmed = [r for r in _mapping_reports(dev) if r[2] & MAPPING_FLAG_DIM]
        self.assertEqual(len(dimmed), 1)
        self.assertEqual(set(_froms(dimmed[0])), {_idx(cache, A)})

    def test_below_v23_every_pair_goes_out_plain(self):
        keeb, dev = _keeb()
        keeb.supports = lambda f: f != "mapping_dim"
        cache = OverlayMRUCache(600)
        self.assertTrue(_send(keeb, cache))
        reports = _mapping_reports(dev)
        self.assertEqual(len(reports), 1)                       # one plain report holds all three
        self.assertFalse(reports[0][2] & MAPPING_FLAG_DIM)

    def test_an_unmarked_list_sends_nothing_dimmed(self):
        keeb, dev = _keeb()
        self.assertTrue(_send(keeb, OverlayMRUCache(600), marked=False))
        self.assertFalse(any(r[2] & MAPPING_FLAG_DIM for r in _mapping_reports(dev)))

    def test_the_cache_sees_the_same_images_dimmed_or_not(self):
        # The keyboard draws the dimming, so a browser image is ONE pool entry:
        # the same files sent unmarked afterwards are all cache hits.
        keeb, dev = _keeb()
        cache = OverlayMRUCache(600)
        self.assertTrue(_send(keeb, cache))
        n_before = len(_reports(dev))
        self.assertTrue(_send(keeb, cache, marked=False))
        new = _reports(dev)[n_before:]
        self.assertTrue(new)
        self.assertTrue(all(r[1] == MAPPING_W for r in new), [r[:3].hex() for r in new])


class UnderlayTest(unittest.TestCase):

    def test_an_underlay_is_its_name(self):
        u = Underlay("chrome_template.mods.png")
        self.assertEqual(u, "chrome_template.mods.png")
        self.assertEqual(hash(u), hash("chrome_template.mods.png"))
        self.assertTrue(u.underlay)
        self.assertFalse(getattr("chrome_template.mods.png", "underlay", False))

    def test_resolving_the_template_path_keeps_the_mark(self):
        from polyhost.core.poly_core import get_overlay_path
        self.assertTrue(get_overlay_path(Underlay("chrome_template.mods.png")).underlay)
        self.assertFalse(getattr(get_overlay_path("chrome_template.mods.png"), "underlay", False))


class EmulatedFirmwareTest(unittest.TestCase):
    """The emulated keyboard keeps the dim bit per position, like display_dim_bits."""

    def _run(self, protocol):
        keeb, fw = _keyboard(protocol)
        cache = OverlayMRUCache(600)
        self.assertTrue(_send(keeb, cache))
        return fw, cache

    def test_v23_marks_only_the_browsers_own_cell(self):
        fw, cache = self._run(23)
        self.assertEqual(fw.dim_positions, {_idx(cache, A)})

    def test_v22_draws_everything_full(self):
        fw, _ = self._run(22)
        self.assertEqual(fw.dim_positions, set())


if __name__ == "__main__":
    unittest.main()
