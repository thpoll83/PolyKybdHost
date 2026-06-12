#!/usr/bin/env bash
#
# PolyKybdHost one-line installer for Linux and macOS.
#
#   curl -fsSL https://raw.githubusercontent.com/thpoll83/PolyKybdHost/main/scripts/install.sh | bash
#
# Clones the repo (if not already inside it), creates a virtual environment,
# installs the Python requirements, and sets up the native hidapi library plus
# (on Linux) the udev rule needed for non-root HID access.
#
# Override the clone location with POLYKYBD_DIR=/path/to/dir.
set -euo pipefail

REPO_URL="https://github.com/thpoll83/PolyKybdHost.git"
TARGET_DIR="${POLYKYBD_DIR:-$(pwd)/PolyKybdHost}"

echo ">> PolyKybdHost installer"

# --- get the source tree -----------------------------------------------------
if [ -f "polyhost/__main__.py" ]; then
    echo ">> Already inside a PolyKybdHost checkout, installing here."
    TARGET_DIR="."
else
    # Offer the default location and let the user pick another, unless the
    # path was pinned via POLYKYBD_DIR or there is no terminal to ask on
    # (e.g. piped in CI).
    if [ -z "${POLYKYBD_DIR:-}" ] && [ -r /dev/tty ]; then
        printf ">> Install location [%s]: " "$TARGET_DIR" > /dev/tty
        read -r reply < /dev/tty || reply=""
        [ -n "$reply" ] && TARGET_DIR="$reply"
    fi
    echo ">> Installing into '$TARGET_DIR'."
fi

if [ "$TARGET_DIR" = "." ]; then
    :  # already inside the checkout, nothing to fetch
elif [ -d "$TARGET_DIR/.git" ]; then
    echo ">> Updating existing checkout in '$TARGET_DIR'."
    git -C "$TARGET_DIR" pull --ff-only
else
    echo ">> Cloning into '$TARGET_DIR'."
    git clone "$REPO_URL" "$TARGET_DIR"
fi
cd "$TARGET_DIR"

# --- python virtual environment ---------------------------------------------
PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
command -v "$PY" >/dev/null 2>&1 || { echo "!! Python 3 not found on PATH."; exit 1; }

echo ">> Creating virtual environment in .venv"
"$PY" -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# --- native hidapi + permissions --------------------------------------------
case "$(uname -s)" in
    Darwin)
        if command -v brew >/dev/null 2>&1; then
            brew list hidapi >/dev/null 2>&1 || brew install hidapi
        else
            echo "!! Homebrew not found - install hidapi manually: brew install hidapi"
        fi
        ;;
    Linux)
        echo ">> Installing native hidapi (sudo may prompt for your password)"
        if command -v apt-get >/dev/null 2>&1; then
            sudo apt-get update && sudo apt-get install -y libhidapi-hidraw0
        elif command -v dnf >/dev/null 2>&1; then
            sudo dnf install -y hidapi
        elif command -v pacman >/dev/null 2>&1; then
            sudo pacman -Sy --noconfirm hidapi
        else
            echo "!! Could not detect a package manager - install hidapi (libhidapi-hidraw0) yourself."
        fi
        echo ">> Installing udev rule for non-root HID access"
        sudo cp polyhost/device/99-hid.rules /etc/udev/rules.d/99-hid.rules
        sudo udevadm control --reload-rules && sudo udevadm trigger
        echo ">> Replug the keyboard so the new udev rule takes effect."
        ;;
esac

echo ""
echo ">> Done. Start PolyKybdHost with:"
echo "       cd $(pwd) && .venv/bin/python -m polyhost"
