"""Check that an installer-made checkout has exactly the files it should.

    .venv\\Scripts\\python.exe scripts\\check_install_tree.py <install dir> [<git checkout>]

Run by .github/workflows/windows-installer.yml after `scripts/install.ps1`,
and by .github/workflows/app-installer.yml after `scripts/install-app.*`.
The app installer makes no git checkout, so that workflow names the
checkout of the same commit as the second argument.
The expected set is every file of the checkout's HEAD that
`updater.is_build_only()` keeps, so the installers' sparse patterns and the
updater's rule are compared on a real clone. It also imports the modules a
fresh Windows install needs at startup, which fails when pip left a package
out. Exit status 0 when everything matches, 1 otherwise.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Written by the installer or by Python itself, not part of the checkout.
# .python is the interpreter uv downloads for the app installer.
GENERATED_DIRS = {".git", ".venv", ".python", "__pycache__"}
GENERATED_SUFFIXES = (".egg-info",)


def expected_files(checkout: Path) -> set[str]:
    from polyhost.services import updater

    # Audit: a fixed git argv on the install dir the caller named; no shell.
    listing = subprocess.run(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        ["git", "-C", str(checkout), "ls-tree", "-r", "--name-only", "HEAD"],
        capture_output=True, text=True, encoding="utf-8", check=True).stdout
    kept = set()
    for rel in listing.splitlines():
        parts = rel.split("/")
        dirs = ["/".join(parts[:i]) for i in range(1, len(parts))]
        if any(updater.is_build_only(d, True) for d in dirs):
            continue
        if not updater.is_build_only(rel):
            kept.add(rel)
    return kept


def files_on_disk(root: Path) -> set[str]:
    found = set()
    for path in root.rglob("*"):
        parts = path.relative_to(root).parts
        if any(p in GENERATED_DIRS or p.endswith(GENERATED_SUFFIXES) for p in parts):
            continue
        if path.is_file():
            found.add("/".join(parts))
    return found


def check_imports() -> list[str]:
    errors = []
    for module in ("PyQt5.QtWidgets", "numpy", "PIL", "yaml", "uharfbuzz",
                   "freetype", "fontTools", "serial", "pywinctl",
                   "polyhost.device.hid_helper", "polyhost.cli.polyctl"):
        try:
            __import__(module)
        # SystemExit too: pymonctl (under pywinctl) calls sys.exit() when it
        # finds no display server, and that must be reported, not end the run.
        except (Exception, SystemExit) as exc:  # report every failure, not only the first
            errors.append("import %s failed: %s: %s" % (module, type(exc).__name__, exc))
    return errors


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print(__doc__)
        return 2
    root = Path(argv[1]).resolve()
    checkout = Path(argv[2]).resolve() if len(argv) == 3 else root
    sys.path.insert(0, str(root))
    expected = expected_files(checkout)
    on_disk = files_on_disk(root)
    missing = sorted(expected - on_disk)
    extra = sorted(on_disk - expected)
    print("expected %d files, found %d on disk" % (len(expected), len(on_disk)))
    for rel in missing[:50]:
        print("MISSING  " + rel)
    for rel in extra[:50]:
        print("EXTRA    " + rel)
    errors = check_imports()
    for line in errors:
        print("ERROR    " + line)
    if missing or extra or errors:
        print("FAILED: %d missing, %d extra, %d import error(s)"
              % (len(missing), len(extra), len(errors)))
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
