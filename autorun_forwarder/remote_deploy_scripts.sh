#!/bin/bash
# Deploys the PolyForwarder IP detection mechanism.
# Must be run ON THE REMOTE MACHINE (the one running the NoMachine or RDP server and
# PolyForwarder, not the machine with the keyboard). It detects NoMachine (4000)
# and RDP (3389, xrdp) by itself. Run with REMOTE_PORTS="<port> <port>" to use
# other ports.
#
# What it does:
#   1. Installs remote_ip_poll.sh to ~/.polyhost/
#   2. Installs a systemd user service + timer that polls the NoMachine and RDP ports every 30 s
#   3. Enables linger so the timer survives without an active login session
#   4. Enables and starts the timer

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.polyhost"
REMOTE_PORTS="${REMOTE_PORTS:-4000 3389}"
POLL_SCRIPT="remote_ip_poll.sh"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_NAME="remote-ip-poll"

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
Description=Poll NoMachine or RDP session IP for PolyHost

[Service]
Type=oneshot
Environment="REMOTE_PORTS=$REMOTE_PORTS"
ExecStart="$TARGET_DIR/$POLL_SCRIPT"
EOF

cat > "$SYSTEMD_USER_DIR/$SERVICE_NAME.timer" <<EOF
[Unit]
Description=Poll NoMachine or RDP session IP every 30 seconds

[Timer]
OnBootSec=10
OnUnitActiveSec=30
AccuracySec=1s

[Install]
WantedBy=timers.target
EOF

echo "Installed: $SYSTEMD_USER_DIR/$SERVICE_NAME.service"
echo "Installed: $SYSTEMD_USER_DIR/$SERVICE_NAME.timer"

# Enable linger so the user's systemd instance (and thus the timer)
# keeps running even when no interactive session is active.
loginctl enable-linger "$(whoami)"
echo "Linger enabled for $(whoami)"

# The NoMachine-only timer from nx_deploy_scripts.sh writes and deletes the same
# host_ip file. Left running, it would delete the address this timer writes for an
# RDP client, every 30 seconds, because it sees no connection on port 4000.
if systemctl --user cat nx-ip-poll.timer >/dev/null 2>&1; then
    systemctl --user disable --now nx-ip-poll.timer || true
    systemctl --user stop nx-ip-poll.service || true
    echo "Disabled the old nx-ip-poll timer (replaced by $SERVICE_NAME)."
fi

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
