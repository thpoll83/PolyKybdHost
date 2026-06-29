#!/bin/bash
# macOS port of nx_ip_poll.sh.
# Polls for an active NoMachine connection on port 4000.
# Writes the keyboard machine's IP to the PolyHost host_ip file when a
# session is active; removes it when no connection is found.
#
# Managed by the nx-ip-poll launchd user agent — see nx_deploy_scripts_mac.sh.
#
# macOS has no `ss`, so this uses `lsof`. For an established TCP connection
# lsof prints the NAME field as "local:port->peer:port"; the peer is the
# machine that connected to this NoMachine server (i.e. the keyboard machine).

HOST_IP_FILE="$HOME/.config/PolyHost/host_ip"

# Grab the foreign (peer) endpoint of an established connection on port 4000,
# then strip the trailing ":port". Mirrors the Linux script's behaviour.
KEYBOARD_IP=$(lsof -nP -iTCP:4000 -sTCP:ESTABLISHED 2>/dev/null \
    | awk 'NR>1 {print $9}' | head -1 \
    | sed -E 's/.*->//; s/:[0-9]+$//')

if [ -n "$KEYBOARD_IP" ]; then
    mkdir -p "$(dirname "$HOST_IP_FILE")"
    echo "$KEYBOARD_IP" > "$HOST_IP_FILE"
else
    rm -f "$HOST_IP_FILE"
fi
