"""Carry a forwarded app's shortcuts across the machine boundary, as TEXT.

A forwarded application runs on the OTHER computer, so its accessibility tree
can only be read there -- the same reason `AppIdentity` is resolved on the
forwarder and relayed rather than looked up on the keyboard machine. This is the
shortcut half of that relay.

⚠️ **The wire carries THREE fields per shortcut and no pixels**: the folded QMK
modifier nibble, the HID usage, and the label. That is not a size optimisation,
it is the whole division of labour -- `shortcut_overlays.plan_report()` reads
exactly `mods`, `hid` and `label` off a harvested shortcut and nothing else, and
everything downstream of it (which concept a label means, which catalog subset
to fetch, what height and corner to raster at) is knowable only on the keyboard
machine. A forwarder that rendered masks would need the icon catalog, the keycap
geometry and the placement setting, none of which are its business, and all
three change under it whenever the user changes a setting here.

⚠️ **Nothing in this module may fail a window report.** Shortcuts ride the main
report frame, unlike the icon, which travels in a separate follow-up call the
forwarder already guards. So `decode` is TOTAL: junk is dropped, oversize is
clamped, and the worst case is a window that draws no shortcut icons -- never a
window the keyboard stops tracking. It is also the parse of attacker-shaped
input on the one method reachable over the network, which is the second reason
every bound here is explicit rather than implied.
"""

from __future__ import annotations

from polyhost.services.shortcut_source.model import Shortcut, displayable_hid

# A generous ceiling next to what an application really exposes: the richest
# measured harvest is 26 accelerators (mousepad's GtkMenuBar), and the planner
# caps what it will DRAW at `shortcut_overlays.MAX_SLOTS` regardless. The number
# that matters is that it is bounded at all -- see the module docstring.
MAX_SHORTCUTS = 64
# Labels are menu-item text. "Toggle Comment Line" is 20; 64 leaves room for a
# localized one without letting a frame carry prose.
MAX_LABEL = 64


def encode(shortcuts) -> list[list]:
    """Harvested shortcuts -> the JSON-safe list the report frame carries.

    Drops anything the receiver could not use anyway (no keycap slot, no label,
    a modifier outside the nibble), so the frame does not pay to carry it.
    """
    out = []
    for sc in shortcuts or ():
        hid = getattr(sc, "hid", None)
        mods = getattr(sc, "mods", 0)
        label = (getattr(sc, "label", "") or "").strip()
        try:
            hid = int(hid)
            mods = int(mods or 0)
        except (TypeError, ValueError):
            continue
        if not label or not displayable_hid(hid) or not 0 <= mods <= 0x0F:
            continue
        out.append([mods, hid, label[:MAX_LABEL]])
        if len(out) >= MAX_SHORTCUTS:
            break
    return out


def decode(value) -> tuple[Shortcut, ...]:
    """The report frame's list -> `Shortcut` objects the planner can read.

    Never raises and never refuses the whole list over one bad entry: see the
    module docstring for why a cosmetic field may not fail a window report.
    """
    if not isinstance(value, (list, tuple)):
        return ()
    out = []
    for item in value[:MAX_SHORTCUTS]:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        mods, hid, label = item[0], item[1], item[2]
        try:
            mods, hid = int(mods), int(hid)
        except (TypeError, ValueError):
            continue
        if not 0 <= mods <= 0x0F or not displayable_hid(hid):
            continue
        label = str(label).strip()[:MAX_LABEL]
        if not label:
            continue
        # `accel`/`keysym`/`role` are the BACKEND's raw material, consumed by
        # `pick_binding`/`parse_accel` before the wire and never read again
        # downstream -- so they are deliberately absent from the frame rather
        # than reconstructed into a plausible-looking lie. The refusal lines
        # spell the chord with `shortcut_overlays.describe`, which builds it
        # from mods+hid, so nothing user-visible loses anything.
        out.append(Shortcut(label=label, role="", accel="", mods=mods,
                            keysym="", hid=hid, displayable=True))
    return tuple(out)


class RelaySource:
    """The forwarder's side: harvest THIS machine's shortcuts, off the poll.

    ⚠️ It lives here rather than in `forwarder.py` because that module imports
    pywinctl at load time and so cannot be tested in the documented environment
    -- and the parts worth testing are exactly the ones below: the three-state
    answer, the in-flight guard, and the privacy gate.

    ⚠️ **`None` and `[]` are different answers and nothing may collapse them.**
    `None` means "not harvested yet" and starts one; `[]` means the harvest ran
    and this application exposes no accelerators. The receiver stops asking on
    either list and keeps asking on neither, so reading `[]` as "no answer"
    re-walks a proven-empty tree on every report, and reading `None` as "nothing
    found" records an answer nobody gave.
    """

    def __init__(self, log, *, harvest=None, reason=None, allowed=None,
                 on_ready=None, spawn=None):
        self.log = log
        self._cache = {}
        self._inflight = set()
        self._harvest = harvest
        self._reason = reason
        self._allowed = allowed
        self._on_ready = on_ready
        self._spawn = spawn or self._thread

    @staticmethod
    def _thread(fn, name):
        import threading
        threading.Thread(target=fn, name=name, daemon=True).start()

    def shortcuts_for(self, name):
        """The wire list for `name`, `[]`, or None while a harvest is running.

        ⚠️ Never harvests INLINE. The window poll calls this, and a harvest is a
        tree walk over another process -- AT-SPI charges a D-Bus round trip per
        node -- so a synchronous answer here would stall every focus change by
        seconds. Same contract as `ShortcutIconFetcher` on the other side.
        """
        key = str(name or "")
        if not key:
            return None
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        if not self._is_allowed():
            # Recorded as an empty answer rather than left unanswered, so the
            # receiver is told once and stops asking on every report.
            self._cache[key] = []
            return []
        if key not in self._inflight:
            self._inflight.add(key)
            self._spawn(lambda: self._run(key), "poly-fwd-shortcuts")
        return None

    def _is_allowed(self):
        """The privacy switch, read on THIS machine because this is where the
        accessibility tree is read. The keyboard machine has its own copy and
        only asks while its own is on, so both have to agree before any
        application's tree is touched."""
        if self._allowed is not None:
            return bool(self._allowed())
        try:
            from polyhost.settings import read_setting
            return bool(read_setting("shortcut_icons_enabled", True))
        except Exception:
            return True

    def _run(self, name):
        """The slow half, on its own thread. Every failure costs an empty list.

        Caches the WIRE form, not the `Shortcut` objects: it is what gets sent,
        it is bounded, and it keeps the backend's raw accelerator strings off
        both the cache and the frame.
        """
        wire = []
        try:
            reason, harvest = self._backend()
            unusable = reason()
            if unusable is not None:
                self.log.info("No shortcuts to relay for %r (%s)", name, unusable)
            else:
                wire = encode(harvest(name))
                self.log.info("Shortcuts for %r: %d to relay", name, len(wire))
        except Exception as e:
            self.log.debug("Shortcut harvest for %r failed: %s", name, e)
        finally:
            self._cache[name] = wire
            self._inflight.discard(name)
        if wire and self._on_ready is not None:
            try:
                self._on_ready(name)
            except Exception:
                # An escape reaches threading.excepthook, which this app routes
                # into crash_log.txt -- a failing observer would then put a
                # spurious crash in every later problem report.
                self.log.debug("shortcut relay ready callback failed",
                               exc_info=True)

    def _backend(self):
        """(unavailable_reason, harvest), imported late.

        ⚠️ Late because importing `shortcut_source` reaches for PyGObject /
        comtypes, and this module is also imported by the RECEIVER's network
        listener -- where the backend is irrelevant and a heavy import on the
        accept path is not wanted.
        """
        if self._harvest is not None:
            return (self._reason or (lambda: None)), self._harvest
        from polyhost.services import shortcut_source
        return shortcut_source.unavailable_reason, shortcut_source.harvest
