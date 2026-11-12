"""Regenerate every overlay spec in one process and print the ones that fail.

    .venv/bin/python .claude/skills/generate-app-overlays/regen_all.py
    git status --short polyhost/res/overlays/    # what changed

One process imports the generator once, so the 294 specs take about two minutes
instead of one interpreter start per spec. Run it after any change to
scripts/generate_app_overlays.py, and on main before that, so drift already on
main is not counted as your change.
"""
import contextlib
import glob
import io
import os
import sys
import traceback
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
os.chdir(REPO)
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))
import generate_app_overlays as g  # noqa: E402

LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
specs = []
for y in sorted(set(glob.glob("polyhost/res/overlay_sources/*/bindings.yaml")
                    + glob.glob("polyhost/res/overlay_sources/*/*.yaml"))):
    try:
        with open(y, encoding="utf-8") as fh:
            d = yaml.load(fh, Loader=LOADER)
    except Exception:
        continue
    if isinstance(d, dict) and "bindings" in d:
        specs.append(y)

failed = 0
for y in specs:
    sys.argv = ["generate_app_overlays.py", y]
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = g.main()
    except SystemExit as e:
        rc = e.code
    except Exception:
        rc = "EXC " + traceback.format_exc().splitlines()[-1]
    if rc not in (0, None):
        failed += 1
        print("FAIL", y, rc, out.getvalue()[-300:].replace("\n", " | "))
print(len(specs), "specs,", failed, "failed")
sys.exit(1 if failed else 0)
