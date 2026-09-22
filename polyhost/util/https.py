"""One TLS trust store for every `urllib` fetch the app makes.

⚠️ **On a python.org macOS build `urllib` has NO certificate store at all, so
every HTTPS fetch fails while `requests` succeeds on the same machine** — the
installer ships `Install Certificates.command` to wire one up and a user who
never ran it has an empty trust store. `requests` does not care because it
carries `certifi` and points OpenSSL at it explicitly; `urllib` uses
`ssl.create_default_context()`, which on that build finds nothing.

Measured in the field (macOS, 2026-09-21): in one session and seconds apart,
`api.open-meteo.com` over `requests` returned 200 twice while every
`cdn.jsdelivr.net` fetch through `urlopen` died with
`CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`. Same
process, same network, same minute — so it is neither the network nor the CDN,
and the failing calls were exactly the three that do not go through `requests`.

⚠️ **The context is the UNION of both stores, never a replacement**, and that
is the whole design. Swapping the platform store for certifi's would fix macOS
and break the opposite case: a corporate MITM proxy whose root is installed in
the SYSTEM store and is not in certifi. Loading the platform's defaults first
and then ADDING certifi's roots can only ever accept more than before, so no
machine that works today can stop working.
"""

from __future__ import annotations

import logging
import ssl

log = logging.getLogger("PolyHost")

# ⚠️ ONE dict, not two module globals, and the KEY'S PRESENCE is the
# "already tried" latch. The obvious shape is a `_CONTEXT` plus a `_FAILED`
# bool, and CodeQL `py/unused-global-variable` flags the bool: its write is
# never read on its own path, only by the NEXT call's guard, which the query
# does not follow across invocations. Returning the global instead of the
# local fixes that for `_CONTEXT` (the return reads the write) and cannot fix
# it for a latch, which is read nowhere else.
#
# Deleting the latch on the query's advice is the trap --
# `shortcut_icons.load_hints` and its three sibling memos each carry a note
# about it -- because a failed build would then be retried on every icon
# fetch. Mutating a dict rebinds no global, so the latch survives and there is
# nothing left for the query to report. Absent key = never tried; present and
# None = tried and failed; present and a context = ready.
_CACHE: dict = {}
_KEY = "context"


def ssl_context() -> ssl.SSLContext | None:
    """A verifying context trusting the platform's roots AND certifi's.

    None when one could not be built, which every caller must treat as "use the
    default" rather than as an error: `urlopen(..., context=None)` is exactly
    the behaviour this module replaces, so the worst case is the status quo.

    Cached — building one parses a few hundred certificates, and these callers
    run per icon fetch.
    """
    if _KEY in _CACHE:
        return _CACHE[_KEY]
    try:
        ctx = ssl.create_default_context()
    except Exception as exc:
        # Verification stays ON: returning None falls back to urllib's own
        # default context, which also verifies. There is no path here that
        # disables checking.
        log.debug("Could not build an SSL context: %s", exc)
        _CACHE[_KEY] = None
        return None
    try:
        import certifi
        ctx.load_verify_locations(cafile=certifi.where())
    except Exception as exc:
        # certifi ships with `requests`, a hard dependency, so this is a broken
        # install rather than a normal state -- and the platform store alone is
        # still correct everywhere except the macOS case above.
        log.debug("certifi unavailable, using the platform trust store "
                  "only: %s", exc)
    _CACHE[_KEY] = ctx
    return ctx
