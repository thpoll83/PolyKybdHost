"""Install PolyKybdHost from a GitHub release, without git.

    python install_app.py --target DIR [--repo OWNER/NAME] [--ref REF] [--no-launch]

scripts/install-app.sh and scripts/install-app.ps1 run this file with a Python
that uv downloaded into DIR/.python, so the user needs neither git nor Python.
It uses only the standard library, because nothing else is installed yet.

Steps: download the release tarball (the latest release, or REF), extract it
into DIR without the build-only paths, create DIR/.venv, pip-install the
requirements, install the native hidapi library (Linux, macOS), and start the
app. A second run updates DIR in place, as the in-app updater does: files are
copied over, nothing is deleted.

The build-only rule below is a copy of the one in polyhost/services/updater.py:
this file runs before polyhost and its dependencies exist.
tests/scripts/install_app_test.py keeps the two the same.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

DEFAULT_REPO = "thpoll83/PolyKybdHost"
USER_AGENT = "PolyKybdHost-installer"

# Copied from polyhost/services/updater.py (see the module docstring).
BUILD_ONLY_DIRS = ("tests/", "polyhost/res/overlay_sources/")
KEPT_IN_BUILD_ONLY = re.compile(r"polyhost/res/overlay_sources/[^/]+/[^/]+\.yaml")


def is_build_only(rel: str, is_dir: bool = False) -> bool:
    """True for a path of the release tree the app does not need."""
    rel = rel.strip("/")
    for prefix in BUILD_ONLY_DIRS:
        top = prefix.rstrip("/")
        if rel != top and not rel.startswith(prefix):
            continue
        if prefix == "polyhost/res/overlay_sources/":
            depth = rel.count("/") - top.count("/")
            if depth == 0 or (depth == 1 and is_dir):
                return False
            if KEPT_IN_BUILD_ONLY.fullmatch(rel):
                return False
        return True
    return False


def say(msg: str) -> None:
    print(">> " + msg, flush=True)


def fail(msg: str) -> None:
    print("!! " + msg, file=sys.stderr, flush=True)
    sys.exit(1)


def _open(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=60)  # nosec B310: fixed https URLs


def latest_tag(repo: str) -> str:
    """The latest release's tag, from the github.com redirect.

    github.com/<repo>/releases/latest redirects to .../releases/tag/<tag>.
    This avoids api.github.com and its 60-requests-per-hour limit."""
    with _open(f"https://github.com/{repo}/releases/latest") as resp:
        final = resp.geturl()
    marker = "/releases/tag/"
    if marker not in final:
        fail(f"{repo} has no published release ({final}).")
    return urllib.request.unquote(final.split(marker, 1)[1])


def tarball_url(repo: str, ref: str) -> str:
    # archive/<ref> takes a tag, a branch or a commit.
    return f"https://github.com/{repo}/archive/{ref}.tar.gz"


def download(url: str, dest: Path) -> None:
    say(f"Downloading {url}")
    with _open(url) as resp, open(dest, "wb") as fh:
        shutil.copyfileobj(resp, fh, 64 * 1024)
    say(f"Downloaded {dest.stat().st_size / 1e6:.1f} MB.")


def _tree_rel(member_name: str) -> str:
    parts = member_name.strip("/").split("/", 1)
    return parts[1] if len(parts) > 1 else ""


def extract(archive: Path, dest: Path) -> Path:
    """Extract `archive` into `dest` without the build-only paths, refusing
    links and paths outside `dest`. Return the tarball's single top folder."""
    with tarfile.open(archive, "r:gz") as tar:
        members = [m for m in tar.getmembers()
                   if not is_build_only(_tree_rel(m.name), m.isdir())]
        if sys.version_info >= (3, 12):
            tar.extractall(path=dest, members=members, filter="data")
        else:
            dest_resolved = dest.resolve()
            for member in members:
                if member.issym() or member.islnk():
                    raise RuntimeError(f"Refusing link tar member: {member.name}")
                target = (dest / member.name).resolve()
                if dest_resolved != target and dest_resolved not in target.parents:
                    raise RuntimeError(f"Refusing unsafe tar member: {member.name}")
            tar.extractall(path=dest, members=members)  # nosec B202: checked above
    children = [p for p in dest.iterdir() if p.is_dir()]
    if len(children) != 1:
        raise RuntimeError(f"Unexpected tarball layout: {[c.name for c in children]}")
    return children[0]


def venv_python(target: Path, windowed: bool = False) -> Path:
    if sys.platform == "win32":
        return target / ".venv" / "Scripts" / ("pythonw.exe" if windowed else "python.exe")
    return target / ".venv" / "bin" / "python"


def run(cmd: list, **kw) -> None:
    # Audit: fixed argv lists built in this file (interpreter, pip, package
    # managers, sudo install of the repo's udev rule); no shell, no user text.
    proc = subprocess.run(cmd, **kw)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
    if proc.returncode != 0:
        fail("Command failed: " + " ".join(str(c) for c in cmd))


def install_python_packages(target: Path) -> None:
    py = venv_python(target)
    if not py.exists():
        say("Creating virtual environment in .venv")
        run([sys.executable, "-m", "venv", str(target / ".venv")])
    env = dict(os.environ)
    # Builds PyYAML without its C extension if a new Python has no wheel yet.
    env["PYYAML_FORCE_LIBYAML"] = "0"
    run([str(py), "-m", "pip", "install", "--upgrade", "pip"], env=env)
    run([str(py), "-m", "pip", "install", "-r", str(target / "requirements.txt")], env=env)
    # Editable install, so the `polyctl` console script is in .venv too.
    run([str(py), "-m", "pip", "install", "-e", str(target)], env=env)


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _quiet_ok(cmd: list) -> bool:
    # Audit: fixed package-query argv; no shell.
    return subprocess.run(cmd, stdout=subprocess.DEVNULL,  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
                          stderr=subprocess.DEVNULL).returncode == 0


def install_native_linux(target: Path) -> None:
    """The same steps as scripts/install.sh: hidapi and the udev rule."""
    if _have("dpkg") and _quiet_ok(["dpkg", "-s", "libhidapi-hidraw0"]) \
            or _have("rpm") and _quiet_ok(["rpm", "-q", "hidapi"]) \
            or _have("pacman") and _quiet_ok(["pacman", "-Q", "hidapi"]):
        say("Native hidapi already installed.")
    elif _have("apt-get"):
        say("Installing native hidapi (sudo may ask for your password)")
        run(["sudo", "apt-get", "update"])
        run(["sudo", "apt-get", "install", "-y", "libhidapi-hidraw0"])
    elif _have("dnf"):
        say("Installing native hidapi (sudo may ask for your password)")
        run(["sudo", "dnf", "install", "-y", "hidapi"])
    elif _have("pacman"):
        say("Installing native hidapi (sudo may ask for your password)")
        run(["sudo", "pacman", "-S", "--noconfirm", "hidapi"])
    else:
        say("No known package manager found. Install hidapi (libhidapi-hidraw0) yourself.")
    say("Installing the udev rule (keyboard HID interface and serial port, non-root)")
    run(["sudo", "install", "-m", "0644", str(target / "polyhost/device/99-hid.rules"),
         "/etc/udev/rules.d/99-hid.rules"])
    run(["sudo", "udevadm", "control", "--reload-rules"])
    run(["sudo", "udevadm", "trigger"])
    say("Replug the keyboard so the new udev rule takes effect.")


def install_native_macos() -> None:
    if not _have("brew"):
        say("Homebrew not found. The app needs the hidapi library to talk to the "
            "keyboard: install Homebrew (https://brew.sh), then run: brew install hidapi")
        return
    if _quiet_ok(["brew", "list", "hidapi"]):
        say("Native hidapi already installed.")
        return
    run(["brew", "install", "hidapi"])


def run_hint(target: Path) -> str:
    if sys.platform == "win32":
        # `&`: PowerShell reads a quoted path alone as a string, not a command.
        return f'& "{venv_python(target)}" -m polyhost'
    return f'cd "{target}" && .venv/bin/python -m polyhost'


def launch(target: Path) -> None:
    say("Starting PolyKybd...")
    env = dict(os.environ)
    scripts = venv_python(target).parent
    # The app needs the venv's script folder on PATH, as an activated venv
    # has it (see Start-PolyKybd in install.ps1).
    env["VIRTUAL_ENV"] = str(target / ".venv")
    env["PATH"] = str(scripts) + os.pathsep + env.get("PATH", "")
    for var in ("PYTHONHOME", "PYTHONPATH"):
        env.pop(var, None)
    if sys.platform == "win32":
        pyw = venv_python(target, windowed=True)
        if not pyw.exists():
            pyw = venv_python(target)
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        # No handles to the installer's console or pipes: the app outlives it.
        # Audit: fixed argv (the venv interpreter + "-m polyhost"); no shell.
        subprocess.Popen([str(pyw), "-m", "polyhost"], cwd=target, env=env,  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
        say("PolyKybd started. It also registers itself to start at login.")
        return
    log_path = target / "polyhost_launch.log"
    with open(log_path, "wb") as log_fh:
        # Audit: fixed argv (the venv interpreter + "-m polyhost"); no shell.
        proc = subprocess.Popen([str(venv_python(target)), "-m", "polyhost"],  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
                                cwd=target, env=env, stdin=subprocess.DEVNULL,
                                stdout=log_fh, stderr=subprocess.STDOUT,
                                start_new_session=True)
    time.sleep(3)
    if proc.poll() is None:
        say(f"PolyKybd started (PID {proc.pid}). It also registers itself to start at login.")
        if sys.platform == "darwin":
            say("Look for the PolyKybd icon in the menu bar (top right). It does not appear in the Dock.")
        return
    print(f"!! PolyKybd exited right after starting. Last lines of {log_path}:")
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-15:]
    for line in lines:
        print("   | " + line)
    say(f"Fix the problem above, then start it with:  {run_hint(target)}")


def ask_launch() -> bool:
    try:
        answer = input(">> Start PolyKybd now? [Y/n] ")
    except EOFError:  # no terminal: start right away, as install.sh does
        return True
    return not answer.strip().lower().startswith("n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", required=True, type=Path)
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--ref", default="", help="tag, branch or commit (default: latest release)")
    ap.add_argument("--no-launch", action="store_true")
    args = ap.parse_args(argv)

    target = args.target.resolve()
    if (target / ".git").exists():
        fail(f"'{target}' is a git checkout from the developer installer. "
             "Update it with `git pull`, or choose another folder.")
    target.mkdir(parents=True, exist_ok=True)

    ref = args.ref or latest_tag(args.repo)
    say(f"Installing {args.repo} {ref} into '{target}'.")
    with tempfile.TemporaryDirectory(prefix="polykybd-") as td:
        archive = Path(td) / "src.tar.gz"
        download(tarball_url(args.repo, ref), archive)
        extracted = Path(td) / "extracted"
        extracted.mkdir()
        top = extract(archive, extracted)
        try:
            shutil.copytree(top, target, dirs_exist_ok=True)
        except (OSError, shutil.Error) as exc:
            # On Windows a running app holds hidapi.dll open.
            fail(f"Could not copy the files into '{target}': {exc}\n"
                 "   If PolyKybd is running, quit it from the tray menu and run the installer again.")

    install_python_packages(target)
    if sys.platform.startswith("linux"):
        install_native_linux(target)
    elif sys.platform == "darwin":
        install_native_macos()

    print()
    say("Done.")
    if args.no_launch or os.environ.get("POLYKYBD_NO_LAUNCH"):
        say(f"Not starting. Start it later with:  {run_hint(target)}")
    elif ask_launch():
        launch(target)
    else:
        say(f"Not started. Start it later with:  {run_hint(target)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
