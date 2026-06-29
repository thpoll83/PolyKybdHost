#!/bin/bash
# macOS port of nx_deploy_scripts.sh.
# Deploys the PolyForwarder IP detection mechanism.
# Must be run ON THE REMOTE MACHINE (the one running the NoMachine server
# and PolyForwarder — NOT the machine with the keyboard).
#
# macOS has no systemd, so instead of a systemd user service + timer this
# installs a launchd LaunchAgent that runs the poll script every 30 s.
#
# What it does:
#   1. Installs nx_ip_poll_mac.sh to ~/.polyhost/
#   2. Installs a launchd LaunchAgent plist that polls port 4000 every 30 s
#   3. Loads (bootstraps) and starts the agent

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.polyhost"
POLL_SCRIPT="nx_ip_poll_mac.sh"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LABEL="org.polykybd.nx-ip-poll"
PLIST="$LAUNCH_AGENTS_DIR/$LABEL.plist"

echo "Deploying PolyForwarder IP poll agent..."

if [ ! -f "$SCRIPT_DIR/$POLL_SCRIPT" ]; then
    echo "Error: $POLL_SCRIPT not found in $SCRIPT_DIR" >&2
    exit 1
fi

# Install the poll script
mkdir -p "$TARGET_DIR"
cp "$SCRIPT_DIR/$POLL_SCRIPT" "$TARGET_DIR/$POLL_SCRIPT"
chmod +x "$TARGET_DIR/$POLL_SCRIPT"
echo "Installed: $TARGET_DIR/$POLL_SCRIPT"

# Install the launchd LaunchAgent
mkdir -p "$LAUNCH_AGENTS_DIR"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$TARGET_DIR/$POLL_SCRIPT</string>
    </array>
    <key>StartInterval</key>
    <integer>30</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$TARGET_DIR/nx-ip-poll.log</string>
    <key>StandardErrorPath</key>
    <string>$TARGET_DIR/nx-ip-poll.log</string>
</dict>
</plist>
EOF

echo "Installed: $PLIST"

# (Re)load the agent. Prefer the modern bootstrap/bootout API (launchd on
# 10.11+), falling back to the legacy load/unload for older systems.
DOMAIN="gui/$(id -u)"
if launchctl bootstrap "$DOMAIN" "$PLIST" 2>/dev/null; then
    echo "Bootstrapped $LABEL into $DOMAIN"
else
    # Already loaded, or older launchctl — bounce it the legacy way.
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    if ! launchctl bootstrap "$DOMAIN" "$PLIST" 2>/dev/null; then
        launchctl unload "$PLIST" 2>/dev/null || true
        launchctl load -w "$PLIST"
    fi
    echo "(Re)loaded $LABEL"
fi

# Kick it once now so the host_ip file is populated without waiting 30 s.
launchctl kickstart "$DOMAIN/$LABEL" 2>/dev/null || true

echo ""
echo "Agent status:"
launchctl print "$DOMAIN/$LABEL" 2>/dev/null | grep -E '^\s*(state|pid|last exit code)' || \
    launchctl list | grep "$LABEL" || true

echo ""
echo "PolyForwarder must be started with:"
echo "  python3 -m polyhost --host-file ~/.config/PolyHost/host_ip"
echo ""
echo "To remove later:"
echo "  launchctl bootout $DOMAIN/$LABEL"
echo "  rm \"$PLIST\""
