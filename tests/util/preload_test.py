"""util/preload: the image libraries load on a background thread at start."""
import logging
import subprocess
import sys
import unittest

from polyhost.util import preload


class PreloadTest(unittest.TestCase):

    def test_a_fresh_process_has_numpy_and_pillow_after_the_thread(self):
        # A subprocess, because this test process imported numpy long ago.
        code = ("import sys, logging\n"
                "from polyhost.util import preload\n"
                "assert 'numpy' not in sys.modules and 'PIL.Image' not in sys.modules\n"
                "preload.start(logging.getLogger('x')).join(60)\n"
                "print('numpy' in sys.modules, 'PIL.Image' in sys.modules,"
                " 'PIL.PngImagePlugin' in sys.modules)\n")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.split(), ["True", "True", "True"])

    def test_it_logs_one_line_with_each_module(self):
        log = logging.getLogger("preload-test")
        with self.assertLogs(log, level="INFO") as cm:
            preload.start(log).join(60)
        self.assertEqual(len(cm.output), 1)
        for name in preload.MODULES:
            self.assertIn(name, cm.output[0])

    def test_a_failing_import_is_a_warning_not_an_exception(self):
        log = logging.getLogger("preload-test")
        with self.assertLogs(log, level="WARNING") as cm:
            thread = preload.start(log, modules=("numpy", "no_such_module_here"))
            thread.join(60)
        self.assertFalse(thread.is_alive())
        self.assertTrue(any("no_such_module_here" in line for line in cm.output))

    def test_the_module_does_not_import_qt(self):
        code = ("import sys\nfrom polyhost.util import preload\n"
                "preload.start().join(60)\n"
                "print(any(m.startswith('PyQt5') for m in sys.modules))\n")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True, timeout=120)
        self.assertEqual(out.stdout.strip(), "False", out.stderr)


if __name__ == "__main__":
    unittest.main()
