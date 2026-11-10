"""Put one page of agents on the keyboard's number row (HID cmd 45/46, v30+).

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
# Card indices after the 10 number keys (firmware AI_CARD_MINUS / AI_CARD_PLUS).
CARD_DICTATION = 10
CARD_NEXT_WAITING = 11
# Cmd 45 op 1 flags (firmware AI_FLAG_*).
FLAG_ESC_ATTENTION = 0x01
FLAG_MORE_PAGES = 0x02
FLAG_ANY_WAITING = 0x04
FLAG_EXTRA_CARDS = 0x08


class AgentKeysController:
    def __init__(self, registry, card_slots, raise_agent=None, log=None, marks=None,
                 dictate=None):
        """`card_slots`: the 12 pool slots reserved for the cards: one per number
        key, then '-' and '+'. `raise_agent(agent)` brings an agent's window forward
        and `dictate()` starts dictation; both run on their own thread, never on the
        HID worker."""
        self.registry = registry
        self.card_slots = list(card_slots)
        if len(self.card_slots) != NUMBER_KEYS + 2:
            raise ValueError("need 12 card slots: 10 number keys, '-' and '+'")
        self.raise_agent = raise_agent
        self.dictate = dictate
        self._last_waiting_slot = None   # the agent '+' raised last
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
            self._cards = [None] * len(self.card_slots)
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
        states, slots = [], []
        for i, agent in enumerate(view[:NUMBER_KEYS]):
            if cancel is not None and cancel.is_set():
                return
            if agent is None:
                states.append(AgentState.EMPTY)
                slots.append(NO_SLOT)
                continue
            states.append(agent.state)
            slots.append(self.card_slots[i])
            card_key = (agent.vendor, agent.state, agent.display_headline, self.marks.version)
            if self._cards[i] != card_key:
                data = card_bytes(render_card(agent.vendor, agent.state,
                                              agent.display_headline, self.marks))
                ok, msg = keeb.ai_upload_card(self.card_slots[i], data)
                if not ok:
                    self.log.debug("Agent card %d not uploaded: %s", i, msg)
                    self._cards[i] = None
                    continue
                self._cards[i] = card_key
        waiting = len(self.registry.waiting())
        extra_ok = True
        for card, key in ((CARD_DICTATION, ("dictation",)),
                          (CARD_NEXT_WAITING, ("next", waiting))):
            if self._cards[card] != key:
                image = (render_dictation_card() if card == CARD_DICTATION
                         else render_next_waiting_card(waiting))
                ok, msg = keeb.ai_upload_card(self.card_slots[card], card_bytes(image))
                self._cards[card] = key if ok else None
                extra_ok = extra_ok and ok
                if not ok:
                    self.log.debug("Agent card %d not uploaded: %s", card, msg)
        slots += [self.card_slots[CARD_DICTATION], self.card_slots[CARD_NEXT_WAITING]]
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

    def _handle_key(self, key: int):
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
                return
            self._last_waiting_slot = agent.slot
            with self._lock:
                self.page = agent.slot // self.registry.page_size   # show where it is
            self.log.info("Agent keys: '+' raises %s %s", agent.vendor, agent.display_headline)
            if self.raise_agent is not None:
                threading.Thread(target=self._raise, args=(agent,), name="agent-raise",
                                 daemon=True).start()
            return
        view = self.registry.page(self.page)
        agent = view[key] if 0 <= key < len(view) else None
        if agent is None:
            return
        self.registry.mark_seen(agent.vendor, agent.session_id)
        self.log.info("Agent keys: key %d raises %s %s", key + 1, agent.vendor,
                      agent.display_headline)
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

    def _raise(self, agent):
        try:
            ok = self.raise_agent(agent)
            if not ok:
                self.log.info("Agent keys: no window found for %s %s",
                              agent.vendor, agent.display_headline)
        except Exception as e:  # noqa: BLE001 - a failed raise must not kill anything
            self.log.info("Agent keys: raising %s failed: %s", agent.vendor, e)
