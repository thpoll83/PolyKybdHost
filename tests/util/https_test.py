"""One trust store for every `urllib` fetch — see `polyhost/util/https.py`.

⚠️ The bug these guard against is INVISIBLE off macOS: on Linux and Windows a
bare `urlopen` verifies perfectly, so a missing `context=` passes every test on
this machine and fails on every python.org Mac. The call-site tests below
therefore assert the ARGUMENT, not the outcome.
"""

import ssl
import unittest
import unittest.mock as mock

from polyhost.util import https


class SslContextTest(unittest.TestCase):

    def setUp(self):
        # ⚠️ CLEAR the dict, never rebind it -- `ssl_context` reads the
        # module-level object, so `https._CACHE = {}` here would leave the
        # function looking at the old one and the reset would do nothing.
        https._CACHE.clear()
        self.addCleanup(https._CACHE.clear)

    def test_it_returns_a_VERIFYING_context(self):
        """⚠️ The one thing this must never do is make TLS more permissive."""
        ctx = https.ssl_context()
        self.assertIsInstance(ctx, ssl.SSLContext)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)

    def test_it_trusts_BOTH_stores_not_just_certifi(self):
        """⚠️ The union is the design. Replacing the platform store with
        certifi's would fix macOS and break a corporate MITM proxy whose root is
        installed in the system store and is not in certifi — so the platform
        defaults are loaded FIRST and certifi is added on top."""
        calls = []
        real = ssl.create_default_context

        def spy(*a, **kw):
            ctx = real(*a, **kw)
            calls.append("default")
            orig = ctx.load_verify_locations

            def note(*aa, **kk):
                calls.append("certifi")
                return orig(*aa, **kk)

            ctx.load_verify_locations = note
            return ctx

        with mock.patch.object(https.ssl, "create_default_context", spy):
            https.ssl_context()
        self.assertEqual(calls, ["default", "certifi"])

    def test_a_MISSING_certifi_still_yields_the_platform_store(self):
        """A broken install must degrade to today's behaviour, not to None —
        the platform store alone is correct everywhere but the macOS case."""
        real_import = __import__

        def no_certifi(name, *a, **kw):
            if name == "certifi":
                raise ImportError("no certifi")
            return real_import(name, *a, **kw)

        with mock.patch("builtins.__import__", no_certifi):
            ctx = https.ssl_context()
        self.assertIsInstance(ctx, ssl.SSLContext)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)

    def test_it_returns_NONE_rather_than_raising_when_no_context_can_be_built(self):
        """None means "use urllib's default", which also verifies. Every caller
        passes it straight to `context=`, where None is the status quo."""
        with mock.patch.object(https.ssl, "create_default_context",
                               side_effect=OSError("no ssl")):
            self.assertIsNone(https.ssl_context())

    def test_the_failure_is_not_retried_on_every_fetch(self):
        with mock.patch.object(https.ssl, "create_default_context",
                               side_effect=OSError("no ssl")) as create:
            https.ssl_context()
            https.ssl_context()
        self.assertEqual(create.call_count, 1)

    def test_the_context_is_CACHED(self):
        """These callers run per icon fetch and building one parses a few
        hundred certificates."""
        self.assertIs(https.ssl_context(), https.ssl_context())


class CallSiteTest(unittest.TestCase):
    """⚠️ Every runtime `urlopen` in the package must pass the context.

    A new one that forgets is a fetch that works on the developer's Linux box
    and fails on every python.org Mac — which is exactly how all three of these
    shipped.
    """

    def test_EVERY_urlopen_in_polyhost_passes_a_context(self):
        import pathlib
        import re
        root = pathlib.Path(https.__file__).resolve().parents[1]
        offenders = []
        for path in root.rglob("*.py"):
            if "overlay_sources" in path.parts:
                continue            # build-time tooling, not the shipped app
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"urlopen\((?:[^()]|\([^()]*\))*\)", text):
                if "context=" not in m.group(0):
                    offenders.append("%s: %s" % (path.name, m.group(0)[:60]))
        self.assertEqual(offenders, [], "urlopen without a trust store")


if __name__ == "__main__":
    unittest.main()
