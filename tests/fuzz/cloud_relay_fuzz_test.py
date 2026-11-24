"""Properties of the cloud-session relay client (services/agents/cloud_relay.py and
the sealing in cloud_hook.py): WebSocket frames from the relay, sealed reports, the
join code a user pastes, and the channel file."""
import base64
import json
import math
import os
import socket
import tempfile
import unittest

from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.services.agents import cloud_hook, cloud_relay as cr

load_profile()

HEX = "0123456789abcdef"
KEY = st.binary(min_size=32, max_size=32)
JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats() | st.text(max_size=12),
    lambda inner: st.lists(inner, max_size=4)
    | st.dictionaries(st.text(max_size=8), inner, max_size=5),
    max_leaves=16)
CHANNEL = st.fixed_dictionaries({
    "url": st.text(st.characters(blacklist_characters="|", blacklist_categories=("Cs",)),
                   max_size=30).map(lambda t: "https://" + t),
    "channel": st.text(HEX, min_size=32, max_size=32),
    "read_token": st.text(HEX, min_size=64, max_size=64),
    "write_token": st.text(HEX, min_size=64, max_size=64),
    "key": KEY,
})


def server_frame(op, payload, fin=True):
    """One unmasked frame as a server sends it (RFC 6455 section 5.2)."""
    n = len(payload)
    head = bytes([(0x80 if fin else 0) | op])
    if n < 126:
        head += bytes([n])
    elif n < 1 << 16:
        head += bytes([126]) + n.to_bytes(2, "big")
    else:
        head += bytes([127]) + n.to_bytes(8, "big")
    return head + payload


class _Sock:
    """Hands out the stream in the given chunks, then times out."""

    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.sent = []

    def settimeout(self, t):
        pass

    def recv(self, n):
        if not self.chunks:
            raise socket.timeout()
        chunk = self.chunks.pop(0)
        if len(chunk) > n:
            self.chunks.insert(0, chunk[n:])
            chunk = chunk[:n]
        return chunk

    def sendall(self, data):
        self.sent.append(data)


def _split(stream, cuts):
    points = sorted({c % (len(stream) + 1) for c in cuts})
    pieces, last = [], 0
    for p in points + [len(stream)]:
        if p > last:
            pieces.append(stream[last:p])
            last = p
    return pieces


def _read_all(ws, limit=64):
    out = []
    for _ in range(limit):
        text = ws.recv(1.0)
        if text is None:
            return out
        out.append(text)
    return out


MESSAGE = st.text(max_size=40)
PAYLOAD = st.one_of(st.binary(max_size=200),
                    st.sampled_from([125, 126, 127, 65535, 65536]).map(bytes))


class WebSocketFuzzTest(unittest.TestCase):
    @given(st.lists(st.tuples(MESSAGE, st.integers(1, 3),
                              st.lists(st.binary(max_size=4), max_size=2)), max_size=5),
           st.lists(st.integers(0, 4096), max_size=8))
    def test_messages_arrive_whole_in_any_chunking(self, messages, cuts):
        """Fragmented text messages with pings between the fragments, cut into
        arbitrary TCP reads, come out as the same texts; each ping is answered
        with a pong carrying its payload."""
        stream, pings = b"", []
        for text, parts, ping_payloads in messages:
            data = text.encode()
            size = -(-len(data) // parts) or 1
            pieces = [data[i:i + size] for i in range(0, len(data), size)] or [b""]
            for i, piece in enumerate(pieces):
                stream += server_frame(0x1 if i == 0 else 0x0, piece, fin=i == len(pieces) - 1)
                for pp in ping_payloads:
                    stream += server_frame(0x9, pp)
                    pings.append(pp)
        sock = _Sock(_split(stream, cuts))
        got = _read_all(cr.WebSocket(sock))
        self.assertEqual(got, [t for t, _, _ in messages])
        reader = cr.WebSocket(None)
        reader._buf = b"".join(sock.sent)
        pongs = []
        while (frame := reader._parse_frame()) is not None:
            pongs.append(frame)
        self.assertEqual(pongs, [(True, 0xA, pp) for pp in pings])

    @given(st.sampled_from([0x1, 0x8, 0x9, 0xA]), PAYLOAD)
    def test_client_frame_round_trip(self, op, payload):
        sock = _Sock([])
        cr.WebSocket(sock)._send(op, payload)
        reader = cr.WebSocket(None)
        reader._buf = b"".join(sock.sent)
        self.assertEqual(reader._parse_frame(), (True, op, payload))
        self.assertEqual(reader._buf, b"")

    @given(st.binary(max_size=200), st.lists(st.integers(0, 256), max_size=6))
    def test_arbitrary_stream(self, stream, cuts):
        ws = cr.WebSocket(_Sock(_split(stream, cuts)))
        try:
            for text in _read_all(ws):
                self.assertIsInstance(text, str)
        except (ConnectionError, cr.ChannelGone):
            pass  # a documented refusal; any other exception fails the test

    @given(st.integers(cr.MAX_MESSAGE_BYTES + 1, 2 ** 63 - 1))
    def test_an_oversized_length_is_refused_before_the_payload(self, n):
        ws = cr.WebSocket(_Sock([bytes([0x81, 127]) + n.to_bytes(8, "big")]))
        with self.assertRaises(ConnectionError):
            ws.recv(1.0)

    @given(st.integers(0, 0xFFFF), st.binary(max_size=8))
    def test_close_frame(self, code, reason):
        ws = cr.WebSocket(_Sock([server_frame(0x8, code.to_bytes(2, "big") + reason)]))
        want = cr.ChannelGone if code == cr.CLOSE_CHANNEL_DELETED else ConnectionError
        with self.assertRaises(want):
            ws.recv(1.0)


class SealFuzzTest(unittest.TestCase):
    @given(KEY, st.binary(max_size=300), st.binary(min_size=16, max_size=16))
    def test_seal_round_trip(self, key, plaintext, nonce):
        self.assertEqual(cloud_hook.open_sealed(key, cloud_hook.seal(key, plaintext, nonce)),
                         plaintext)

    @given(KEY, st.binary(max_size=60), st.integers(0, 10 ** 6), st.integers(1, 255))
    def test_a_changed_byte_is_refused(self, key, plaintext, where, flip):
        raw = bytearray(base64.urlsafe_b64decode(cloud_hook.seal(key, plaintext) + "=="))
        raw[where % len(raw)] ^= flip
        with self.assertRaises(ValueError):
            cloud_hook.open_sealed(key, base64.urlsafe_b64encode(bytes(raw)).decode())

    @given(KEY, st.one_of(st.text(max_size=80), st.text(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_", max_size=80)))
    def test_open_arbitrary_text(self, key, token):
        try:
            cloud_hook.open_sealed(key, token)
        except ValueError:
            return
        self.fail("an unsealed token was accepted")

    @given(KEY, st.one_of(JSON, st.fixed_dictionaries({}, optional={
        "state": st.sampled_from(["working", "waiting", "done", "idle", "ended", "x"]) | JSON,
        "url": st.sampled_from(["https://claude.ai/code/session_abc", "http://x"]) | JSON,
        "title": JSON | st.text(max_size=100), "cwd": JSON | st.text(max_size=200),
        "ts": JSON})))
    def test_decode_report(self, key, report):
        blob = cloud_hook.seal(key, json.dumps(report).encode())
        got = cr.decode_report(key, blob)
        if not isinstance(report, dict) or report.get("state") not in (
                "working", "waiting", "done", "idle", "ended"):
            self.assertIsNone(got)
            return
        url, ts = report.get("url"), report.get("ts")
        want_ts = float(ts) if type(ts) in (int, float) else 0.0
        got_ts = got.pop("ts")
        self.assertTrue(got_ts == want_ts or (math.isnan(got_ts) and math.isnan(want_ts)))
        self.assertEqual(got, {
            "state": report["state"],
            "url": url if cr.is_session_url(url) else "",
            "title": str(report.get("title") or "")[:cloud_hook.TITLE_MAX_CHARS],
            "cwd": str(report.get("cwd") or "")[:120]})
        self.assertIsNone(cr.decode_report(bytes(32) if key != bytes(32) else b"\1" * 32, blob))


class JoinCodeFuzzTest(unittest.TestCase):
    @given(CHANNEL, st.lists(st.integers(0, 400), max_size=3))
    def test_round_trip(self, channel, breaks):
        code = cr.join_code(channel)
        for b in sorted(breaks, reverse=True):     # a pasted code can wrap
            code = code[:b] + "\n " + code[b:]
        want = dict(channel, url=channel["url"].rstrip("/"))
        if len(cr.join_code(channel)) > cr.JOIN_CODE_MAX_CHARS:
            with self.assertRaises(ValueError):
                cr.parse_join_code(code)
            return
        if not want["url"].startswith("https://"):
            with self.assertRaises(ValueError):    # "https://" + "/" strips to "https:"
                cr.parse_join_code(code)
            return
        self.assertEqual(cr.parse_join_code(code), want)

    @given(st.one_of(JSON, st.text(max_size=60).map(lambda t: cr.JOIN_PREFIX + t),
                     st.lists(st.text(max_size=70), min_size=1, max_size=6).map(
                         lambda parts: cr.JOIN_PREFIX + base64.urlsafe_b64encode(
                             "|".join(parts).encode()).decode())))
    def test_arbitrary_text(self, text):
        try:
            out = cr.parse_join_code(text)
        except ValueError:
            return
        cloud_hook.parse_config(cr.setup_config(out))
        self.assertTrue(cloud_hook._is_hex(out["read_token"], 64))


class ChannelFileFuzzTest(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._dir.name, cr.FILE_NAME)

    def tearDown(self):
        self._dir.cleanup()

    @given(CHANNEL.filter(lambda c: c["url"].rstrip("/").startswith("https://")))
    def test_save_load_round_trip(self, channel):
        cr.save_channel(self.path, channel)
        self.assertEqual(cr.load_channel(self.path), dict(channel, url=channel["url"].rstrip("/")))

    @given(st.one_of(JSON, st.fixed_dictionaries({"format": st.just(cr.FILE_FORMAT)}, optional={
        name: JSON | st.text(HEX, min_size=32, max_size=64)
        for name in ("url", "channel", "read_token", "write_token", "key")})),
        st.booleans())
    def test_arbitrary_file(self, data, as_json):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data) if as_json else str(data))
        out = cr.load_channel(self.path)
        if out is not None:
            cloud_hook.parse_config(cr.setup_config(out))
            self.assertTrue(cloud_hook._is_hex(out["read_token"], 64))


if __name__ == "__main__":
    unittest.main()
