"""Pairing a forwarder with the keyboard computer: the window-report key as a code.

The network window-report endpoint (server/window_report_server.py) accepts only a
client that holds its key, `polykybd-winreport.authkey` on the keyboard computer.
A forwarder in RPC mode (the mode the agent keys need) must hold the same key.
Instead of copying the file, the keyboard computer shows the key as a code and the
forwarder saves it to its own config folder (`paired_key_path()`); a forwarder with
a saved pairing uses RPC mode and that key without command-line flags.

⚠️ The code IS the secret: whoever has it can send window and agent reports to the
keyboard computer (security audit, HOST-6). The dialogs say so.
"""
from __future__ import annotations

import os
import re

PAIRED_KEY_FILE = "polykybd-forwarder-pairing.authkey"
_KEY_HEX = 64          # protocol.load_or_create_authkey: secrets.token_hex(32)


def pairing_code() -> str:
    """The keyboard computer's window-report key, in 8 groups of 8 characters.
    Creates the key on first use, as the endpoint itself would."""
    from polyhost.server import protocol
    key = protocol.load_or_create_authkey(protocol.window_report_authkey_path())
    text = key.decode("ascii").strip().lower()
    return "-".join(text[i:i + 8] for i in range(0, len(text), 8))


def parse_code(code: str) -> bytes | None:
    """The key in a pasted code, or None when it is not one. Spaces, dashes and
    letter case do not matter."""
    text = re.sub(r"[\s\-]", "", code or "").lower()
    if len(text) != _KEY_HEX or not re.fullmatch(r"[0-9a-f]+", text):
        return None
    return text.encode("ascii")


def paired_key_path() -> str:
    from polyhost.server import protocol
    return os.path.join(protocol._config_dir(), PAIRED_KEY_FILE)


def save_paired_key(key: bytes, path: str | None = None) -> str:
    """Write the key (0600 where the OS honours it), replacing an earlier pairing."""
    path = path or paired_key_path()
    tmp = f"{path}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(key)
    os.replace(tmp, path)
    return path


def paired_key_file(path: str | None = None) -> str | None:
    """The saved pairing's path when it holds a valid key, else None."""
    path = path or paired_key_path()
    try:
        with open(path, "rb") as fh:
            ok = parse_code(fh.read().decode("ascii", "replace")) is not None
    except OSError:
        return None
    return path if ok else None


def forget_pairing(path: str | None = None) -> bool:
    try:
        os.remove(path or paired_key_path())
        return True
    except OSError:
        return False
