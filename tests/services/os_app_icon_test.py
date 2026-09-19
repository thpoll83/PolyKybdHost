"""What the OS can tell us about a running application.

⚠️ The module had NO tests at all before this file, on any branch, while carrying
a hand-written PE resource walker and three platform backends of which two have
never run against a live application. The VERSIONINFO parse is exercised against
a synthetic blob laid out the way a linker lays one out, which is the only way
any of it is checkable off Windows.
"""
import struct
import unittest
# ⚠️ Mock is reached by a plain import, not by the repo's prevailing
# import-from idiom (28 test files use that). Mixing the two forms for one
# module trips CodeQL's py/import-and-import-from, which reports on changed
# code -- so the existing files are unflagged and a new one is not.
import unittest.mock as mock

from polyhost.services import os_app_icon as osi


# --------------------------------------------------------------------------
# A VS_VERSIONINFO blob, built the way a linker builds one: every node is
# `wLength wValueLength wType`, a NUL-terminated UTF-16LE key, and a body, each
# part padded to a 32-bit boundary.
# --------------------------------------------------------------------------

def _node(key, value=b"", value_len=None, value_type=0, children=b""):
    encoded = key.encode("utf-16-le") + b"\x00\x00"
    head = 6 + len(encoded)
    pad = b"\x00" * ((-head) % 4)
    body = value + b"\x00" * ((-len(value)) % 4) + children
    length = head + len(pad) + len(body)
    declared = len(value) if value_len is None else value_len
    return struct.pack("<HHH", length, declared, value_type) + encoded + pad + body


def _string(key, text, value_len=None):
    raw = (text + "\x00").encode("utf-16-le")
    return _node(key, raw, value_len=len(raw) // 2 if value_len is None else value_len,
                 value_type=1)


def version_blob(pairs, lang="040904b0", string_nodes=None):
    strings = string_nodes if string_nodes is not None else b"".join(
        _string(k, v) for k, v in pairs)
    table = _node(lang, value_type=1, children=strings)
    info = _node("StringFileInfo", value_type=1, children=table)
    fixed = struct.pack("<I", 0xFEEF04BD) + b"\x00" * 48
    return _node("VS_VERSION_INFO", fixed, value_type=0, children=info)


def names_in(blob):
    return osi.names_from_version_strings(dict(osi._vs_walk(blob, 0, len(blob))))


class VersionResourceTest(unittest.TestCase):

    def test_every_string_is_recovered_from_a_real_layout(self):
        blob = version_blob([("CompanyName", "Microsoft Corporation"),
                             ("FileDescription", "Microsoft Word"),
                             ("ProductName", "Microsoft Office"),
                             ("FileVersion", "16.0.1")])
        self.assertEqual(dict(osi._vs_walk(blob, 0, len(blob))), {
            "CompanyName": "Microsoft Corporation",
            "FileDescription": "Microsoft Word",
            "ProductName": "Microsoft Office",
            "FileVersion": "16.0.1"})

    def test_FileDescription_outranks_ProductName(self):
        # ⚠️ The ordering IS the feature. `ProductName` is routinely the suite,
        # so taking it first hands Word, Excel and PowerPoint one identical
        # "Microsoft Office" mark -- three apps, one picture, which is the exact
        # failure the per-app mark exists to avoid.
        blob = version_blob([("ProductName", "Microsoft Office"),
                             ("FileDescription", "Microsoft Word")])
        self.assertEqual(names_in(blob),
                         ("Microsoft Word", "Microsoft Office"))

    def test_a_repeated_value_is_offered_once(self):
        blob = version_blob([("FileDescription", "Inkscape"),
                             ("ProductName", "Inkscape")])
        self.assertEqual(names_in(blob), ("Inkscape",))

    def test_a_value_length_given_in_BYTES_still_reads(self):
        # Documented in WCHARs, written by some producers in bytes. Clamping to
        # the node covers both -- an over-long count simply runs to the node end
        # and the NUL strip gives the same string.
        raw = ("Krita" + "\x00").encode("utf-16-le")
        node = _string("ProductName", "Krita", value_len=len(raw))
        blob = version_blob([], string_nodes=node)
        self.assertEqual(dict(osi._vs_walk(blob, 0, len(blob))), {"ProductName": "Krita"})

    def test_an_UNTERMINATED_value_cannot_read_into_the_next_node(self):
        # ⚠️ This is the only case where clamping the value to its node changes
        # the answer, and it took a mutation sweep to find: a well-formed value
        # ends in NUL, so the split trims any over-read and the clamp is
        # invisible. Strip the terminator -- which a truncated or hostile
        # resource does -- and an over-long `wValueLength` walks straight into
        # the following node's bytes.
        raw = "AB".encode("utf-16-le")                   # deliberately no NUL
        first = _node("ProductName", raw, value_len=8, value_type=1)
        second = _string("FileDescription", "Second")
        blob = version_blob([], string_nodes=first + second)
        self.assertEqual(dict(osi._vs_walk(blob, 0, len(blob))).get("ProductName"), "AB")

    def test_a_zero_length_node_does_not_hang(self):
        # ⚠️ Not merely malformed -- `pos` would never advance, so a truncated or
        # hostile resource would spin forever inside a cosmetic lookup.
        blob = struct.pack("<HHH", 0, 0, 0) + b"\x00" * 32
        self.assertEqual(list(osi._vs_walk(blob, 0, len(blob))), [])

    def test_a_truncated_blob_yields_nothing_rather_than_raising(self):
        blob = version_blob([("ProductName", "GIMP")])
        for cut in range(1, len(blob), 7):
            list(osi._vs_walk(blob[:cut], 0, cut))      # must not raise

    def test_a_pe_with_no_resources_has_no_names(self):
        self.assertEqual(osi.version_strings(b"not a PE at all"), {})
        self.assertEqual(osi.names_from_pe(b"not a PE at all"), ())


class DesktopEntryTest(unittest.TestCase):

    def _entries(self, mapping):
        return lambda: iter(list(mapping.items()))

    def test_StartupWMClass_wins_over_everything(self):
        entries = {
            "/x/aaa.desktop": {"Icon": "aaa", "Name": "Aaa", "Exec": "thing"},
            "/x/thing.desktop": {"Icon": "byname", "Name": "By Name", "Exec": "thing"},
            "/x/zzz.desktop": {"Icon": "wm", "Name": "By WM Class",
                               "StartupWMClass": "thing", "Exec": "other"},
        }
        with mock.patch.object(osi, "_desktop_entries", self._entries(entries)):
            self.assertEqual(osi._linux_entry("/usr/bin/thing", "thing")["Name"],
                             "By WM Class")

    def test_the_reverse_dns_stem_beats_an_Exec_match(self):
        # ⚠️ The regression this rank was added for. Both entries carry the SAME
        # `Exec` stem and the SAME icon, so the ambiguity is invisible while only
        # `Icon=` is read -- and readdir order decides, putting the settings
        # dialog first. Measured on a stock Xfce install.
        entries = {
            "/x/org.xfce.mousepad-settings.desktop": {
                "Icon": "org.xfce.mousepad", "Name": "Text Editor Settings",
                "Exec": "mousepad --preferences"},
            "/x/org.xfce.mousepad.desktop": {
                "Icon": "org.xfce.mousepad", "Name": "Mousepad",
                "Exec": "mousepad %U"},
        }
        with mock.patch.object(osi, "_desktop_entries", self._entries(entries)):
            self.assertEqual(osi._linux_entry("/usr/bin/mousepad", "mousepad")["Name"],
                             "Mousepad")

    def test_a_reverse_dns_id_resolves_with_no_proc_lookup(self):
        entries = {"/x/org.gnome.gedit.desktop": {"Icon": "g", "Name": "gedit",
                                                  "Exec": "gedit %U"}}
        with mock.patch.object(osi, "_desktop_entries", self._entries(entries)):
            self.assertEqual(osi._linux_entry("", "gedit")["Name"], "gedit")

    def test_an_entry_with_no_icon_still_yields_a_NAME(self):
        # A name with no icon still resolves a catalog mark, so the second pass
        # exists. A wrong icon would not be worth the same latitude.
        entries = {"/x/thing.desktop": {"Name": "The Thing", "Exec": "thing"}}
        with mock.patch.object(osi, "_desktop_entries", self._entries(entries)):
            self.assertEqual(osi._linux_entry("", "thing").get("Name"), "The Thing")

    def test_the_icon_bearing_pass_is_preferred(self):
        # Both match by stem; the one that can actually supply an icon wins, so
        # adding the name pass cannot move an icon that resolves today.
        entries = {
            "/x/thing.desktop": {"Name": "No Icon", "Exec": "thing"},
            "/x/other.desktop": {"Icon": "i", "Name": "Has Icon", "Exec": "thing"},
        }
        with mock.patch.object(osi, "_desktop_entries", self._entries(entries)):
            self.assertEqual(osi._linux_entry("/usr/bin/thing", "")["Name"], "Has Icon")


class WindowsExeTest(unittest.TestCase):

    def test_off_windows_it_returns_empty_rather_than_raising(self):
        # The whole module is a cosmetic lookup: a failure must never reach the
        # overlay send. Off Windows `ctypes.WinDLL` does not exist at all, so
        # this is the path every non-Windows run takes.
        self.assertEqual(osi._windows_exe(1), "")

    def test_the_handle_is_bound_as_a_HANDLE_not_an_int(self):
        # ⚠️ The bug this pins is invisible in practice: with no explicit
        # restype ctypes returns OpenProcess's HANDLE as c_int and truncates it
        # on 64-bit, so CloseHandle closes the wrong thing. Windows hands out
        # small handles, so it looks fine until it does not -- and this path has
        # never run on Windows at all.
        recorded = {}

        class FakeFunc:
            def __init__(self, name, result):
                self.name, self.result = name, result
                self.argtypes = self.restype = None

            def __call__(self, *args):
                recorded.setdefault("calls", []).append(self.name)
                return self.result

        class FakeKernel32:
            def __init__(self):
                self._f = {"OpenProcess": FakeFunc("OpenProcess", 0)}

            def __getattr__(self, name):
                return self._f.setdefault(name, FakeFunc(name, 0))

        fake = FakeKernel32()
        import ctypes
        with mock.patch.object(ctypes, "WinDLL", create=True,
                               side_effect=lambda *a, **k: fake):
            osi._windows_exe(1)
        self.assertIsNotNone(fake._f["OpenProcess"].restype,
                             "OpenProcess must declare its HANDLE restype")
        self.assertIsNotNone(fake._f["OpenProcess"].argtypes)


class AppIdentityTest(unittest.TestCase):

    def test_an_unsupported_platform_is_an_EMPTY_identity_not_None(self):
        # A caller reading `.names` must need no guard.
        with mock.patch.object(osi, "platform_key", lambda: "haiku"):
            found = osi.app_identity(1, "anything")
        self.assertIsInstance(found, osi.AppIdentity)
        self.assertEqual((found.icon, found.icon_path, found.names), (None, "", ()))

    def test_a_backend_that_raises_is_swallowed(self):
        def boom(pid, app_name):
            raise RuntimeError("no")
        with mock.patch.dict(osi.BACKENDS, {"haiku": boom}, clear=False), \
                mock.patch.object(osi, "platform_key", lambda: "haiku"):
            self.assertEqual(osi.app_identity(1, "x").names, ())

    def test_icon_bytes_stays_the_old_shape(self):
        ident = osi.AppIdentity(b"PNG", "/a/b.png", ("B",))
        with mock.patch.object(osi, "app_identity", lambda *a, **k: ident):
            self.assertEqual(osi.icon_bytes(1, "b"), (b"PNG", "/a/b.png"))
            self.assertEqual(osi.display_names(1, "b"), ("B",))

    def test_icon_bytes_is_None_when_only_a_NAME_was_found(self):
        ident = osi.AppIdentity(None, "", ("Only A Name",))
        with mock.patch.object(osi, "app_identity", lambda *a, **k: ident):
            self.assertIsNone(osi.icon_bytes(1, "x"))
            self.assertEqual(osi.display_names(1, "x"), ("Only A Name",))



class MatchRankIsReportedTest(unittest.TestCase):
    """The log line that says WHICH of the four matches fired.

    ⚠️ It exists because "no mark appeared" and "no desktop entry matched" look
    identical from outside, and telling them apart decides whether to look at
    the lookup or at the 1-bit score. A session was spent building a fixture to
    answer it for one app.

    ⚠️ And it is pinned because the first version LIED. It re-walked
    `_desktop_entries()` and matched the winner by identity -- which can never
    hit, since that generator re-parses every file and yields fresh dicts -- so
    ranks 2 and 3 were both reported as "4/Exec-vs-exe". A wrong diagnostic
    sends the next round the wrong way, which is worse than no diagnostic.
    """

    def _entries(self, mapping):
        return lambda: iter(list(mapping.items()))

    def _rank(self, entries, exe, name):
        with mock.patch.object(osi, "_desktop_entries", self._entries(entries)), \
                mock.patch.object(osi.log, "info") as info:
            osi._linux_entry(exe, name)
        return info.call_args.args[-1]

    def test_each_rank_reports_itself(self):
        cases = [
            ("1/StartupWMClass",
             {"/x/a.desktop": {"Icon": "a", "Name": "A", "StartupWMClass": "thing"}},
             "/usr/bin/other", "thing"),
            ("2/stem",
             {"/x/thing.desktop": {"Icon": "a", "Name": "A", "Exec": "other"}},
             "/usr/bin/other2", "thing"),
            ("3/reverse-dns",
             {"/x/org.gnome.thing.desktop": {"Icon": "a", "Name": "A", "Exec": "x"}},
             "/usr/bin/other", "thing"),
            ("4/Exec-vs-exe",
             {"/x/unrelated.desktop": {"Icon": "a", "Name": "A", "Exec": "thing %U"}},
             "/usr/bin/thing", "gnome-thing-trunc"),
            ("none (name-only pass)", {}, "/usr/bin/thing", "thing"),
        ]
        for expected, entries, exe, name in cases:
            with self.subTest(expected):
                self.assertIn(expected, self._rank(entries, exe, name))

    def test_rank_2_is_not_reported_as_rank_4(self):
        # The exact shape of the lie: an entry that matches by stem AND by exec.
        entries = {"/x/thing.desktop": {"Icon": "a", "Name": "A", "Exec": "thing"}}
        self.assertIn("2/stem", self._rank(entries, "/usr/bin/thing", "thing"))

class ResourceReaderCallersAgreeTest(unittest.TestCase):
    """⚠️ `_pe_resource_reader` returns (to_offset, root) and BOTH callers must
    unpack it that way round.

    `version_strings` had it backwards, so `_resource_blob` received a function
    where it wants an int, raised, and `app_identity` caught the error and
    returned an EMPTY identity — losing every Windows display name and the icon
    that had already been parsed. Green everywhere off Windows, because the path
    needs a real PE to reach (Greptile, #240).

    Tested as a CONTRACT between the two callers rather than against a synthetic
    PE: the bug is an argument order, and a fixture elaborate enough to reach it
    would be testing the linker's layout instead."""

    def _spy(self, fn):
        """Run `fn` with the reader stubbed, returning what `_resource_blob` got."""
        seen = {}

        def fake_reader(data):
            return ("TO_OFFSET_SENTINEL", 0xABCD)        # (to_offset, root)

        def fake_blob(data, root, to_offset, type_id, wanted_id=None):
            seen["root"], seen["to_offset"] = root, to_offset
            return b""

        real_reader, real_blob = osi._pe_resource_reader, osi._resource_blob
        osi._pe_resource_reader, osi._resource_blob = fake_reader, fake_blob
        try:
            fn(b"irrelevant")
        finally:
            osi._pe_resource_reader, osi._resource_blob = real_reader, real_blob
        return seen

    def test_version_strings_passes_root_as_the_INT(self):
        seen = self._spy(osi.version_strings)
        self.assertEqual(seen["root"], 0xABCD)
        self.assertEqual(seen["to_offset"], "TO_OFFSET_SENTINEL")

    def test_icon_from_pe_agrees_with_it(self):
        """The caller that always worked — pinned so the two cannot drift apart
        again in either direction."""
        seen = self._spy(osi.icon_from_pe)
        self.assertEqual(seen["root"], 0xABCD)
        self.assertEqual(seen["to_offset"], "TO_OFFSET_SENTINEL")


if __name__ == "__main__":
    unittest.main()
