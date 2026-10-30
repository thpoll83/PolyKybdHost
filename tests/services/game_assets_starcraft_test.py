"""The StarCraft reader (game_assets/starcraft) and the StarCraft II overlay
drawn from it. Synthetic game files only.

Blizzard's files may not be committed, so the tests write small MPQ archives
and GRP sprites with encoders that exist only here: stored, zlib, bzip2 and
PKWARE implode sectors, encrypted or not. The implode decoder is also checked
against the one published test vector, from the comment at the top of
zlib's contrib/blast/blast.c. Nothing here was checked against real
StarCraft files.
"""
import bz2
import os
import struct
import tempfile
import unittest
import unittest.mock as mock
import zlib
from pathlib import Path

import numpy as np

from polyhost.device.keys import KeyCode, Modifier
from polyhost.services import game_assets
from polyhost.services.game_assets import build, dither
from polyhost.services.game_assets.starcraft import explode, grp, mpq
from polyhost.services.game_assets.starcraft import reader as sc
from tests.services.game_assets_ra_test import cells
from tests.services.game_assets_test import blob_frame

SPEC = build.RES / "overlay_sources" / "starcraft2" / "starcraft2.yaml"
OVERLAYS = build.RES / "overlays"
RACES = ("terran", "protoss", "zerg")
BLAST_VECTOR = bytes.fromhex("00048224258f807f")      # blast.c: "AIAIAIAIAIAIA"

# --------------------------------------------------------------------------- #
# encoders (test-only)
# --------------------------------------------------------------------------- #


class BitWriter:
    def __init__(self):
        self.out, self.buf, self.cnt = bytearray(), 0, 0

    def put(self, value: int, n: int) -> None:
        self.buf |= value << self.cnt
        self.cnt += n
        while self.cnt >= 8:
            self.out.append(self.buf & 0xFF)
            self.buf >>= 8
            self.cnt -= 8

    def code(self, table, sym: int) -> None:
        """One symbol of a fixed code, inverted and most significant bit first,
        as explode's decode() reads it."""
        count, symbol = table
        p = symbol.index(sym)
        first = index = 0
        for n in range(1, explode.MAXBITS + 1):
            if p < index + count[n]:
                value = first + p - index
                for i in range(n - 1, -1, -1):
                    self.put(((value >> i) & 1) ^ 1, 1)
                return
            index += count[n]
            first = (first + count[n]) << 1
        raise AssertionError(f"symbol {sym} has no code")

    def bytes(self) -> bytes:
        return bytes(self.out) + (bytes([self.buf]) if self.cnt else b"")


def implode(data: bytes, coded: bool = True, dict_bits: int = 6, window: int = 64) -> bytes:
    """A PKWARE DCL stream: greedy matches up to `window` bytes back, literals
    Huffman coded or plain."""
    w = BitWriter()
    w.put(1 if coded else 0, 8)
    w.put(dict_bits, 8)
    i = 0
    while i < len(data):
        best, best_d = 0, 0
        for d in range(1, min(i, window) + 1):
            n = 0
            while i + n < len(data) and n < 518 and data[i + n - d] == data[i + n]:
                n += 1
            if n > best:
                best, best_d = n, d
        if best >= 3 or (best == 2 and best_d <= 4 << 2):
            w.put(1, 1)
            sym = next(s for s in range(16)
                       if explode.BASE[s] <= best < explode.BASE[s] + (1 << explode.EXTRA[s]))
            w.code(explode._LEN, sym)
            w.put(best - explode.BASE[sym], explode.EXTRA[sym])
            low = 2 if best == 2 else dict_bits
            w.code(explode._DIST, (best_d - 1) >> low)
            w.put((best_d - 1) & ((1 << low) - 1), low)
            i += best
        else:
            w.put(0, 1)
            if coded:
                w.code(explode._LIT, data[i])
            else:
                w.put(data[i], 8)
            i += 1
    w.put(1, 1)
    w.code(explode._LEN, 15)
    w.put(255, 8)                                       # length 519: the end
    return w.bytes()


def write_grp(frames: list, offsets=None) -> bytes:
    """A GRP file: every row coded with transparent runs, repeats and literals."""
    h = max(f.shape[0] for f in frames)
    w = max(f.shape[1] for f in frames)
    offsets = offsets or [(0, 0)] * len(frames)
    head = struct.pack("<HHH", len(frames), w, h)
    body = bytearray()
    base = 6 + 8 * len(frames)
    entries = []
    for f, (x, y) in zip(frames, offsets):
        fh, fw = f.shape
        table_at = base + len(body)
        rows = [_rle(bytes(r)) for r in f.astype(np.uint8)]
        table, pos = bytearray(), 2 * fh
        for r in rows:
            table += struct.pack("<H", pos)
            pos += len(r)
        body += table + b"".join(rows)
        entries.append(struct.pack("<BBBBI", x, y, fw, fh, table_at))
    return head + b"".join(entries) + bytes(body)


def _rle(row: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(row):
        j = i
        while j < len(row) and row[j] == row[i] and j - i < 0x3F:
            j += 1
        if row[i] == 0:
            n = min(j - i, 0x7F)
            out.append(0x80 | n)
            i += n
        elif j - i >= 3:
            out += bytes([0x40 | (j - i), row[i]])
            i = j
        else:
            k = i
            while k < len(row) and row[k] != 0 and k - i < 0x3F and \
                    not (k + 2 < len(row) and row[k] == row[k + 1] == row[k + 2]):
                k += 1
            k = max(k, i + 1)
            out.append(k - i)
            out += row[i:k]
            i = k
    return bytes(out)


SECTOR_SHIFT = 0                                         # 512-byte sectors


def _compress(method: str, chunk: bytes) -> bytes:
    if method == "zlib":
        return bytes([mpq.ZLIB]) + zlib.compress(chunk, 9)
    if method == "bzip2":
        return bytes([mpq.BZIP2]) + bz2.compress(chunk)
    if method == "pkware":
        return bytes([mpq.PKWARE]) + implode(chunk)
    if method == "implode":
        return implode(chunk)
    raise AssertionError(method)


def write_mpq(files: dict, prefix: bytes = b"", hash_size: int = 16) -> bytes:
    """An MPQ v1 archive. `files` maps a name to (data, method, options):
    method "stored", "zlib", "bzip2", "pkware" (COMPRESS with mask 0x08),
    "implode" (the old IMPLODE flag), "single" (one zlib unit), or "raw" and
    "rawimplode" (`data` is the one sector as stored, e.g. a test vector, under
    COMPRESS or IMPLODE; the unpacked size is the 4th item); options
    is a set of "encrypt", "fix_key", "locale"."""
    sector = 512 << SECTOR_SHIFT
    body, blocks, hashes = bytearray(), [], [(0xFFFFFFFF, 0xFFFFFFFF, 0xFFFF, 0xFFFF, mpq.EMPTY)] * hash_size
    for name, (data, method, options, *rest) in files.items():
        size = rest[0] if rest else len(data)
        offset = 32 + len(body)
        flags = mpq.EXISTS
        if method in ("zlib", "bzip2", "pkware", "raw"):
            flags |= mpq.COMPRESS
        elif method in ("implode", "rawimplode"):
            flags |= mpq.IMPLODE
        elif method == "single":
            flags |= mpq.SINGLE_UNIT | mpq.COMPRESS
        if "encrypt" in options:
            flags |= mpq.ENCRYPTED
        if "fix_key" in options:
            flags |= mpq.FIX_KEY
        key = mpq.file_key(name, offset, size, flags) if "encrypt" in options else None
        if method == "single":
            blob = bytes([mpq.ZLIB]) + zlib.compress(data)
            if key is not None:
                blob = mpq.encrypt(blob, key)
        elif method == "stored":
            blob = b"".join(mpq.encrypt(data[i:i + sector], key + k) if key is not None
                            else data[i:i + sector]
                            for k, i in enumerate(range(0, len(data), sector)))
        else:
            if method in ("raw", "rawimplode"):
                sectors = [data]
            else:
                sectors = []
                for i in range(0, len(data), sector):
                    chunk = data[i:i + sector]
                    c = _compress(method, chunk)
                    sectors.append(c if len(c) < len(chunk) else chunk)
            table, pos = [], 4 * (len(sectors) + 1)
            for s in sectors:
                table.append(pos)
                pos += len(s)
            table.append(pos)
            tb = struct.pack(f"<{len(table)}I", *table)
            if key is not None:
                tb = mpq.encrypt(tb, key - 1)
                sectors = [mpq.encrypt(s, key + k) for k, s in enumerate(sectors)]
            blob = tb + b"".join(sectors)
        blocks.append((offset, len(blob), size, flags))
        body += blob
        i = mpq.hash_string(name, mpq.HASH_OFFSET) & (hash_size - 1)
        while hashes[i][4] != mpq.EMPTY:
            i = (i + 1) & (hash_size - 1)
        locale = 0x407 if "locale" in options else 0
        hashes[i] = (mpq.hash_string(name, mpq.HASH_A), mpq.hash_string(name, mpq.HASH_B),
                     locale, 0, len(blocks) - 1)
    ht = b"".join(struct.pack("<IIHHI", *h) for h in hashes)
    bt = b"".join(struct.pack("<IIII", *b) for b in blocks)
    hash_pos = 32 + len(body)
    block_pos = hash_pos + len(ht)
    head = struct.pack("<4sIIHHIIII", mpq.MAGIC, 32, block_pos + len(bt), 0, SECTOR_SHIFT,
                       hash_pos, block_pos, hash_size, len(blocks))
    archive = (head + bytes(body) + mpq.encrypt(ht, mpq.hash_string("(hash table)", mpq.HASH_KEY))
               + mpq.encrypt(bt, mpq.hash_string("(block table)", mpq.HASH_KEY)))
    return prefix + archive


# Every unit id the spec draws, and a few more.
UNIT_IDS = 160


def wireframes(seed: int) -> bytes:
    return write_grp([blob_frame(20, 20, i + seed) for i in range(UNIT_IDS)])


def wpe() -> bytes:
    return b"".join(bytes([i, i, i, 0]) for i in range(256))


def make_game_files(folder: Path, upper: bool = True, brood: bool = True) -> None:
    """StarDat.mpq (palette, wireframes) and BrooDat.mpq (newer wireframes,
    imploded with coded literals and encrypted), as Brood War has them."""
    folder.mkdir(parents=True, exist_ok=True)
    cap = (lambda s: s.replace("stardat", "StarDat").replace("broodat", "BrooDat")) if upper else str
    star = {sc.PALETTE: (wpe(), "zlib", {"encrypt", "fix_key"}),
            sc.WIREFRAMES: (wireframes(0), "bzip2", {"encrypt"}),
            sc.CMDICONS: (write_grp([blob_frame(14, 16, i) for i in range(UNIT_IDS)]), "zlib", set())}
    (folder / cap("stardat.mpq")).write_bytes(write_mpq(star, hash_size=8))
    if brood:
        bw = {sc.WIREFRAMES: (wireframes(1), "pkware", {"encrypt", "fix_key"})}
        (folder / cap("broodat.mpq")).write_bytes(write_mpq(bw, hash_size=4))


# --------------------------------------------------------------------------- #

class ExplodeTest(unittest.TestCase):

    def test_the_blast_c_test_vector(self):
        self.assertEqual(explode.explode(BLAST_VECTOR), b"AIAIAIAIAIAIA")

    def test_the_fixed_codes_are_complete(self):
        """blast.c's tables: 256 literals, 16 lengths, 64 distances, each a
        complete prefix code (Kraft sum 1)."""
        for rep, n in ((explode.LITLEN, 256), (explode.LENLEN, 16), (explode.DISTLEN, 64)):
            lengths = explode.lengths(rep)
            self.assertEqual(len(lengths), n)
            self.assertEqual(sum(2 ** -k for k in lengths if k), 1.0)

    def test_round_trips_with_coded_and_plain_literals(self):
        data = bytes(range(256)) + b"abcabcabcabc" * 40 + bytes(600) + b"\x01\x02" * 30
        for coded in (True, False):
            for dict_bits in (4, 5, 6):
                with self.subTest(coded=coded, dict_bits=dict_bits):
                    self.assertEqual(explode.explode(implode(data, coded, dict_bits)), data)

    def test_damaged_streams_are_refused(self):
        with self.assertRaises(ValueError):
            explode.explode(BLAST_VECTOR[:4])              # ends early
        with self.assertRaises(ValueError):
            explode.explode(b"\x02\x04" + BLAST_VECTOR[2:])  # bad literal flag
        with self.assertRaises(ValueError):
            explode.explode(b"\x00\x07" + BLAST_VECTOR[2:])  # bad dictionary size
        with self.assertRaisesRegex(ValueError, "grows past"):
            explode.explode(BLAST_VECTOR, max_size=5)
        # A copy from before the start of the output.
        w = BitWriter()
        w.put(0, 8)
        w.put(4, 8)
        w.put(1, 1)
        w.code(explode._LEN, 0)                              # length 3
        w.code(explode._DIST, 0)
        w.put(0, 4)
        with self.assertRaisesRegex(ValueError, "too far back"):
            explode.explode(w.bytes() + b"\0\0")


class MpqTest(unittest.TestCase):

    DATA = bytes((i * 7) % 251 for i in range(1500)) + bytes(700)

    def test_the_table_keys_are_the_published_constants(self):
        self.assertEqual(mpq.hash_string("(hash table)", mpq.HASH_KEY), 0xC3AF3770)
        self.assertEqual(mpq.hash_string("(block table)", mpq.HASH_KEY), 0xEC83B3A3)
        self.assertEqual(mpq.hash_string("unit/a.grp", 1), mpq.hash_string("UNIT\\A.GRP", 1))

    def test_every_storage_method_reads_back(self):
        files = {f"unit\\{m}{'_e' if enc else ''}.grp": (self.DATA, m, {"encrypt", "fix_key"} if enc else set())
                 for m in ("stored", "zlib", "bzip2", "pkware", "implode", "single")
                 for enc in (False, True)}
        a = mpq.Archive(write_mpq(files, hash_size=16))
        for name in files:
            with self.subTest(name):
                self.assertIn(name, a)
                self.assertEqual(a.get(name), self.DATA)
        self.assertIsNone(a.get("unit\\missing.grp"))
        self.assertNotIn("unit\\missing.grp", a)

    def test_the_blast_vector_as_an_imploded_sector(self):
        """The vector stored as the one sector of a 13-byte file, once under
        the old IMPLODE flag and once as a COMPRESS sector with mask 0x08."""
        files = {"a.txt": (BLAST_VECTOR, "rawimplode", set(), 13),
                 "b.txt": (bytes([mpq.PKWARE]) + BLAST_VECTOR, "raw", {"encrypt"}, 13)}
        a = mpq.Archive(write_mpq(files, hash_size=4))
        self.assertEqual(a.get("a.txt"), b"AIAIAIAIAIAIA")
        self.assertEqual(a.get("b.txt"), b"AIAIAIAIAIAIA")

    def test_an_archive_after_a_prefix_is_found(self):
        a = mpq.Archive(write_mpq({"x": (b"hello", "stored", set())}, prefix=bytes(1024), hash_size=4))
        self.assertEqual(a.base, 1024)
        self.assertEqual(a.get("x"), b"hello")

    def test_another_language_is_a_fallback(self):
        a = mpq.Archive(write_mpq({"x": (b"german", "stored", {"locale"})}, hash_size=4))
        self.assertEqual(a.get("x"), b"german")

    def test_damaged_archives_are_refused(self):
        with self.assertRaisesRegex(ValueError, "not an MPQ"):
            mpq.Archive(bytes(2048))
        good = write_mpq({"x": (self.DATA, "zlib", set())}, hash_size=4)
        with self.assertRaisesRegex(ValueError, "past the end"):
            mpq.Archive(good[:-8])
        a = mpq.Archive(good)
        offset, csize, size, flags = a.blocks[0]
        a.blocks[0] = (offset, csize, 1 << 31, flags)
        with self.assertRaisesRegex(ValueError, "claims"):
            a.get("x")
        a.blocks[0] = (offset, csize + 10 ** 6, size, flags)
        with self.assertRaises(ValueError):
            a.get("x")

    def test_an_archive_on_disk_is_read_in_parts(self):
        """open() keeps the path, not the bytes; a header past the first
        scan chunk and a file deleted after opening are handled."""
        files = {f"unit\\{m}.grp": (self.DATA, m, {"encrypt", "fix_key"})
                 for m in ("stored", "zlib", "pkware", "single")}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "StarDat.mpq"
            path.write_bytes(write_mpq(files, prefix=bytes(3 * 512), hash_size=16))
            with mock.patch.object(mpq, "SCAN_CHUNK", 1024):
                a = mpq.Archive.open(path)
            self.assertIsNone(a.data)
            self.assertEqual(a.base, 3 * 512)
            for name in files:
                with self.subTest(name):
                    self.assertEqual(a.get(name), self.DATA)
            path.unlink()
            with self.assertRaises(ValueError):           # what build.render skips per key
                a.get("unit\\zlib.grp")

    def test_sound_compressions_are_refused(self):
        raw = bytes([mpq.HUFFMAN]) + b"\0" * 8
        a = mpq.Archive(write_mpq({"x.wav": (raw, "raw", set(), 64)}, hash_size=4))
        with self.assertRaisesRegex(ValueError, "not supported"):
            a.get("x.wav")


class GrpTest(unittest.TestCase):

    def test_frames_round_trip_with_offsets(self):
        frames = [blob_frame(12, 10, i) for i in range(3)]
        frames[1][3, :] = 9                                  # a repeat run
        data = write_grp(frames, offsets=[(0, 0), (2, 1), (0, 0)])
        self.assertEqual(grp.frame_count(data), 3)
        np.testing.assert_array_equal(grp.frame(data, 0), frames[0])
        got = grp.frame(data, 1)
        self.assertEqual(got.shape, (13, 12))
        np.testing.assert_array_equal(got[1:, 2:], frames[1])
        with self.assertRaises(IndexError):
            grp.frame(data, 3)

    def test_a_damaged_row_is_refused(self):
        data = bytearray(write_grp([blob_frame(6, 6, 0)]))
        table = struct.unpack_from("<I", data, 6 + 4)[0]
        first = table + struct.unpack_from("<H", data, table)[0]
        data[first] = 0x3F                                   # a literal past the row
        with self.assertRaises(ValueError):
            grp.frame(bytes(data), 0)
        with self.assertRaises(ValueError):
            grp.frame(bytes(data[:first + 1]), 0)

    def test_a_box_larger_than_any_frame_is_refused(self):
        data = bytearray(write_grp([blob_frame(6, 6, 0)]))
        struct.pack_into("<HH", data, 2, 0xFFFF, 0xFFFF)     # 65535 x 65535: 4 GiB
        with self.assertRaisesRegex(ValueError, "larger than a GRP frame"):
            grp.frame(bytes(data), 0)
        struct.pack_into("<HH", data, 2, grp.MAX_BOX, grp.MAX_BOX)
        self.assertEqual(grp.frame(bytes(data), 0).shape, (grp.MAX_BOX, grp.MAX_BOX))

    def test_the_wpe_palette(self):
        pal = grp.wpe_palette(wpe())
        self.assertEqual(pal.shape, (256, 3))
        self.assertEqual(tuple(pal[200]), (200, 200, 200))
        with self.assertRaises(ValueError):
            grp.wpe_palette(b"\0" * 100)


class FindTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        for p in (mock.patch.object(Path, "home", return_value=self.home),
                  mock.patch.dict(os.environ, {"PROGRAMFILES": "", "PROGRAMFILES(X86)": "",
                                               "WINEPREFIX": ""}),
                  mock.patch.object(sc, "_casc_logged", set())):
            p.start()
            self.addCleanup(p.stop)

    def test_a_configured_folder_in_either_case(self):
        for upper in (True, False):
            d = self.home / f"sc{upper}"
            make_game_files(d, upper=upper)
            self.assertEqual(sorted(sc.find(str(d))), ["broodat.mpq", "stardat.mpq"])

    def test_without_stardat_there_is_nothing(self):
        d = self.home / "x"
        d.mkdir()
        (d / "BrooDat.mpq").write_bytes(b"")
        self.assertIsNone(sc.find(str(d)))

    def test_a_remastered_install_is_named_in_the_log_once(self):
        d = self.home / "StarCraft"
        (d / "Data" / "data").mkdir(parents=True)
        (d / ".build.info").write_text("x")
        with self.assertLogs("PolyHost", "INFO") as logs:
            self.assertIsNone(sc.find(str(d)))
            self.assertIsNone(sc.find(str(d)))
        self.assertEqual(len(logs.output), 1)
        self.assertIn("CASC", logs.output[0])

    def test_the_wine_prefix_is_searched(self):
        self.assertIsNone(sc.find(""))
        d = self.home / ".wine" / "drive_c" / "Program Files (x86)" / "Starcraft"
        make_game_files(d)
        self.assertEqual(sc.find("")["stardat.mpq"].parent, d)

    def test_an_install_beside_starcraft_ii_is_found_from_its_folder(self):
        pf = self.home / "Program Files (x86)"
        sc2 = pf / "StarCraft II" / "Versions" / "Base75689"
        sc2.mkdir(parents=True)
        make_game_files(pf / "StarCraft")
        self.assertIsNone(sc.find(""))
        self.assertEqual(sc.find("", hint=sc2)["stardat.mpq"].parent, pf / "StarCraft")


class SourceTest(unittest.TestCase):

    def test_brood_war_files_take_priority_and_frames_draw(self):
        with tempfile.TemporaryDirectory() as d:
            make_game_files(Path(d))
            src = sc.open_source(sc.find(d))
            np.testing.assert_array_equal(src.frame(sc.WIREFRAMES, 5), blob_frame(20, 20, 6))
            for recipe in ({"wireframe": 0}, {"cmdicon": 7}, {"wireframe": 3, "flat": True}):
                m = sc.draw(src, recipe, (40, 40))
                self.assertTrue(m.any(), recipe)
                self.assertLessEqual(m.shape[0], 40)
                self.assertLessEqual(m.shape[1], 40)
            with self.assertRaises(IndexError):
                sc.draw(src, {"wireframe": UNIT_IDS}, (40, 40))
            with self.assertRaises(ValueError):
                sc.draw(src, {"sprite": 1}, (40, 40))

    def test_without_brood_war_the_original_files_are_used(self):
        with tempfile.TemporaryDirectory() as d:
            make_game_files(Path(d), brood=False)
            src = sc.open_source(sc.find(d))
            np.testing.assert_array_equal(src.frame(sc.WIREFRAMES, 5), blob_frame(20, 20, 5))


class BuildTest(unittest.TestCase):
    """The StarCraft II overlay drawn from synthetic files: the keys the spec
    redraws change on every tier, in both files, for every race, and no other
    key does."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.data, cls.cache = root / "sc", root / "cache"
        make_game_files(cls.data)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_race(self):
        spec = build.load_spec(SPEC)
        stems = set(spec["game_assets"]["icons"])
        want = {}
        for b in build.bindings(spec):
            if Path(b["icon"]).stem in stems:
                want.setdefault(build.modifier(b.get("mods")), set()).add(
                    KeyCode[f"KC_{str(b['key']).upper()}"].value)
        self.assertEqual(set(want), {Modifier.NO_MOD, Modifier.CTRL, Modifier.ALT, Modifier.SHIFT,
                                     Modifier.ALT_SHIFT})
        built = {}
        for race in RACES:
            settings = {"game_sc1_data_dir": str(self.data), "game_sc1_race": race}
            for template in ("starcraft2_template.mods.png", "starcraft2_template.combo.mods.png"):
                with self.subTest(race=race, template=template):
                    out = build.build(template, SPEC, settings.get, self.cache)
                    self.assertIsNotNone(out)
                    built[race, template] = out
                    for mod, keys in want.items():
                        if (mod == Modifier.ALT_SHIFT) != (".combo." in template):
                            continue
                        shipped, patched = cells(OVERLAYS / template, mod), cells(out, mod)
                        for kc in set(shipped) | set(patched):
                            changed = shipped.get(kc) != patched.get(kc)
                            self.assertEqual(changed, kc in keys, f"{mod.name} 0x{kc:02x}")
        names = {built[r, "starcraft2_template.mods.png"].name for r in RACES}
        self.assertEqual(len(names), 3, "each race has its own cached copy")

    def test_without_game_files_there_is_no_copy(self):
        with tempfile.TemporaryDirectory() as d:
            settings = {"game_sc1_data_dir": d, "game_sc1_race": "zerg"}
            self.assertIsNone(build.build("starcraft2_template.mods.png", SPEC, settings.get, Path(d)))


class SpecTest(unittest.TestCase):

    def test_every_recipe_replaces_a_bound_icon(self):
        spec = build.load_spec(SPEC)
        stems = {Path(b["icon"]).stem for b in build.bindings(spec)}
        for race in RACES:
            got = build.recipes(spec, race)
            self.assertEqual(set(got) - stems, set(), race)
            for stem, recipe in got.items():
                base = recipe.get("plus", recipe.get("of"))
                if base is not None:
                    self.assertIn(base, got, f"{stem} marks nothing")
                else:
                    self.assertIn("wireframe", recipe, stem)

    def test_the_unit_ids_are_bwapi_s(self):
        """BWAPI's UnitType enum (bwapi/include/BWAPI/UnitType.h, read
        2026-10-30); the spec's comment names the units in this order."""
        ids = {"terran": [0, 32, 34, 1, 2, 5, 3, 8, 12, 7],
               "protoss": [65, 66, 67, 61, 68, 83, 60, 70, 72, 64],
               "zerg": [37, 38, 103, 39, 43, 44, 45, 46, 42, 41]}
        spec = build.load_spec(SPEC)
        for race, want in ids.items():
            got = build.recipes(spec, race)
            self.assertEqual([got[f"group{d}"]["wireframe"] for d in "1234567890"], want, race)

    def test_the_mapping_registers_both_files(self):
        import yaml
        with open(build.RES / "overlay-mapping.poly.yaml", encoding="utf-8") as f:
            mapping = yaml.safe_load(f)
        with mock.patch.dict(game_assets._specs, clear=True):
            game_assets.register_mapping(mapping)
            for template in ("starcraft2_template.mods.png", "starcraft2_template.combo.mods.png"):
                self.assertEqual(game_assets._specs.get(template), SPEC, template)

    def test_the_shipped_groups_use_the_reader_s_marks(self):
        """The shipped Ctrl, Shift, Alt and Shift+Alt groups are the plain group
        with dither's marks, so the two sets look alike."""
        from PIL import Image
        icons = SPEC.parent / "icons"

        def load(stem):
            return np.asarray(Image.open(icons / f"{stem}.png").convert("RGBA").getchannel("A")) > 127

        for d in "1234567890":
            g = load(f"group{d}")
            np.testing.assert_array_equal(load(f"groupnew{d}"), dither.with_plus(g))
            for stem, kind in (("groupadd", "ring"), ("groupsteal", "box"), ("groupaddsteal", "disc")):
                np.testing.assert_array_equal(load(f"{stem}{d}"), dither.with_mark(g, kind), f"{stem}{d}")


if __name__ == "__main__":
    unittest.main()
