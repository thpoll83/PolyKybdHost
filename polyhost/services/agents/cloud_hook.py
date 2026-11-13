"""Agent keys for Claude Code cloud sessions (claude.ai/code): the hook and the
end-to-end encryption, standard library only.

A cloud session runs in a VM that cannot reach the keyboard computer. Its hooks
send the session's state through the relay Worker (`agent-relay/` in this
repository), and the host on the keyboard computer reads it from there. This one
file is three things:

- the hook command in the cloud VM (`python3 cloud_hook.py`, the hook JSON on
  stdin). The relay serves this file at `/v1/hook.py`, and the cloud environment's
  setup script installs it (`--install`);
- the encryption both ends share (`seal` / `open_sealed`);
- the configuration string both ends share (`parse_config` / `format_config`).

The relay sees only an opaque session key and ciphertext: never the session's
title, state, URL or ID. The key that encrypts is in the configuration string,
which the host creates and the user pastes into the cloud environment's
variables (POLYKYBD_CLOUD_RELAY).

The hook never writes to stdout and always exits 0: a hook that fails or prints
can block or steer the agent, and a keyboard light is not worth that.
"""
import base64
import contextlib
import hashlib
import hmac
import json
import os
import secrets
import sys
import tempfile
import time
import urllib.request

CONFIG_ENV = "POLYKYBD_CLOUD_RELAY"
CONFIG_PREFIX = "pkr1"
SEAL_VERSION = 1
NONCE_BYTES = 16
TAG_BYTES = 16
TITLE_MAX_CHARS = 60
POST_TIMEOUT_S = 3.0
# Cloudflare refuses Python's default User-Agent ("Python-urllib/3.x") on
# workers.dev with 403 "error code: 1010", so every request names itself.
USER_AGENT = "polykybd-cloud-hook/1"
INSTALL_PATH = "/usr/local/bin/polykybd-cloud-hook"

# The events the hook is registered for, and the state each one reports.
# None: no state of its own (the title or nothing changes).
EVENT_STATES = {
    "SessionStart": "idle",
    "UserPromptSubmit": "working",
    "PreToolUse": "working",
    "PostToolUse": "working",
    "PermissionRequest": "waiting",
    "Notification": None,          # decided by notification_type below
    "Stop": "done",
    "SessionEnd": "ended",
}

_TITLE_TYPES = ("custom-title", "ai-title", "summary")
_TITLE_FIELDS = ("customTitle", "aiTitle", "title", "summary")
_TRANSCRIPT_TAIL_BYTES = 256 * 1024


# ---- configuration -------------------------------------------------------------

def format_config(url: str, channel: str, write_token: str, key: bytes) -> str:
    """The string the user pastes into the cloud environment's variables."""
    return "|".join((CONFIG_PREFIX, url.rstrip("/"), channel, write_token,
                     base64.urlsafe_b64encode(key).decode().rstrip("=")))


def parse_config(text: str) -> dict:
    """{url, channel, write_token, key} from format_config's string. Raises
    ValueError on anything else."""
    parts = (text or "").strip().split("|")
    if len(parts) != 5 or parts[0] != CONFIG_PREFIX:
        raise ValueError("not a PolyKybd cloud relay configuration")
    _, url, channel, write_token, key = parts
    if not url.startswith("https://") and not url.startswith("http://127.0.0.1"):
        raise ValueError("the relay address must use https")
    if not _is_hex(channel, 32) or not _is_hex(write_token, 64):
        raise ValueError("malformed channel or token")
    raw = base64.urlsafe_b64decode(key + "=" * (-len(key) % 4))
    if len(raw) != 32:
        raise ValueError("malformed key")
    return {"url": url, "channel": channel, "write_token": write_token, "key": raw}


def new_channel() -> dict:
    """A new channel with its secrets, made by the host. The relay gets only the
    two token hashes (token_hash)."""
    return {"channel": secrets.token_hex(16), "read_token": secrets.token_hex(32),
            "write_token": secrets.token_hex(32), "key": secrets.token_bytes(32)}


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _is_hex(text, length) -> bool:
    return (isinstance(text, str) and len(text) == length
            and all(c in "0123456789abcdef" for c in text))


# ---- encryption ----------------------------------------------------------------
# Encrypt-then-MAC with HMAC-SHA256 as the pseudorandom function: the keystream
# is HMAC(k_enc, nonce || counter) block by block, the tag HMAC(k_mac, version ||
# nonce || ciphertext) cut to 16 bytes. Both subkeys come from the 32-byte key.
# Standard library only, because the cloud VM and the host have no crypto
# package in common.

def _subkeys(key: bytes):
    return (hmac.new(key, b"polykybd-cloud enc", hashlib.sha256).digest(),
            hmac.new(key, b"polykybd-cloud mac", hashlib.sha256).digest())


def _keystream(k_enc: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hmac.new(k_enc, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        counter += 1
    return bytes(out[:length])


def seal(key: bytes, plaintext: bytes, nonce: bytes | None = None) -> str:
    """base64url(version || nonce || ciphertext || tag)."""
    k_enc, k_mac = _subkeys(key)
    nonce = nonce or secrets.token_bytes(NONCE_BYTES)
    ct = bytes(a ^ b for a, b in zip(plaintext, _keystream(k_enc, nonce, len(plaintext))))
    head = bytes([SEAL_VERSION]) + nonce
    tag = hmac.new(k_mac, head + ct, hashlib.sha256).digest()[:TAG_BYTES]
    return base64.urlsafe_b64encode(head + ct + tag).decode().rstrip("=")


def open_sealed(key: bytes, token: str) -> bytes:
    """The plaintext of seal()'s output. Raises ValueError when it was not made
    with this key or was changed."""
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (ValueError, TypeError) as exc:
        raise ValueError("not base64") from exc
    if len(raw) < 1 + NONCE_BYTES + TAG_BYTES or raw[0] != SEAL_VERSION:
        raise ValueError("unknown format")
    head, ct, tag = raw[:1 + NONCE_BYTES], raw[1 + NONCE_BYTES:-TAG_BYTES], raw[-TAG_BYTES:]
    k_enc, k_mac = _subkeys(key)
    if not hmac.compare_digest(tag, hmac.new(k_mac, head + ct, hashlib.sha256).digest()[:TAG_BYTES]):
        raise ValueError("authentication failed")
    return bytes(a ^ b for a, b in zip(ct, _keystream(k_enc, head[1:], len(ct))))


def session_slot(key: bytes, session_id: str) -> str:
    """The opaque key the relay stores a session under: the relay never sees the
    session ID itself."""
    return hmac.new(key, b"slot " + session_id.encode(), hashlib.sha256).hexdigest()[:32]


# ---- the hook ------------------------------------------------------------------

def state_for(payload: dict):
    """The state word one hook event reports, or None."""
    event = payload.get("hook_event_name") or ""
    if event == "Notification":
        kind = str(payload.get("notification_type") or "")
        if kind in ("permission_prompt", "elicitation_dialog"):
            return "waiting"
        if kind == "idle_prompt":
            return "idle"
        return None
    return EVENT_STATES.get(event)


def transcript_title(path) -> str:
    """The newest session title in a Claude Code transcript, or ''. Only this one
    line leaves the VM, encrypted: never the prompt or the conversation."""
    if not path or not isinstance(path, str) or not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as fh:
            fh.seek(max(0, os.path.getsize(path) - _TRANSCRIPT_TAIL_BYTES))
            lines = fh.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        if '"type"' not in line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict) or record.get("type") not in _TITLE_TYPES:
            continue
        for name in _TITLE_FIELDS:
            value = record.get(name)
            if isinstance(value, str) and value.strip():
                return " ".join(value.split())[:TITLE_MAX_CHARS]
    return ""


def session_url(session_id: str) -> str:
    """claude.ai's page for a cloud session. The VM knows the session as cse_…,
    the page as session_… with the same suffix."""
    if session_id.startswith("cse_"):
        return "https://claude.ai/code/session_" + session_id[4:]
    return ""


def build_report(payload: dict, environ=os.environ):
    """(session_id, report dict) for one hook event, or None when it reports
    nothing."""
    state = state_for(payload)
    if state is None:
        return None
    session_id = environ.get("CLAUDE_CODE_REMOTE_SESSION_ID") or str(payload.get("session_id") or "")
    if not session_id:
        return None
    report = {"state": state, "title": transcript_title(payload.get("transcript_path")),
              "url": session_url(session_id), "cwd": os.path.basename(str(payload.get("cwd") or ""))}
    return session_id, report


def _last_sent_path(slot: str) -> str:
    return os.path.join(tempfile.gettempdir(), f"polykybd-cloud-{slot}.json")


def last_sent(slot: str):
    """The report last sent for this session, or None."""
    try:
        with open(_last_sent_path(slot), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        # No file yet, or a broken one: treat as nothing sent, so the report goes out.
        return None


def remember_sent(slot: str, report: dict) -> None:
    try:
        with open(_last_sent_path(slot), "w", encoding="utf-8") as fh:
            json.dump(report, fh)
    except OSError:
        # Unwritable temp folder: the next event sends again, which costs one
        # request and changes nothing on the keys.
        return


@contextlib.contextmanager
def _session_lock(slot: str):
    """One hook process per session at a time: parallel tool calls run their
    PostToolUse hooks together, and both would send the same change."""
    try:
        import fcntl
    except ImportError:          # not POSIX: the cloud VM always is
        yield
        return
    fd = os.open(_last_sent_path(slot) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def post(config: dict, slot: str, blob: str, ended: bool) -> int:
    body = json.dumps({"k": slot, "blob": blob, "ended": ended}).encode()
    req = urllib.request.Request(
        f"{config['url']}/v1/c/{config['channel']}/event", data=body, method="POST",
        headers={"Authorization": f"Bearer {config['write_token']}",
                 "Content-Type": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=POST_TIMEOUT_S) as resp:
        return resp.status


def run_hook(stdin_text: str, environ=os.environ, poster=post) -> bool:
    """One hook event. True when a report was sent."""
    config = parse_config(environ.get(CONFIG_ENV, ""))
    payload = json.loads(stdin_text or "{}")
    if not isinstance(payload, dict):
        return False
    built = build_report(payload, environ)
    if built is None:
        return False
    session_id, report = built
    slot = session_slot(config["key"], session_id)
    with _session_lock(slot):
        previous = last_sent(slot)
        if not report["title"] and previous:
            # The title record can fall out of the transcript tail this hook reads;
            # that is not a rename, so keep the title already shown.
            report["title"] = previous.get("title") or ""
        if previous == report:
            # Only a change goes out: every tool call reports "working" again, and
            # each POST costs relay requests for every PolyKybd user.
            return False
        report_with_time = dict(report, ts=int(time.time()))
        blob = seal(config["key"], json.dumps(report_with_time).encode())
        poster(config, slot, blob, report["state"] == "ended")
        remember_sent(slot, report)
    return True


# ---- installing the hook in the cloud VM ---------------------------------------

def hook_settings(command: str) -> dict:
    """The "hooks" block for ~/.claude/settings.json."""
    return {event: [{"matcher": "", "hooks": [{"type": "command", "command": command,
                                                "timeout": 10}]}]
            for event in EVENT_STATES}


def install(settings_path: str, command: str) -> bool:
    """Add the PolyKybd hooks to a Claude Code settings file, keeping everything
    else in it. True when the file changed."""
    try:
        with open(settings_path, encoding="utf-8") as fh:
            settings = json.load(fh)
    except FileNotFoundError:
        settings = {}
    if not isinstance(settings, dict):
        raise ValueError(f"{settings_path} is not a JSON object")
    hooks = settings.setdefault("hooks", {})
    changed = False
    for event, groups in hook_settings(command).items():
        existing = hooks.setdefault(event, [])
        if any(h.get("command") == command
               for g in existing if isinstance(g, dict) for h in g.get("hooks") or []):
            continue
        existing.extend(groups)
        changed = True
    if changed:
        os.makedirs(os.path.dirname(settings_path) or ".", exist_ok=True)
        tmp = settings_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=2)
        os.replace(tmp, settings_path)
    return changed


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--install"]:
        # Run by the cloud environment's setup script, as root, before Claude starts.
        settings = os.path.expanduser("~/.claude/settings.json")
        changed = install(settings, f"python3 {INSTALL_PATH}")
        print(("PolyKybd hooks added to " if changed else "PolyKybd hooks already in ")
              + settings)
        return 0
    try:
        run_hook(sys.stdin.read())
    except Exception:  # noqa: BLE001 - see the module docstring: never fail the agent
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
