"""OverlayMRUCache.allocate_aside: pool slots for images no switch maps (the agent
cards). Nothing is reserved; a switch evicts them first; they never evict the
images of the newest switch, which are on the keys."""
import unittest

from polyhost.device.overlay_cache import ASIDE_BATCH, OverlayMRUCache


class AllocateAsideTest(unittest.TestCase):
    def _switch(self, cache, name, n):
        with cache.batch():
            return [cache.get_or_allocate((name, 0, k))[0] for k in range(n)]

    def test_free_slot_and_hit(self):
        cache = OverlayMRUCache(10)
        slot = cache.allocate_aside(("agentcard", 0))
        self.assertEqual(slot, 0)
        self.assertEqual(cache.allocate_aside(("agentcard", 0)), 0)   # held
        self.assertEqual(cache.holds(("agentcard", 0)), 0)
        self.assertIsNone(cache.holds(("agentcard", 1)))

    def test_a_switch_evicts_an_aside_entry_first(self):
        cache = OverlayMRUCache(4)
        self._switch(cache, "old.png", 2)
        aside = cache.allocate_aside(("agentcard", 0))
        self._switch(cache, "mid.png", 1)
        # Full. The next switch needs one slot: the card goes before old.png.
        self._switch(cache, "new.png", 1)
        self.assertIsNone(cache.holds(("agentcard", 0)))
        self.assertEqual(cache.holds(("new.png", 0, 0)), aside)
        self.assertIsNotNone(cache.holds(("old.png", 0, 0)))

    def test_never_evicts_the_newest_switch_or_another_card(self):
        cache = OverlayMRUCache(3)
        self._switch(cache, "old.png", 1)
        self._switch(cache, "shown.png", 1)
        first = cache.allocate_aside(("agentcard", 0))
        self.assertEqual(first, 2)
        # Full: the next card may take only old.png's slot.
        second = cache.allocate_aside(("agentcard", 1))
        self.assertEqual(second, cache.holds(("agentcard", 1)))
        self.assertIsNone(cache.holds(("old.png", 0, 0)))
        self.assertIsNotNone(cache.holds(("shown.png", 0, 0)))
        # Now only the shown switch and cards are left: nothing to take.
        self.assertIsNone(cache.allocate_aside(("agentcard", 2)))
        self.assertIsNotNone(cache.holds(("shown.png", 0, 0)))
        self.assertEqual(cache.holds(("agentcard", 0)), first)

    def test_aside_entries_are_older_than_any_switch(self):
        cache = OverlayMRUCache(5)
        slot = cache.allocate_aside(("agentcard", 0))
        self.assertEqual(cache._slot_batch[slot], ASIDE_BATCH)


if __name__ == "__main__":
    unittest.main()
