"""What would a bigger PRC context buy? A study, not a shipped format.

PRC (cmd 41) predicts each pixel from 10 already-coded neighbours through a
frozen 1 KB table. This tool measures, on the shipped templates, how much a
12-, 14- or 16-pixel context would save. The result (2026-09-29) is recorded in
docs/FUTURE_WORK.md: about 0.3 reports per cold switch once the icon library
fills its images, so it was not pursued.

    python tools/prc_context_study.py            # report counts per context size
    python tools/prc_context_study.py --greedy   # pick the best extra pixels first

Every number is HELD OUT: 5 folds split by app (an app's OS variants stay in one
fold), so a table never codes images of an app it was trained on. A bigger table
trained and measured on the same images memorises them and looks up to 3 points
better than it is. Reports are packed the way PrcReportPacker packs them; an
image whose record does not fit one report falls back to the smallest older
encoding.
"""
import argparse
import glob
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from polyhost.device.device_settings import DeviceSettings  # noqa: E402
from polyhost.device.im_converter import ImageConverter  # noqa: E402
from polyhost.device.keys import Modifier  # noqa: E402
from polyhost.device.poly_kybd import PolyKybd  # noqa: E402
from polyhost.util import prc_codec as pc  # noqa: E402

BASE = pc.TEMPLATE
# The greedy search's pick, in order (--greedy reproduces it).
GREEDY = ((-3, 2), (-3, -2), (-1, -3), (-3, 1), (0, -3), (-2, -3))
CAP = DeviceSettings().MAX_PAYLOAD_BYTES_PER_REPORT
FOLDS = 5


def contexts(roi, tpl):
    a = np.asarray(roi, dtype=np.uint32)
    h, w = a.shape
    p = np.zeros((h + 3, w + 8), dtype=np.uint32)
    p[3:, 4:w + 4] = a
    ctx = np.zeros((h, w), dtype=np.uint32)
    for dy, dx in tpl:
        ctx = (ctx << 1) | p[3 + dy:3 + dy + h, 4 + dx:4 + dx + w]
    return ctx.flatten()


def train(rois, tpl):
    """Same estimator as prc_codec.train, for any template size."""
    n = np.zeros((1 << len(tpl), 2), dtype=np.int64)
    for roi in rois:
        np.add.at(n, (contexts(roi, tpl), np.asarray(roi, dtype=np.uint8).flatten()), 1)
    p0 = np.rint(256 * (n[:, 0] + 0.5) / (n.sum(axis=1) + 1))
    return np.clip(p0, 1, 255).astype(np.int64)


def encode_len(roi, tpl, tbl):
    enc = pc._Encoder()
    for v, c in zip(np.asarray(roi, dtype=np.uint8).flatten().tolist(), contexts(roi, tpl).tolist()):
        enc.bit(v, int(tbl[c]))
    return len(enc.finish())


def app_of(path):
    name = re.sub(r"_template$", "", os.path.basename(path).split(".")[0])
    return re.sub(r"_(linux|gnome|kde|mac|macos|win|windows)$", "", name)


def load():
    """{template path: [(image bytes, ROI, fallback reports)]}"""
    per_file = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "polyhost", "res", "overlays", "*.png"))):
        conv = ImageConverter(DeviceSettings())
        if not conv.open(path):
            continue
        items = []
        for mod in Modifier:
            for ov in (conv.extract_overlays(mod) or {}).values():
                m = np.unpackbits(np.frombuffer(ov.all_bytes, dtype=np.uint8)).reshape(40, 72).astype(bool)
                roi = pc.crop_to_roi(m)
                if roi is not None:
                    fb = min(ov.all_msgs, ov.compressed_msgs, ov.roi_msgs, ov.compressed_roi_msgs)
                    items.append((ov.all_bytes, roi, fb))
        per_file[path] = items
    return per_file


def switch_reports(seq):
    """Reports for one cold switch: records packed in order, fallbacks alone."""
    reports, fill = 0, None
    for n, fb in seq:
        rec = pc.RECORD_HDR + n
        if n > pc.MAX_RECORD_PAYLOAD or rec > CAP:
            reports += fb
            continue
        if fill is None or fill + rec > CAP:
            reports, fill = reports + 1, 0
        fill += rec
    return reports


def folds(per_file):
    apps = sorted({app_of(p) for p in per_file})
    return {a: int(hashlib.sha256(a.encode()).hexdigest(), 16) % FOLDS for a in apps}


def report_counts(per_file, lib):
    fold_of = folds(per_file)
    uniq = {k: roi for it in per_file.values() for k, roi, _ in it}
    print(f"{len(per_file)} templates, {len(fold_of)} apps, {len(uniq)} distinct images, "
          f"{len(lib & set(uniq))} in icons.plyi; report capacity {CAP} B")
    print("context  table     payload   cold reports   ...not in library")
    for size in (10, 12, 14, 16):
        tpl = BASE + GREEDY[:size - 10]
        lens = {}
        for f in range(FOLDS):
            keys = {k for p, it in per_file.items() if fold_of[app_of(p)] != f for k, _, _ in it}
            tbl = train([uniq[k] for k in keys], tpl)
            for p, it in per_file.items():
                if fold_of[app_of(p)] == f:
                    for k, roi, _ in it:
                        lens[(p, k)] = encode_len(roi, tpl, tbl)
        payload = sum(lens.values())
        cold = sum(switch_reports([(lens[(p, k)], fb) for k, _, fb in it]) for p, it in per_file.items())
        rest = sum(switch_reports([(lens[(p, k)], fb) for k, _, fb in it if k not in lib])
                   for p, it in per_file.items())
        print(f"{size:5d} px  {1 << len(tpl):6d} B  {payload:8d} B  {cold:12d}  {rest:17d}")


def greedy(per_file, until=18):
    """Add, one at a time, the candidate pixel that most lowers the held-out
    ideal code length (sum of -log2 p), and print each step."""
    fold_of = folds(per_file)
    uniq, key_fold = {}, {}
    for p, it in per_file.items():
        for k, roi, _ in it:
            uniq.setdefault(k, roi)
            key_fold.setdefault(k, fold_of[app_of(p)])
    keys = sorted(uniq)
    bits = {k: np.asarray(uniq[k], dtype=np.uint8).flatten() for k in keys}

    def cost(tpl):
        ctx = {k: contexts(uniq[k], tpl) for k in keys}
        total = 0.0
        for f in range(FOLDS):
            n = np.zeros((1 << len(tpl), 2), dtype=np.int64)
            for k in keys:
                if key_fold[k] != f:
                    np.add.at(n, (ctx[k], bits[k]), 1)
            p0 = np.clip(np.rint(256 * (n[:, 0] + 0.5) / (n.sum(1) + 1)), 1, 255) / 256
            for k in keys:
                if key_fold[k] == f:
                    p = p0[ctx[k]]
                    total += -np.log2(np.where(bits[k] == 0, p, 1 - p)).sum()
        return total / 8

    cands = [(dy, dx) for dy in (-3, -2, -1) for dx in range(-4, 5)] + [(0, -4), (0, -3)]
    tpl = tuple(BASE)
    cands = [c for c in cands if c not in tpl]
    print(f"{len(tpl)} px: {cost(tpl):8.0f} B ideal, held out")
    while len(tpl) < until:
        best = min(cands, key=lambda c: cost(tpl + (c,)))
        tpl += (best,)
        cands.remove(best)
        print(f"{len(tpl)} px: {cost(tpl):8.0f} B  + {best}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--greedy", action="store_true", help="run the pixel selection instead")
    args = ap.parse_args(argv)
    per_file = load()
    if args.greedy:
        greedy(per_file)
    else:
        _, index = PolyKybd._shipped_icon_library()
        report_counts(per_file, set(index))
    return 0


if __name__ == "__main__":
    sys.exit(main())
