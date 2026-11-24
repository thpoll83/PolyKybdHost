#!/bin/bash
# Polls for an active Remote Desktop (RDP) connection to this machine, for a
# Linux RDP server such as xrdp (port 3389). Writes the keyboard machine's IP to
# the PolyHost host_ip file when a client is connected, and removes it when none
# is. The RDP counterpart of nx_ip_poll.sh.
#
# Run on the REMOTE machine (the one with the RDP server and the PolyForwarder,
# not the one with the keyboard). Managed by the rdp-ip-poll systemd user timer,
# see rdp_deploy_scripts.sh.
#
# RDP_PORT (default 3389) and HOST_IP_FILE can be set in the environment.

RDP_PORT="${RDP_PORT:-3389}"
HOST_IP_FILE="${HOST_IP_FILE:-$HOME/.config/PolyHost/host_ip}"

# Established connections whose LOCAL port is the RDP port: column 4 is the peer
# "address:port". Take the first peer that is not this machine. A dual-stack
# listener shows an IPv4 client as [::ffff:a.b.c.d]:port.
KEYBOARD_IP=$(ss -tn state established "( sport = :${RDP_PORT} )" \
    | awk 'NR>1 {print $4}' \
    | sed -e 's/:[0-9]*$//' -e 's/^\[//' -e 's/\]$//' -e 's/^::ffff://' -e 's/%.*$//' \
    | grep -v -e '^127\.' -e '^::1$' -e '^$' \
    | head -n 1)

if [ -n "$KEYBOARD_IP" ]; then
    mkdir -p "$(dirname "$HOST_IP_FILE")"
    # Write only on a change: the forwarder reads the file on every reconnect.
    if [ "$(cat "$HOST_IP_FILE" 2>/dev/null)" != "$KEYBOARD_IP" ]; then
        echo "$KEYBOARD_IP" > "$HOST_IP_FILE"
    fi
else
    rm -f "$HOST_IP_FILE"
fi
