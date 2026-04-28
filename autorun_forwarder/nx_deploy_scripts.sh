#!/bin/bash
# Deploys the PolyForwarder IP detection mechanism.
# Must be run ON THE REMOTE MACHINE (the one running the NoMachine server
# and PolyForwarder — NOT the machine with the keyboard).
#
# Replaces the previous NX session hook approach (which crashed NX sessions
# due to nxuser lacking permission to write to the real user's home directory).
#
# What it does:
#   1. Installs nx_ip_poll.sh to ~/.polyhost/
#   2. Installs a systemd user service + timer that polls port 4000 every 30 s
#   3. Enables linger so the timer survives without an active login session
#   4. Enables and starts the timer

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.polyhost"
POLL_SCRIPT="nx_ip_poll.sh"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_NAME="nx-ip-poll"

echo "Deploying PolyForwarder IP poll timer..."

if [ ! -f "$SCRIPT_DIR/$POLL_SCRIPT" ]; then
    echo "Error: $POLL_SCRIPT not found in $SCRIPT_DIR" >&2
    exit 1
fi

# Install the poll script
mkdir -p "$TARGET_DIR"
cp "$SCRIPT_DIR/$POLL_SCRIPT" "$TARGET_DIR/$POLL_SCRIPT"
chmod +x "$TARGET_DIR/$POLL_SCRIPT"
echo "Installed: $TARGET_DIR/$POLL_SCRIPT"

# Install systemd user units
mkdir -p "$SYSTEMD_USER_DIR"

cat > "$SYSTEMD_USER_DIR/$SERVICE_NAME.service" <<EOF
[Unit]
Description=Poll NoMachine session IP for PolyHost

[Service]
Type=oneshot
ExecStart=$TARGET_DIR/$POLL_SCRIPT
EOF

cat > "$SYSTEMD_USER_DIR/$SERVICE_NAME.timer" <<EOF
[Unit]
Description=Poll NoMachine session IP every 30 seconds

[Timer]
OnBootSec=10
OnUnitActiveSec=30

[Install]
WantedBy=timers.target
EOF

echo "Installed: $SYSTEMD_USER_DIR/$SERVICE_NAME.service"
echo "Installed: $SYSTEMD_USER_DIR/$SERVICE_NAME.timer"

# Enable linger so the user's systemd instance (and thus the timer)
# keeps running even when no interactive session is active.
loginctl enable-linger "$(whoami)"
echo "Linger enabled for $(whoami)"

# Reload and start the timer
systemctl --user daemon-reload
systemctl --user enable --now "$SERVICE_NAME.timer"

echo ""
echo "Timer status:"
systemctl --user status "$SERVICE_NAME.timer" --no-pager || true

echo ""
echo "PolyForwarder must be started with:"
echo "  python3 -m polyhost --host-file ~/.config/PolyHost/host_ip"
echo ""
echo "Note: NoMachine node.cfg hooks (UserScriptAfterSessionStart /"
echo "      UserScripBeforeSessionDisconnect) are no longer needed."
echo "      Remove them from /usr/NX/etc/node.cfg if previously added."
