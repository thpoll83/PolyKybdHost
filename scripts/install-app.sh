#!/usr/bin/env bash
#
# PolyKybdHost installer for Linux and macOS that needs neither git nor Python.
#
#   curl -fsSL https://raw.githubusercontent.com/thpoll83/PolyKybdHost/main/scripts/install-app.sh | bash
#
# Downloads uv (one checksum-verified binary, deleted afterwards), lets uv
# download Python 3.13 into <install dir>/.python, then runs
# scripts/install_app.py with it. That script downloads the latest release,
# creates .venv, installs the requirements, installs hidapi (and the udev rule
# on Linux, with sudo) and starts the app. Nothing is added to PATH: deleting
# the install folder removes the app (the udev rule and hidapi stay).
#
# The developer install (git clone of main, your own Python) is
# scripts/install.sh.
#
#   POLYKYBD_DIR        install folder (default ~/PolyKybdHost)
#   POLYKYBD_NO_LAUNCH  1 skips starting the app at the end
#   POLYKYBD_REPO       owner/name to install from (default thpoll83/PolyKybdHost)
#   POLYKYBD_REF        branch, tag or commit instead of the latest release;
#                       install_app.py is then taken from that ref too.
#                       .github/workflows/app-installer.yml uses these two.
set -euo pipefail

UV_VERSION="0.13.5"
PYTHON_VERSION="3.13"

REPO="${POLYKYBD_REPO:-thpoll83/PolyKybdHost}"
SCRIPT_REF="${POLYKYBD_REF:-main}"
TARGET_DIR="${POLYKYBD_DIR:-$HOME/PolyKybdHost}"

echo ">> PolyKybdHost installer"

# From https://astral.sh/uv/0.13.5/install.sh. Change them with UV_VERSION.
case "$(uname -s)-$(uname -m)" in
    Linux-x86_64)
        UV_ASSET="uv-x86_64-unknown-linux-gnu.tar.gz"
        UV_SHA256="f68d291c75783122dad58ab77def0e13f3233f358731db5d6d7e8715603b928f" ;;
    Linux-aarch64|Linux-arm64)
        UV_ASSET="uv-aarch64-unknown-linux-gnu.tar.gz"
        UV_SHA256="4bb69cf95ed13f23713bb7bc09f241896ea0c75b7c557e615a20604b82f9c403" ;;
    Darwin-x86_64)
        UV_ASSET="uv-x86_64-apple-darwin.tar.gz"
        UV_SHA256="b0f52b0e3945b4107d89024ea38e625683011fbfc05a0d98f9fa2d6dcee28c66" ;;
    Darwin-arm64)
        UV_ASSET="uv-aarch64-apple-darwin.tar.gz"
        UV_SHA256="743f85035a1996ecb350659e01cd9faea9709829be09b1b4b03c73eaf3c9cd73" ;;
    *)
        echo "!! No installer for $(uname -s) $(uname -m). PyQt5 has no wheels for it either."
        echo "   Try the developer install: scripts/install.sh"
        exit 1 ;;
esac

if [ -z "${POLYKYBD_DIR:-}" ] && (exec < /dev/tty) 2>/dev/null; then
    printf ">> Install location [%s]: " "$TARGET_DIR" > /dev/tty
    read -r reply < /dev/tty || reply=""
    [ -n "$reply" ] && TARGET_DIR="$reply"
fi
if [ -d "$TARGET_DIR/.git" ]; then
    echo "!! '$TARGET_DIR' is a git checkout from the developer installer."
    echo "   Update it with git pull, or choose another folder."
    exit 1
fi
mkdir -p "$TARGET_DIR"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/polykybd.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

fetch() {  # fetch URL FILE
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "$2" "$1"
    else
        wget -q -O "$2" "$1"
    fi
}

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d' ' -f1
    else
        shasum -a 256 "$1" | cut -d' ' -f1
    fi
}

# --- uv ----------------------------------------------------------------------
echo ">> Downloading uv $UV_VERSION"
fetch "https://releases.astral.sh/github/uv/releases/download/$UV_VERSION/$UV_ASSET" "$TMP/$UV_ASSET"
got="$(sha256_of "$TMP/$UV_ASSET")"
if [ "$got" != "$UV_SHA256" ]; then
    echo "!! uv download has the wrong SHA-256 ($got)."
    exit 1
fi
tar -xzf "$TMP/$UV_ASSET" -C "$TMP"
UV="$TMP/${UV_ASSET%.tar.gz}/uv"

# --- Python ------------------------------------------------------------------
# Only uv's own Python, kept inside the install folder. No python3.13 in
# ~/.local/bin.
export UV_PYTHON_INSTALL_DIR="$TARGET_DIR/.python"
export UV_CACHE_DIR="$TMP/cache"
export UV_PYTHON_PREFERENCE="only-managed"
export UV_PYTHON_INSTALL_BIN="0"
echo ">> Downloading Python $PYTHON_VERSION"
"$UV" python install "$PYTHON_VERSION"
PY="$("$UV" python find "$PYTHON_VERSION")"

# --- install -----------------------------------------------------------------
fetch "https://raw.githubusercontent.com/$REPO/$SCRIPT_REF/scripts/install_app.py" "$TMP/install_app.py"
set -- "$TMP/install_app.py" --target "$TARGET_DIR" --repo "$REPO"
[ -n "${POLYKYBD_REF:-}" ] && set -- "$@" --ref "$POLYKYBD_REF"
# stdin of this script is the curl pipe, so the questions go to the terminal.
# install_app.py reads POLYKYBD_NO_LAUNCH itself.
# `[ -r /dev/tty ]` is true in CI too, where opening it fails, so try to open it.
if (exec < /dev/tty) 2>/dev/null; then
    "$PY" "$@" < /dev/tty
else
    "$PY" "$@" < /dev/null
fi
