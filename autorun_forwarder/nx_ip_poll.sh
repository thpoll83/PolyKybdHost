#!/bin/bash
# Polls for an active NoMachine connection on port 4000.
# Writes the keyboard machine's IP to the PolyHost host_ip file when a
# session is active; removes it when no connection is found.
#
# Managed by the nx-ip-poll systemd user timer — see nx_deploy_scripts.sh.

HOST_IP_FILE="$HOME/.config/PolyHost/host_ip"

KEYBOARD_IP=$(ss -tn state established 'sport = :4000 or dport = :4000' \
    | awk 'NR==2 {print $4}' | sed 's/:[0-9]*$//')

if [ -n "$KEYBOARD_IP" ]; then
    mkdir -p "$(dirname "$HOST_IP_FILE")"
    echo "$KEYBOARD_IP" > "$HOST_IP_FILE"
else
    rm -f "$HOST_IP_FILE"
fi
