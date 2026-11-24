#!/bin/bash
# Polls for an active remote-desktop connection to this machine and writes the
# keyboard machine's IP to the PolyHost host_ip file while one is connected.
# It removes the file when none is. One script for both protocols: it looks at
# the NoMachine port (4000) and the RDP port (3389, xrdp), so it needs no
# setting for which one the user connected with. Replaces nx_ip_poll.sh when you
# use both; nx_ip_poll.sh still works for NoMachine alone.
#
# Run on the REMOTE machine (the one with the remote-desktop server and the
# PolyForwarder, not the one with the keyboard). Managed by the
# remote-ip-poll systemd user timer, see remote_deploy_scripts.sh.
#
# REMOTE_PORTS (default "4000 3389") and HOST_IP_FILE can be set in the
# environment. With clients on both ports, the first port in the list wins.

REMOTE_PORTS="${REMOTE_PORTS:-4000 3389}"
HOST_IP_FILE="${HOST_IP_FILE:-$HOME/.config/PolyHost/host_ip}"

# Established connections whose LOCAL port is one of the listed ports: column 4
# is the peer "address:port". A dual-stack listener shows an IPv4 client as
# [::ffff:a.b.c.d]:port. Take the first IPv4 peer that is not this machine: the
# forwarder's report endpoint and legacy relay are AF_INET sockets, so an IPv6
# address could not be dialled.
KEYBOARD_IP=""
for port in $REMOTE_PORTS; do
    # Check ss itself. A missing or failing ss would otherwise read as "no client"
    # and delete a valid host_ip; leave the file as it is and fail instead.
    if ! SS_OUT=$(ss -tn state established "( sport = :${port} )" 2>/dev/null); then
        echo "remote_ip_poll: ss failed; host_ip left unchanged" >&2
        exit 1
    fi
    KEYBOARD_IP=$(printf '%s\n' "$SS_OUT" \
        | awk 'NR>1 {print $4}' \
        | sed -e 's/:[0-9]*$//' -e 's/^\[//' -e 's/\]$//' -e 's/^::ffff://' \
        | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' \
        | grep -v '^127\.' \
        | head -n 1)
    [ -n "$KEYBOARD_IP" ] && break
done

if [ -n "$KEYBOARD_IP" ]; then
    mkdir -p "$(dirname "$HOST_IP_FILE")"
    # Write only on a change: the forwarder reads the file on every reconnect.
    if [ "$(cat "$HOST_IP_FILE" 2>/dev/null)" != "$KEYBOARD_IP" ]; then
        echo "$KEYBOARD_IP" > "$HOST_IP_FILE"
    fi
else
    rm -f "$HOST_IP_FILE"
fi
