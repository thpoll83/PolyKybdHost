"""Shrinking an OS app icon before it crosses the network.

The bug: a forwarder reported `icon too large (294276 > 65536 base64 chars)` and
the window-report RPC FAILED -- a 512x512 VS Code icon against an endpoint that
bounds its one network-reachable method on purpose. The receiver reduces every
icon to a 38 px mark, so the resolution was redundant the whole way.
"""

import base64
import io
import random
import unittest
from unittest.mock import patch

from PIL import Image

from polyhost.services import icon_binarise

SVG = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"/>'


def _noise(w, h, seed=1):
    """Genuinely incompressible pixels.

    ⚠️ An arithmetic "noise" pattern is NOT noise -- `(x*7 + y*13) % 256` is a
    smooth gradient and PNG stores a 256x256 one in 1.5 KB. The first cut of
    this file used it and asserted a size reduction on data that needed none,
    which is the fixture agreeing with itself rather than testing anything.
    """
    rng = random.Random(seed)
    return [(rng.randrange(256), rng.randrange(256), rng.randrange(256), 255)
            for _ in range(w * h)]


def _png(w, h, seed=1):
    img = Image.new("RGBA", (w, h))
    img.putdata(_noise(w, h, seed))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _size_of(data):
    return Image.open(io.BytesIO(data)).size


class ShrinkForTransportTest(unittest.TestCase):

    def test_a_big_raster_icon_is_reduced(self):
        big = _png(512, 512)
        small = icon_binarise.shrink_for_transport(big)
        self.assertLessEqual(max(_size_of(small)), icon_binarise.TRANSPORT_MAX_PX)
        self.assertLess(len(small), len(big))

    def test_the_reduced_icon_fits_the_endpoint_cap(self):
        # The whole point: the measured failure was 294276 base64 chars.
        from polyhost.server.window_report_server import MAX_ICON_B64
        small = icon_binarise.shrink_for_transport(_png(512, 512))
        self.assertLess(len(base64.b64encode(small)), MAX_ICON_B64)

    def test_the_cap_covers_an_INCOMPRESSIBLE_icon_at_the_transport_size(self):
        # ⚠️ The pairing that has to hold, and the one a realistic fixture will
        # not check: shrinking guarantees the RASTER, not the byte count, so the
        # cap has to cover the worst PNG of that raster. Pure random RGBA is
        # that worst case -- measured 102685 bytes / 136916 base64 at 160px,
        # which a 64 KB cap would still have refused. Shrink the sender and
        # leave the cap alone and the bug comes back for a busy icon.
        from polyhost.server.window_report_server import MAX_ICON_B64
        n = icon_binarise.TRANSPORT_MAX_PX
        img = Image.new("RGBA", (n, n))
        img.putdata(_noise(n, n, seed=7))
        out = io.BytesIO()
        img.save(out, format="PNG")
        self.assertLess(len(base64.b64encode(out.getvalue())), MAX_ICON_B64)

    def test_an_already_small_icon_is_passed_through_UNCHANGED(self):
        # Byte-identical, not merely equivalent: re-encoding buys nothing and
        # would change the content hash the receiver caches on.
        small = _png(32, 32)
        self.assertIs(icon_binarise.shrink_for_transport(small), small)

    def test_an_icon_exactly_at_the_limit_is_not_re_encoded(self):
        at = _png(icon_binarise.TRANSPORT_MAX_PX, icon_binarise.TRANSPORT_MAX_PX)
        self.assertIs(icon_binarise.shrink_for_transport(at), at)

    def test_svg_is_never_rasterised_here(self):
        # Vector is what makes the Linux backend work at all; rasterising it
        # here would throw the path away for every forwarded app.
        self.assertIs(icon_binarise.shrink_for_transport(SVG), SVG)

    def test_svg_never_even_REACHES_pillow(self):
        # ⚠️ The assertion above cannot catch a missing guard: Pillow cannot
        # open SVG, so the except-clause fallback returns the same object and
        # `assertIs` passes either way. Deleting the guard was mutation-tested
        # and escaped on exactly that. Assert the call is not made -- which is
        # also the real cost being avoided, a raised exception and a debug
        # traceback for every SVG icon on every forwarded app.
        with patch("PIL.Image.open") as opened:
            self.assertIs(icon_binarise.shrink_for_transport(SVG), SVG)
        opened.assert_not_called()

    def test_an_svg_with_an_xml_prologue_is_still_svg(self):
        data = b"   " + SVG
        self.assertIs(icon_binarise.shrink_for_transport(data), data)

    def test_a_multi_frame_ico_flattens_to_its_largest_frame(self):
        # Which is the frame the receiver picks anyway. Pillow reports an ICO's
        # size as its largest frame, so reading 160 back proves the 256 frame
        # was the one taken and then reduced -- a 16px frame would read 16.
        src = Image.new("RGBA", (256, 256))
        src.putdata(_noise(256, 256))
        out = io.BytesIO()
        src.save(out, format="ICO", sizes=[(16, 16), (48, 48), (256, 256)])
        ico = out.getvalue()
        small = icon_binarise.shrink_for_transport(ico)
        self.assertLessEqual(max(_size_of(small)), icon_binarise.TRANSPORT_MAX_PX)

    def test_the_pixel_cap_holds_even_when_the_source_is_TINY_in_bytes(self):
        # A smooth 512x512 stores in a couple of KB, so a bytes-only rule would
        # pass it straight through and leave the receiver decoding 16x the
        # pixels it can use. The cap is on the raster, deliberately.
        flat = Image.new("RGBA", (512, 512), (10, 20, 30, 255))
        out = io.BytesIO()
        flat.save(out, format="PNG")
        data = out.getvalue()
        self.assertLess(len(data), 5000, "fixture is meant to be tiny in bytes")
        self.assertLessEqual(max(_size_of(icon_binarise.shrink_for_transport(data))),
                             icon_binarise.TRANSPORT_MAX_PX)

    def test_a_multi_frame_ICNS_is_shrunk_too(self):
        # The regression this replaced: `image.size = max(info["sizes"])` --
        # copied from app_icons, where it is harmless -- assigned an ICNS
        # 3-tuple (w, h, scale), the decode raised, and the fallback returned a
        # 4.1 MB icon unshrunk. It passed every ICO test.
        src = Image.new("RGBA", (512, 512))
        src.putdata(_noise(512, 512, seed=11))
        out = io.BytesIO()
        try:
            src.save(out, format="ICNS", sizes=[(16, 16), (128, 128), (512, 512)])
        except Exception:
            self.skipTest("this Pillow cannot write ICNS")
        icns = out.getvalue()
        small = icon_binarise.shrink_for_transport(icns)
        self.assertIsNot(small, icns, "an ICNS must not pass through unshrunk")
        self.assertLessEqual(max(_size_of(small)), icon_binarise.TRANSPORT_MAX_PX)

    def test_pillow_opens_a_multi_frame_icon_at_its_LARGEST_frame(self):
        # The premise the code now relies on instead of selecting a frame. If a
        # future Pillow defaults to the smallest, the shrink would feed the
        # receiver a 16px mark and nothing else would say so.
        src = Image.new("RGBA", (256, 256))
        src.putdata(_noise(256, 256, seed=12))
        out = io.BytesIO()
        src.save(out, format="ICO", sizes=[(16, 16), (48, 48), (256, 256)])
        opened = Image.open(io.BytesIO(out.getvalue()))
        self.assertEqual(max(opened.size), 256)

    def test_undecodable_bytes_come_back_untouched(self):
        # Never raises: a cosmetic feature must not break window reporting.
        junk = b"\x00\x01\x02not an image at all"
        self.assertIs(icon_binarise.shrink_for_transport(junk), junk)

    def test_empty_input_is_returned_as_is(self):
        self.assertEqual(icon_binarise.shrink_for_transport(b""), b"")
        self.assertIsNone(icon_binarise.shrink_for_transport(None))

    def test_the_result_is_still_readable_by_the_binariser(self):
        # A shrink that produced something `choose` cannot read would turn a
        # too-big icon into a silently missing mark -- the same outcome, one
        # step later.
        small = icon_binarise.shrink_for_transport(_png(512, 512))
        mask, conversion, score = icon_binarise.choose(
            Image.open(io.BytesIO(small)), 38)
        self.assertIsNotNone(mask)
        self.assertIsNotNone(conversion)


class TransportSizeIsTiedToTheMarkBoxTest(unittest.TestCase):

    def test_it_keeps_4x_headroom_over_the_receivers_box(self):
        # ⚠️ This is the assert that cannot live in icon_binarise: app_icons
        # imports it, so importing PROGRAM_ICON_BOX back would be a cycle. If
        # the mark box grows, this fails rather than the transport quietly
        # starving the receiver's LANCZOS pass of pixels.
        from polyhost.services.app_icons import PROGRAM_ICON_BOX
        self.assertGreaterEqual(icon_binarise.TRANSPORT_MAX_PX,
                                4 * PROGRAM_ICON_BOX)


if __name__ == "__main__":
    unittest.main()
