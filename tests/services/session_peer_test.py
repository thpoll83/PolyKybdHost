"""services/session_peer.py: the keyboard computer's address from the remote-desktop
connection to this computer (NoMachine port 4000, RDP port 3389)."""
import unittest

from polyhost.services import session_peer as sp

SS_HEADER = "Recv-Q Send-Q Local Address:Port  Peer Address:Port Process\n"

WINDOWS = (
    "Active Connections\n\n"
    "  Proto  Local Address          Foreign Address        State\n"
    "  TCP    0.0.0.0:3389           0.0.0.0:0              LISTENING\n"
    "  TCP    10.0.0.5:3389          10.0.0.9:51234         ESTABLISHED\n"
    "  TCP    10.0.0.5:4000          10.0.0.8:50000         ESTABLISHED\n"
    "  TCP    10.0.0.5:51000         52.1.2.3:443           ESTABLISHED\n")

MACOS = ("tcp4       0      0  10.0.0.5.3389         10.0.0.9.51234        ESTABLISHED\n"
         "tcp4       0      0  *.22                  *.*                   LISTEN\n")


class ParseTest(unittest.TestCase):
    def test_ss_rows_give_the_peer_address(self):
        text = SS_HEADER + "0 0 10.0.0.5:3389 10.0.0.9:51234\n"
        self.assertEqual(sp.parse_ss(text), ["10.0.0.9"])

    def test_ss_maps_ipv4_mapped_and_drops_loopback_and_native_ipv6(self):
        text = (SS_HEADER
                + "0 0 [::ffff:10.0.0.5]:3389 [::ffff:10.0.0.7]:1\n"
                + "0 0 127.0.0.1:3389 127.0.0.1:2\n"
                + "0 0 [::1]:3389 [::1]:3\n"
                + "0 0 [2001:db8::5]:3389 [2001:db8::9]:4\n"
                + "0 0 10.0.0.5:3389 10.0.0.9:5\n")
        self.assertEqual(sp.parse_ss(text), ["10.0.0.7", "10.0.0.9"])

    def test_netstat_keeps_only_connections_to_the_wanted_ports(self):
        self.assertEqual(sp.parse_netstat(WINDOWS, [3389]), ["10.0.0.9"])
        self.assertEqual(sp.parse_netstat(WINDOWS, [4000]), ["10.0.0.8"])
        self.assertEqual(sp.parse_netstat(WINDOWS, [22]), [])

    def test_netstat_reads_the_macos_dotted_ports(self):
        self.assertEqual(sp.parse_netstat(MACOS, [3389]), ["10.0.0.9"])


class DetectTest(unittest.TestCase):
    def test_linux_asks_ss_once_per_port_and_the_first_port_wins(self):
        calls = []

        def run(argv):
            calls.append(argv)
            if "( sport = :4000 )" in argv:
                return SS_HEADER + "0 0 10.0.0.5:4000 10.0.0.8:1\n"
            return SS_HEADER + "0 0 10.0.0.5:3389 10.0.0.9:2\n"
        self.assertEqual(sp.detect_client_address((4000, 3389), "linux", run),
                         (True, "10.0.0.8"))
        self.assertEqual(len(calls), 1)             # 4000 answered, 3389 not asked
        self.assertEqual(calls[0][:4], ["ss", "-tn", "state", "established"])

    def test_linux_nobody_connected_is_a_successful_none(self):
        self.assertEqual(sp.detect_client_address((4000, 3389), "linux",
                                                  lambda argv: SS_HEADER), (True, None))

    def test_a_tool_that_fails_is_not_read_as_nobody(self):
        self.assertEqual(sp.detect_client_address((4000, 3389), "linux",
                                                  lambda argv: None), (False, None))
        self.assertEqual(sp.detect_client_address((4000, 3389), "win32",
                                                  lambda argv: None), (False, None))

    def test_windows_and_macos_use_netstat(self):
        seen = []

        def win(argv):
            seen.append(argv)
            return WINDOWS
        self.assertEqual(sp.detect_client_address((4000, 3389), "win32", win),
                         (True, "10.0.0.8"))
        self.assertEqual(seen[0][:2], ["netstat", "-an"])
        self.assertEqual(sp.detect_client_address((3389,), "darwin", lambda a: MACOS),
                         (True, "10.0.0.9"))


class WatcherTest(unittest.TestCase):
    def test_a_failed_look_keeps_the_last_address(self):
        answers = [(True, "10.0.0.9"), (False, None), (True, None)]
        watcher = sp.ClientAddressWatcher(detect=lambda ports: answers.pop(0))
        watcher.refresh()
        self.assertEqual(watcher._address, "10.0.0.9")
        watcher.refresh()                       # the tool failed
        self.assertEqual(watcher._address, "10.0.0.9")
        watcher.refresh()                       # a real "nobody connected"
        self.assertIsNone(watcher._address)

    def test_address_starts_the_thread_once_and_answers_from_memory(self):
        import threading
        started = threading.Event()

        def detect(ports):
            started.set()
            return True, "10.0.0.9"
        watcher = sp.ClientAddressWatcher(detect=detect, interval=0.01)
        self.addCleanup(watcher.stop)
        watcher.address()
        self.assertTrue(started.wait(2))
        thread = watcher._thread
        watcher.address()
        self.assertIs(watcher._thread, thread)
        for _ in range(200):
            if watcher.address() == "10.0.0.9":
                break
            started.wait(0.01)
        self.assertEqual(watcher.address(), "10.0.0.9")


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

    def test_nothing_named_and_no_detection_is_no_host(self):
        self.assertIsNone(sp.resolve_host(None, False, None, False, None))
        self.assertIsNone(sp.resolve_host(None, False, None, True, _Watcher(None)))


if __name__ == "__main__":
    unittest.main()
