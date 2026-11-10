"""Put one page of agents on the keyboard's number row (HID cmd 45/46, v31+).

Runs on the HID worker thread (PolyCore's "agents" periodic). Pushes only what
changed: a card is uploaded when its (vendor, state, headline, mark) changes, and
the key states when any of them change. A reconnect forgets what the keyboard
holds (`forget_device()`), since the firmware keeps this state in RAM only.

Key presses come back as events: the firmware writes them to a ring, bumps the
GET_ID `G` counter and prints `ai ev <seq> <key>` on the console. Either signal
makes the next pass read the ring (cmd 45 op 2).
"""
from __future__ import annotations

import logging
import threading

from polyhost.services.agents.card import (VendorMarks, card_bytes, render_card,
                                           render_dictation_card, render_next_waiting_card)
from polyhost.services.agents.model import AgentState

PAGER_KEY = 10
DICTATION_KEY = 11     # '-'
NEXT_WAITING_KEY = 12  # '+'
NO_SLOT = 0xFFFF
NUMBER_KEYS = 10
CARD_COUNT = NUMBER_KEYS + 2
# Card indices after the 10 number keys (firmware AI_CARD_MINUS / AI_CARD_PLUS).
CARD_DICTATION = 10
CARD_NEXT_WAITING = 11
# Cmd 45 op 1 flags (firmware AI_FLAG_*).
FLAG_ESC_ATTENTION = 0x01
FLAG_MORE_PAGES = 0x02
FLAG_ANY_WAITING = 0x04
FLAG_EXTRA_CARDS = 0x08


class AgentKeysController:
    def __init__(self, registry, cache_for, raise_agent=None, log=None, marks=None,
                 dictate=None):
        """`cache_for()` returns the keyboard's overlay MRU cache (it is replaced at
        every connect). The cards take pool slots from it as "aside" entries, so no
        slot is reserved: a program switch evicts a card before any app image, and
        the next pass here uploads the card again into a new slot.
        `raise_agent(agent)` brings an agent's window forward and `dictate()` starts
        dictation; both run on their own thread, never on the HID worker."""
        self.registry = registry
        self.cache_for = cache_for
        self.raise_agent = raise_agent
        self.raise_remote = None   # set by PolyCore: queue a raise for a forwarder
        self.raise_viewer = None   # set by PolyCore: raise the viewer showing a machine
        self.dictate = dictate
        self._last_waiting_slot = None   # the agent '+' raised last
        # The last AI-key press and what came of it, for `polyctl agents list`: a
        # press that "does nothing" is then one of: never read, no agent on the key,
        # no window found, or the OS refused the focus.
        self.last_press = None
        self.log = log or logging.getLogger("PolyHost")
        self.marks = marks or VendorMarks()
        self.page = 0
        self._lock = threading.Lock()
        self._read_events = False
        self.forget_device()

    # ---- signals ----------------------------------------------------------------

    def forget_device(self):
        """The keyboard lost or never had our state (connect, reboot)."""
        with self._lock:
            self._pushed_keys = None
            self._cards = [None] * CARD_COUNT   # (what is drawn, pool slot) per card
            self._last_seq = None          # None: take the keyboard's newest as the start
            self._last_gen = None
            self._read_events = True
            self._console_tail = ""

    def note_console(self, text: str):
        """A console read. The line can arrive split over two reads, so the tail of
        the previous read is kept and searched together with this one."""
        if not text:
            return
        with self._lock:
            joined = self._console_tail + text
            self._console_tail = joined[-8:]
            if "ai ev" in joined:
                self._read_events = True

    def note_state_generation(self, generation):
        with self._lock:
            if generation is not None and generation != self._last_gen:
                self._last_gen = generation
                self._read_events = True

    def next_page(self):
        with self._lock:
            pages = self.registry.page_count()
            self.page = (self.page + 1) % max(1, pages)

    # ---- the worker pass ---------------------------------------------------------

    def sync(self, keeb, cancel=None, poll_events: bool = True):
        """One pass: read events, then push the shown page.

        ⚠️ `poll_events` reads the ring on EVERY pass (one report per second). The
        console line and the G counter only speed it up: in steady state the host's
        probe sends GET_LANG, not GET_ID, so G is not refreshed, and the console line
        can be lost (first hardware test, 2026-11-10: presses did nothing)."""
        with self._lock:
            read = self._read_events or poll_events
            self._read_events = False
        if read:
            self._poll_events(keeb)
        self.registry.tick()
        with self._lock:
            self.page = min(self.page, self.registry.page_count() - 1)
            page = self.page
        view = self.registry.page(page)
        cache = self.cache_for()
        states, slots = [], []
        for i, agent in enumerate(view[:NUMBER_KEYS]):
            if cancel is not None and cancel.is_set():
                return
            if agent is None:
                states.append(AgentState.EMPTY)
                slots.append(NO_SLOT)
                continue
            states.append(agent.state)
            drawn = (agent.vendor, agent.state, agent.display_headline, self.marks.version)
            slots.append(self._card(keeb, cache, i, drawn,
                                    lambda a=agent: render_card(a.vendor, a.state,
                                                                a.display_headline,
                                                                self.marks)))
        waiting = len(self.registry.waiting())
        extra = [self._card(keeb, cache, CARD_DICTATION, ("dictation",), render_dictation_card),
                 self._card(keeb, cache, CARD_NEXT_WAITING, ("next", waiting),
                            lambda: render_next_waiting_card(waiting))]
        slots += extra
        extra_ok = NO_SLOT not in extra
        flags = 0
        if self.registry.waiting_elsewhere(page):
            flags |= FLAG_ESC_ATTENTION
        if self.registry.page_count() > 1:
            flags |= FLAG_MORE_PAGES
        if waiting:
            flags |= FLAG_ANY_WAITING
        if extra_ok:
            flags |= FLAG_EXTRA_CARDS
        keys = (tuple(int(s) for s in states), flags, tuple(slots))
        if keys != self._pushed_keys:
            ok, msg = keeb.ai_set_keys(list(keys[0]), keys[1], list(keys[2]))
            if ok:
                self._pushed_keys = keys     # only what the keyboard confirmed
            else:
                self.log.debug("Agent keys not pushed: %s", msg)

    def _card(self, keeb, cache, index, drawn, render) -> int:
        """The pool slot of card `index` showing `drawn`, uploading it when the slot
        is new or the picture changed; NO_SLOT when the pool has no room for it."""
        if cache is None:
            return NO_SLOT
        key = ("agentcard", index)
        slot = cache.holds(key)
        if slot is None:
            slot = cache.allocate_aside(key)
            if slot is None:
                self._cards[index] = None
                return NO_SLOT
        if self._cards[index] == (drawn, slot):
            return slot
        cache.mark_written(slot)     # an app image reusing it later must clear it
        ok, msg = keeb.ai_upload_card(slot, card_bytes(render()))
        if not ok:
            self.log.debug("Agent card %d not uploaded: %s", index, msg)
            self._cards[index] = None
            return NO_SLOT
        self._cards[index] = (drawn, slot)
        return slot

    def _poll_events(self, keeb):
        start = self._last_seq
        ok, payload = keeb.ai_read_events(start or 0)
        if not ok:
            with self._lock:
                self._read_events = True     # try again next pass
            return
        newest, events = payload
        if start is None:
            # First read after a connect: presses from before we were listening
            # are not acted on.
            self._last_seq = newest
            return
        self._last_seq = newest
        for _seq, key in events:
            self._handle_key(key)

    def _note(self, key, result, agent=None):
        import time
        self.last_press = {"at": time.time(), "key": key, "result": result,
                           "agent": (f"{agent.vendor} {agent.display_headline}"
                                     if agent is not None else "")}

    def _handle_key(self, key: int):
        self._note(key, "read")
        if key == PAGER_KEY:
            self.next_page()
            self.log.info("Agent keys: page %d", self.page + 1)
            return
        if key == DICTATION_KEY:
            self.log.info("Agent keys: dictation")
            if self.dictate is not None:
                threading.Thread(target=self._run_dictate, name="agent-dictate",
                                 daemon=True).start()
            return
        if key == NEXT_WAITING_KEY:
            agent = self.registry.next_waiting(self._last_waiting_slot)
            if agent is None:
                self.log.info("Agent keys: no agent waits")
                self._note(key, "no agent waits")
                return
            self._last_waiting_slot = agent.slot
            with self._lock:
                self.page = agent.slot // self.registry.page_size   # show where it is
            self.log.info("Agent keys: '+' raises %s %s", agent.vendor, agent.display_headline)
            self.raise_now(agent)
            return
        view = self.registry.page(self.page)
        agent = view[key] if 0 <= key < len(view) else None
        if agent is None:
            self._note(key, "no agent on this key")
            return
        self.registry.mark_seen(agent.vendor, agent.session_id)
        self.log.info("Agent keys: key %d raises %s %s", key + 1, agent.vendor,
                      agent.display_headline)
        self.raise_now(agent)

    def raise_now(self, agent):
        """Raise `agent`: here on its own thread, or, for an agent on a forwarder's
        machine, by handing it to `raise_remote(agent)`, which the forwarder picks
        up with its next window report (PolyCore.report_window)."""
        if agent.machine and agent.machine != "local":
            # The forwarder raises the agent's own window only when its
            # `agents_raise_here` is on; here the viewer that shows that
            # computer comes forward (services/agents/viewer.py).
            if self.raise_remote is not None:
                self.raise_remote(agent)
            if self.raise_viewer is not None:
                threading.Thread(target=self._raise_viewer, args=(agent,),
                                 name="agent-raise-viewer", daemon=True).start()
            else:
                self._note(self.last_press["key"] if self.last_press else None,
                           f"sent to {agent.machine}", agent)
            return
        if self.raise_agent is not None:
            threading.Thread(target=self._raise, args=(agent,), name="agent-raise",
                             daemon=True).start()

    def _run_dictate(self):
        try:
            if not self.dictate():
                self.log.info("Agent keys: no dictation shortcut for this system "
                              "(setting agents_dictation_shortcut)")
        except Exception as e:  # noqa: BLE001 - must not kill anything
            self.log.info("Agent keys: dictation failed: %s", e)

    def _raise_viewer(self, agent):
        key = self.last_press["key"] if self.last_press else None
        try:
            result = self.raise_viewer(agent.machine)
            if result is True:
                result = f"sent to {agent.machine}; its viewer raised"
            elif not result:
                result = f"sent to {agent.machine}; no viewer window for it found"
            self.log.info("Agent keys: %s %s: %s", agent.vendor, agent.display_headline,
                          result)
            self._note(key, str(result), agent)
        except Exception as e:  # noqa: BLE001 - a failed raise must not kill anything
            self.log.info("Agent keys: raising the viewer for %s failed: %s",
                          agent.machine, e)
            self._note(key, f"sent to {agent.machine}; viewer failed: {e}", agent)

    def _raise(self, agent):
        key = self.last_press["key"] if self.last_press else None
        try:
            result = self.raise_agent(agent)
            if result is True:
                result = "raised"
            elif not result:
                result = "no window found"
            self.log.info("Agent keys: %s %s: %s", agent.vendor, agent.display_headline, result)
            self._note(key, str(result), agent)
        except Exception as e:  # noqa: BLE001 - a failed raise must not kill anything
            self.log.info("Agent keys: raising %s failed: %s", agent.vendor, e)
            self._note(key, f"failed: {e}", agent)
