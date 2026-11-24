#!/bin/bash
# Deploys the PolyForwarder IP detection mechanism.
# Must be run ON THE REMOTE MACHINE (the one running the RDP server and
# PolyForwarder, not the machine with the keyboard). For an RDP server such as
# xrdp. The port is 3389; run with RDP_PORT=<port> to use another one.
#
# What it does:
#   1. Installs rdp_ip_poll.sh to ~/.polyhost/
#   2. Installs a systemd user service + timer that polls the RDP port every 30 s
#   3. Enables linger so the timer survives without an active login session
#   4. Enables and starts the timer

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.polyhost"
RDP_PORT="${RDP_PORT:-3389}"
POLL_SCRIPT="rdp_ip_poll.sh"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_NAME="rdp-ip-poll"

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
Description=Poll Remote Desktop (RDP) session IP for PolyHost

[Service]
Type=oneshot
Environment=RDP_PORT=$RDP_PORT
ExecStart=$TARGET_DIR/$POLL_SCRIPT
EOF

cat > "$SYSTEMD_USER_DIR/$SERVICE_NAME.timer" <<EOF
[Unit]
Description=Poll Remote Desktop (RDP) session IP every 30 seconds

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
