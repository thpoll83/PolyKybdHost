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
# PolyKybdHost needs Python 3.10+ (match statements, PEP 604 unions). Prefer an
# explicitly-versioned interpreter so we don't silently build the venv on the
# macOS system python3 (3.9, from the Xcode Command Line Tools), which can't run
# the app. Fall back to bare python3/python only if it is new enough.
find_python() {  # echoes the first 3.10+ interpreter on PATH, or nothing
    for cand in python3.13 python3.12 python3.11 python3.10 python3 python; do
        command -v "$cand" >/dev/null 2>&1 || continue
        if "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            echo "$cand"
            return 0
        fi
    done
    return 1
}

PY="$(find_python || true)"

if [ -z "$PY" ] && [ "$(uname -s)" = "Darwin" ] && [ -r /dev/tty ]; then
    # Interactive macOS fallback: offer to install Python 3.10+ for the user.
    # Variant A (Homebrew) can be fully automated; variant B (python.org) is a
    # GUI .pkg, so we point at it rather than driving it.
    echo "!! PolyKybdHost requires Python 3.10 or newer, but none was found on PATH." > /dev/tty
    echo "   The macOS system python3 (Xcode Command Line Tools) is 3.9 and will not work." > /dev/tty
    echo > /dev/tty
    echo "   Install options:" > /dev/tty
    echo "     [A] Homebrew  - I can install it now (brew install python)" > /dev/tty
    echo "     [B] python.org - download the .pkg yourself from https://www.python.org/downloads/macos/" > /dev/tty
    echo "     [S] Skip       - abort and install Python manually" > /dev/tty
    printf "   Choose [A/b/s]: " > /dev/tty
    read -r choice < /dev/tty || choice=""
    case "$(printf '%s' "$choice" | tr '[:upper:]' '[:lower:]')" in
        b)
            echo ">> Opening the python.org downloads page; re-run this installer after installing." > /dev/tty
            command -v open >/dev/null 2>&1 && open "https://www.python.org/downloads/macos/" || true
            exit 1
            ;;
        s)
            echo ">> Skipping. Install Python 3.10+ and re-run this installer." > /dev/tty
            exit 1
            ;;
        *)  # default: Homebrew
            if ! command -v brew >/dev/null 2>&1; then
                echo ">> Installing Homebrew (it may ask for your password)..." > /dev/tty
                if ! /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" < /dev/tty; then
                    echo "!! Homebrew installation failed. Install it manually from https://brew.sh then re-run this installer." >&2
                    exit 1
                fi
                # Put brew on PATH for the rest of this script (Apple Silicon vs Intel).
                for brewbin in /opt/homebrew/bin/brew /usr/local/bin/brew; do
                    [ -x "$brewbin" ] && eval "$("$brewbin" shellenv)" && break
                done
                if ! command -v brew >/dev/null 2>&1; then
                    echo "!! Homebrew installed but 'brew' is not on PATH. Open a new terminal and re-run this installer." >&2
                    exit 1
                fi
            fi
            echo ">> Installing Python via Homebrew..." > /dev/tty
            if ! brew install python; then
                echo "!! 'brew install python' failed (see the brew output above). Resolve it, then re-run this installer." >&2
                exit 1
            fi
            PY="$(find_python || true)"
            if [ -z "$PY" ]; then
                echo "!! Python was installed via Homebrew but no 3.10+ interpreter is on PATH." >&2
                echo "   Open a new terminal (so brew's bin dir is picked up) and re-run this installer." >&2
                exit 1
            fi
            ;;
    esac
fi

if [ -z "$PY" ]; then
    echo "!! PolyKybdHost requires Python 3.10 or newer, but none was found on PATH."
    case "$(uname -s)" in
        Darwin)
            echo "   The macOS system python3 (Xcode Command Line Tools) is 3.9 and will not work."
            echo "   Install a newer Python, then re-run this installer:"
            echo
            echo "     # Option A - Homebrew (recommended):"
            command -v brew >/dev/null 2>&1 || \
                echo "     /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            echo "     brew install python"
            echo
            echo "     # Option B - official installer: https://www.python.org/downloads/macos/"
            ;;
        Linux)
            echo "   Install Python 3.10+ with your distro's package manager, then re-run this installer:"
            echo
            echo "     sudo apt install python3 python3-venv     # Debian/Ubuntu"
            echo "     sudo dnf install python3                   # Fedora/RHEL"
            echo "     sudo pacman -S python                      # Arch"
            echo
            echo "   If your distro is too old to ship 3.10+, see https://www.python.org/downloads/"
            ;;
        *)
            echo "   Install Python 3.10 or newer from https://www.python.org/downloads/ and re-run this installer."
            ;;
    esac
    exit 1
fi
echo ">> Using $PY ($("$PY" --version 2>&1))"

echo ">> Creating virtual environment in .venv"
"$PY" -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
# Editable install too, so the `polyctl` console script lands in .venv/bin
# (deps are already satisfied above; this just adds the package link + script).
python -m pip install -e .

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
            # Plain -S (not -Sy): refreshing only the hidapi entry risks partial
            # upgrades on rolling distros. Assume the system is kept up to date.
            sudo pacman -S --noconfirm hidapi
        else
            echo "!! Could not detect a package manager - install hidapi (libhidapi-hidraw0) yourself."
        fi
        echo ">> Installing udev rule for non-root HID access"
        sudo cp polyhost/device/99-hid.rules /etc/udev/rules.d/99-hid.rules
        sudo udevadm control --reload-rules && sudo udevadm trigger
        echo ">> Replug the keyboard so the new udev rule takes effect."
        ;;
esac

launch_app() {
    echo ">> Starting PolyKybd..."
    nohup .venv/bin/python -m polyhost >/dev/null 2>&1 &
    echo ">> PolyKybd started (PID $!); it also registers itself to autostart at login."
}

echo ""
echo ">> Done."
RUN_HINT="cd \"$(pwd)\" && .venv/bin/python -m polyhost"
if [ -n "${POLYKYBD_NO_LAUNCH:-}" ]; then
    # Opt out of auto-launch (e.g. CI / headless). Don't start the app.
    echo ">> POLYKYBD_NO_LAUNCH set - not starting. Launch it later with:  $RUN_HINT"
elif [ -r /dev/tty ]; then
    printf ">> Start PolyKybd now? [Y/n] " > /dev/tty
    read -r ans < /dev/tty || ans=""
    case "$ans" in
        [Nn]*) echo ">> Not started. Launch it later with:  $RUN_HINT" ;;
        *)     launch_app ;;
    esac
else
    # No terminal to ask on (not started interactively) - start right away.
    launch_app
fi
