"""services/session_peer.py: the keyboard computer's address from the remote-desktop
connection to this computer (NoMachine port 4000, RDP port 3389)."""
import socket
import struct
import threading
import time
import unittest

from polyhost.services import session_peer as sp


def _addr4(text):
    """The 8 hex digits /proc/net/tcp prints for an IPv4 address on this CPU."""
    return "%08X" % struct.unpack("=I", socket.inet_aton(text))[0]


def _addr6(text):
    """The 32 hex digits /proc/net/tcp6 prints for an IPv4-mapped address."""
    raw = b"\0" * 10 + b"\xff\xff" + socket.inet_aton(text)
    return "".join("%08X" % struct.unpack("=I", raw[i:i + 4])[0] for i in range(0, 16, 4))


PROC_HEADER = ("  sl  local_address rem_address   st tx_queue rx_queue tr tm->when "
               "retrnsmt   uid  timeout inode\n")


def proc_row(local, local_port, remote, state="01", v6=False):
    fmt = _addr6 if v6 else _addr4
    return ("   0: %s:%04X %s:C350 %s 00000000:00000000 00:00000000 00000000 0 0 1\n"
            % (fmt(local), local_port, fmt(remote), state))


def windows_table(rows):
    """A MIB_TCPTABLE: `rows` are (state, local_ip, local_port, remote_ip, remote_port)."""
    def port(p):
        return struct.unpack("<I", struct.pack(">H", p) + b"\0\0")[0]

    def ip(a):
        return struct.unpack("<I", socket.inet_aton(a))[0]
    data = struct.pack("<I", len(rows))
    for state, lip, lport, rip, rport in rows:
        data += struct.pack("<5I", state, ip(lip), port(lport), ip(rip), port(rport))
    return data


MACOS = ("tcp4       0      0  10.0.0.5.3389         10.0.0.9.51234        ESTABLISHED\n"
         "tcp4       0      0  *.22                  *.*                   LISTEN\n")


class ParseTest(unittest.TestCase):
    def test_proc_rows_give_the_peer_of_established_connections_to_the_port(self):
        text = (PROC_HEADER
                + proc_row("10.0.0.5", 3389, "10.0.0.9")
                + proc_row("10.0.0.5", 3389, "10.0.0.8", state="0A")      # listening
                + proc_row("10.0.0.5", 22, "10.0.0.7")                    # another port
                + proc_row("127.0.0.1", 3389, "127.0.0.1"))               # loopback
        self.assertEqual(sp.parse_proc_tcp(text, [3389]), ["10.0.0.9"])
        self.assertEqual(sp.parse_proc_tcp(text, [22]), ["10.0.0.7"])
        self.assertEqual(sp.parse_proc_tcp(text, [4000]), [])
        self.assertEqual(sp.parse_proc_tcp("", [3389]), [])

    def test_proc_tcp6_reads_ipv4_mapped_peers_and_drops_native_ipv6(self):
        native = "00000000000000000000000001000000"                      # ::1
        text = (PROC_HEADER
                + proc_row("10.0.0.5", 3389, "10.0.0.9", v6=True)
                + "   1: %s:0D3D %s:C350 01 0:0 0:0 0 0 1\n" % (native, native))
        self.assertEqual(sp.parse_proc_tcp(text, [3389]), ["10.0.0.9"])

    def test_proc_garbage_is_skipped_not_raised(self):
        self.assertEqual(sp.parse_proc_tcp("header\nnot a row\n1: x y 01\n", [3389]), [])

    def test_windows_table_keeps_established_rows_to_the_wanted_ports(self):
        table = windows_table([
            (5, "10.0.0.5", 3389, "10.0.0.9", 51234),
            (5, "10.0.0.5", 4000, "10.0.0.8", 40000),
            (2, "10.0.0.5", 3389, "0.0.0.0", 0),               # listening
            (5, "10.0.0.5", 443, "52.1.2.3", 50000),           # another port
            (5, "127.0.0.1", 3389, "127.0.0.1", 50001)])       # loopback
        self.assertEqual(sp.parse_windows_table(table, [3389]), ["10.0.0.9"])
        self.assertEqual(sp.parse_windows_table(table, [4000]), ["10.0.0.8"])
        self.assertEqual(sp.parse_windows_table(table, [22]), [])

    def test_windows_table_survives_a_short_or_empty_buffer(self):
        self.assertEqual(sp.parse_windows_table(b"", [3389]), [])
        short = windows_table([(5, "10.0.0.5", 3389, "10.0.0.9", 1)])[:-4]
        self.assertEqual(sp.parse_windows_table(short, [3389]), [])
        self.assertEqual(sp.parse_windows_table(struct.pack("<I", 9), [3389]), [])

    def test_netstat_reads_the_macos_dotted_ports(self):
        self.assertEqual(sp.parse_netstat(MACOS, [3389]), ["10.0.0.9"])


class DetectTest(unittest.TestCase):
    def test_linux_reads_tcp_and_tcp6_and_the_first_port_wins(self):
        tcp = PROC_HEADER + proc_row("10.0.0.5", 3389, "10.0.0.9")
        tcp6 = PROC_HEADER + proc_row("10.0.0.5", 4000, "10.0.0.8", v6=True)
        reads = {"tcp": tcp, "tcp6": tcp6}
        self.assertEqual(sp.detect_client_address((4000, 3389), "linux", reads.get),
                         (True, "10.0.0.8"))
        self.assertEqual(sp.detect_client_address((3389, 4000), "linux", reads.get),
                         (True, "10.0.0.9"))

    def test_linux_without_ipv6_is_not_a_failure_but_an_unreadable_tcp6_is(self):
        tcp = PROC_HEADER + proc_row("10.0.0.5", 3389, "10.0.0.9")
        self.assertEqual(sp.detect_client_address((3389,), "linux",
                                                  {"tcp": tcp, "tcp6": ""}.get),
                         (True, "10.0.0.9"))
        nobody = {"tcp": PROC_HEADER, "tcp6": ""}
        self.assertEqual(sp.detect_client_address((3389,), "linux", nobody.get),
                         (True, None))
        self.assertEqual(sp.detect_client_address((3389,), "linux",
                                                  {"tcp": PROC_HEADER}.get),
                         (False, None))                 # tcp6 unreadable: keep the address

    def test_the_real_reader_gives_an_empty_tcp6_when_the_file_is_absent(self):
        from unittest import mock
        with mock.patch("builtins.open", side_effect=FileNotFoundError):
            self.assertEqual(sp._read("tcp6"), "")
            self.assertIsNone(sp._read("tcp"))
        with mock.patch("builtins.open", side_effect=PermissionError):
            self.assertIsNone(sp._read("tcp6"))

    def test_nobody_connected_is_a_successful_none(self):
        reads = {"tcp": PROC_HEADER, "tcp6": PROC_HEADER}
        self.assertEqual(sp.detect_client_address((4000, 3389), "linux", reads.get),
                         (True, None))
        self.assertEqual(sp.detect_client_address((3389,), "win32",
                                                  lambda k: windows_table([])),
                         (True, None))

    def test_a_table_that_cannot_be_read_is_not_read_as_nobody(self):
        for platform in ("linux", "win32", "darwin"):
            self.assertEqual(sp.detect_client_address((3389,), platform, lambda k: None),
                             (False, None), platform)

    def test_windows_and_macos(self):
        table = windows_table([(5, "10.0.0.5", 3389, "10.0.0.9", 1)])
        self.assertEqual(sp.detect_client_address((4000, 3389), "win32", lambda k: table),
                         (True, "10.0.0.9"))
        self.assertEqual(sp.detect_client_address((3389,), "darwin", lambda k: MACOS),
                         (True, "10.0.0.9"))

    def test_the_real_linux_table_can_be_read(self):
        if not sp.sys.platform.startswith("linux"):
            self.skipTest("Linux only")
        ok, _address = sp.detect_client_address((65001,))
        self.assertTrue(ok)


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class WatcherTest(unittest.TestCase):
    def _watcher(self, answers, **kwargs):
        calls = []

        def detect(ports):
            calls.append(ports)
            return answers.pop(0) if len(answers) > 1 else answers[0]
        clock = _Clock()
        watcher = sp.ClientAddressWatcher(detect=detect, clock=clock, **kwargs)
        return watcher, calls, clock

    def test_a_failed_look_keeps_the_last_address(self):
        watcher, _calls, _clock = self._watcher(
            [(True, "10.0.0.9"), (False, None), (True, None)])
        watcher.refresh()
        self.assertEqual(watcher.address(), "10.0.0.9")
        watcher.refresh()                       # the table could not be read
        self.assertEqual(watcher.address(), "10.0.0.9")
        watcher.refresh()                       # a real "nobody connected"
        self.assertIsNone(watcher.address())

    def test_address_starts_no_thread_and_no_look(self):
        watcher, calls, _clock = self._watcher([(True, "10.0.0.9")])
        self.assertIsNone(watcher.address())
        self.assertIsNone(watcher._thread)
        self.assertEqual(calls, [])

    def test_no_timer_without_an_address_or_after_ten_idle_minutes(self):
        watcher, _calls, clock = self._watcher([(True, "10.0.0.9")])
        self.assertIsNone(watcher._timeout())               # nothing found, not touched
        watcher._last_touch = clock.now
        self.assertIsNone(watcher._timeout())               # touched, but no address
        watcher.refresh()
        self.assertEqual(watcher._timeout(), sp.IDLE_INTERVAL_S)
        clock.now += 30
        self.assertEqual(watcher._timeout(), sp.IDLE_INTERVAL_S - 30)
        clock.now += 29
        self.assertEqual(watcher._timeout(), 1)
        clock.now += 1000                                   # past the active time
        self.assertIsNone(watcher._timeout())               # an idle computer runs nothing

    def test_a_window_change_after_idle_looks_again(self):
        watcher, calls, clock = self._watcher([(True, "10.0.0.9")], min_gap=0.0)
        watcher._last_touch = clock.now
        watcher.refresh()
        clock.now += sp.ACTIVE_FOR_S + 1
        self.assertIsNone(watcher._timeout())               # idle: no timer
        before = len(calls)
        self.addCleanup(watcher.stop)
        watcher.touch()                                     # a window changed
        deadline = time.monotonic() + 2
        while len(calls) == before and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(len(calls), before + 1)
        time.sleep(0.05)
        self.assertEqual(watcher._timeout(), sp.IDLE_INTERVAL_S)    # the timer is back

    def test_a_failed_send_does_not_wake_an_idle_watcher(self):
        watcher, calls, clock = self._watcher([(True, "10.0.0.9")], min_gap=0.0)
        self.addCleanup(watcher.stop)
        watcher.request_look()                              # never touched: ignored
        self.assertIsNone(watcher._thread)
        watcher._last_touch = clock.now
        clock.now += sp.ACTIVE_FOR_S + 1                    # no window change for 10 min
        watcher.request_look()
        self.assertIsNone(watcher._thread)
        time.sleep(0.05)
        self.assertEqual(calls, [])

    def test_a_timer_that_runs_out_after_the_idle_cutoff_does_not_look(self):
        watcher, calls, clock = self._watcher([(True, "10.0.0.9")], min_gap=0.0,
                                              idle_interval=0.2)
        self.addCleanup(watcher.stop)
        watcher.refresh()                                   # an address is found
        watcher._last_touch = clock.now                     # in use ...
        before = len(calls)
        watcher.request_look()                              # starts the thread: one look
        deadline = time.monotonic() + 2
        while len(calls) == before and time.monotonic() < deadline:
            time.sleep(0.01)
        after_first = len(calls)
        clock.now += sp.ACTIVE_FOR_S + 1                    # ... then idle, mid-wait
        time.sleep(0.6)                                     # the 0.2 s timer ends
        self.assertEqual(len(calls), after_first)

    def test_a_request_that_waits_out_the_gap_past_the_cutoff_does_not_look(self):
        watcher, calls, clock = self._watcher([(True, "10.0.0.9")], min_gap=0.4)
        self.addCleanup(watcher.stop)
        watcher.refresh()                                   # a look just ran: the gap holds
        watcher._last_touch = clock.now
        before = len(calls)
        watcher.request_look()                              # in use: the thread waits the gap
        time.sleep(0.1)
        clock.now += sp.ACTIVE_FOR_S + 1                    # the cutoff passes meanwhile
        time.sleep(0.6)
        self.assertEqual(len(calls), before)

    def test_a_failed_send_wakes_a_watcher_in_use(self):
        watcher, calls, clock = self._watcher([(True, "10.0.0.9")], min_gap=0.0)
        self.addCleanup(watcher.stop)
        watcher._last_touch = clock.now
        watcher.request_look()
        deadline = time.monotonic() + 2
        while not calls and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(len(calls), 1)

    def test_repeated_failures_log_one_warning(self):
        watcher, _calls, _clock = self._watcher([(False, None)])
        with self.assertLogs(sp.log, "WARNING") as logs:
            for _ in range(sp.WARN_AFTER_FAILURES + 3):
                watcher.refresh()
        self.assertEqual(len(logs.records), 1)

    def test_a_touch_runs_a_look_on_the_thread_and_requests_are_rate_limited(self):
        done = threading.Event()
        count = []

        def detect(ports):
            count.append(time.monotonic())
            done.set()
            return True, "10.0.0.9"
        watcher = sp.ClientAddressWatcher(detect=detect, min_gap=0.3)
        self.addCleanup(watcher.stop)
        for _ in range(5):                                  # five quick window changes
            watcher.touch()
        self.assertTrue(done.wait(2))
        time.sleep(0.05)
        deadline = time.monotonic() + 2
        while watcher.address() != "10.0.0.9" and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(watcher.address(), "10.0.0.9")
        self.assertEqual(len(count), 1)                     # one look for all five
        watcher.touch()                                     # the gap has to pass first
        deadline = time.monotonic() + 2
        while len(count) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(len(count), 2)
        self.assertGreaterEqual(count[1] - count[0], 0.3)


class _Watcher:
    def __init__(self, address):
        self._address = address
        self.asked = 0

    def address(self):
        self.asked += 1
        return self._address


class ResolveTest(unittest.TestCase):
    def test_the_host_file_has_priority_over_host_and_detection(self):
        w = _Watcher("10.0.0.9")
        self.assertEqual(sp.resolve_host("1.1.1.1", True, " 2.2.2.2\n", True, w), "2.2.2.2")
        self.assertEqual(w.asked, 0)

    def test_without_a_host_file_the_host_is_used(self):
        self.assertEqual(sp.resolve_host("1.1.1.1", False, None, True, _Watcher("x")),
                         "1.1.1.1")

    def test_detection_fills_in_when_nothing_names_a_host(self):
        w = _Watcher("10.0.0.9")
        self.assertEqual(sp.resolve_host(None, False, None, True, w), "10.0.0.9")
        # a host file that is absent or empty names none
        self.assertEqual(sp.resolve_host(None, True, None, True, w), "10.0.0.9")
        self.assertEqual(sp.resolve_host(None, True, "  \n", True, w), "10.0.0.9")

    def test_an_absent_host_file_does_not_fall_back_to_host_without_detection(self):
        """Unchanged: a host file with no file means no active session."""
        self.assertIsNone(sp.resolve_host("1.1.1.1", True, None, False, None))

    def test_a_found_address_is_not_used_without_the_authenticated_connection(self):
        """Port 3389 or 4000 accepts a TCP connection before anyone logs in, and the
        plaintext relay would send that computer the window titles."""
        w = _Watcher("10.0.0.9")
        self.assertIsNone(sp.resolve_host(None, False, None, True, w, authenticated=False))
        self.assertEqual(w.asked, 0)
        # a host or host file named by the user is not affected
        self.assertEqual(sp.resolve_host("1.1.1.1", False, None, True, w,
                                         authenticated=False), "1.1.1.1")
        self.assertEqual(sp.resolve_host(None, True, "2.2.2.2", True, w,
                                         authenticated=False), "2.2.2.2")
        self.assertEqual(sp.resolve_host(None, False, None, True, w, authenticated=True),
                         "10.0.0.9")

    def test_nothing_named_and_no_detection_is_no_host(self):
        self.assertIsNone(sp.resolve_host(None, False, None, False, None))
        self.assertIsNone(sp.resolve_host(None, False, None, True, _Watcher(None)))


if __name__ == "__main__":
    unittest.main()
