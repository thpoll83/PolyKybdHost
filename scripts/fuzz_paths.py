#!/usr/bin/env python3
"""List the polyhost files the property/fuzz tests import, and check the fuzz workflow.

    python scripts/fuzz_paths.py          # print the files, one per line (runs tests/fuzz)
    python scripts/fuzz_paths.py --check  # exit 1 if .github/workflows/host-fuzz.yml's
                                          # pull_request paths: misses one, or lists a
                                          # polyhost file that no fuzz module imports

The fuzz workflow runs on a PR only when one of these files (or tests/fuzz/) changes, so
its paths: list must follow what tests/fuzz imports. Run from the repository root, with
the test requirements installed (hypothesis, requirements.txt).
"""
import glob
import importlib
import io
import os
import sys
import unittest

WORKFLOW = ".github/workflows/host-fuzz.yml"


def imported_files():
    """Import every fuzz module AND run it on the fixed-seed `paths` profile (about 5 s), then
    collect the polyhost modules that were loaded. Running matters: some parsers import
    a module inside a function (the tutorial loader imports macro_label for a `say`
    step), and importing the test module alone never loads it."""
    root = os.getcwd()
    sys.path.insert(0, root)
    # A fixed seed, so the modules a run reaches are the same every time (profile.py).
    os.environ["POLYKYBD_HYPOTHESIS_PROFILE"] = "paths"
    names = [p[:-3].replace(os.sep, ".") for p in sorted(glob.glob("tests/fuzz/*_fuzz_test.py"))]
    for name in names:
        importlib.import_module(name)
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    if not result.wasSuccessful():
        sys.exit(f"tests/fuzz failed ({len(result.failures)} failures, "
                 f"{len(result.errors)} errors); fix them before listing imports")
    prefix = os.path.join(root, "polyhost") + os.sep
    return sorted({os.path.relpath(m.__file__, root).replace(os.sep, "/")
                   for m in list(sys.modules.values())
                   if getattr(m, "__file__", None) and m.__file__.startswith(prefix)})


def workflow_paths():
    import yaml
    with open(WORKFLOW, encoding="utf-8") as f:
        wf = yaml.safe_load(f)
    on = wf.get(True) or wf.get("on")
    return on["pull_request"]["paths"]


def main():
    files = imported_files()
    if "--check" not in sys.argv:
        print("\n".join(files))
        return 0
    listed = workflow_paths()
    listed_py = {p for p in listed if p.startswith("polyhost/")}
    missing = [f for f in files if f not in listed_py]
    extra = sorted(listed_py - set(files))
    for f in missing:
        print("NOT IN paths:", f)
    for f in extra:
        print("in paths: but not imported by tests/fuzz:", f)
    print(f"{len(files)} imported polyhost files, {len(listed_py)} listed: "
          + ("OK" if not (missing or extra) else f"{len(missing) + len(extra)} problem(s)"))
    return 1 if (missing or extra) else 0


if __name__ == "__main__":
    sys.exit(main())
