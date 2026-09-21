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

_CONTEXT: ssl.SSLContext | None = None
_FAILED = False


def ssl_context() -> ssl.SSLContext | None:
    """A verifying context trusting the platform's roots AND certifi's.

    None when one could not be built, which every caller must treat as "use the
    default" rather than as an error: `urlopen(..., context=None)` is exactly
    the behaviour this module replaces, so the worst case is the status quo.

    Cached — building one parses a few hundred certificates, and these callers
    run per icon fetch.
    """
    global _CONTEXT, _FAILED
    if _CONTEXT is not None or _FAILED:
        return _CONTEXT
    try:
        ctx = ssl.create_default_context()
    except Exception as exc:
        # Verification stays ON: returning None falls back to urllib's own
        # default context, which also verifies. There is no path here that
        # disables checking.
        log.debug("Could not build an SSL context: %s", exc)
        _FAILED = True
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
    _CONTEXT = ctx
    return ctx
