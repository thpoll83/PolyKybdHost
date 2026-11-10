from dataclasses import dataclass, field
from typing import Any

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.overlay_cache import OverlayMRUCache


@dataclass
class DeviceEntry:
    device: Any               # PolyKybd | PolyKybdMock
    name: str
    is_primary: bool
    cache: OverlayMRUCache | None = field(default=None)


class DeviceManager:
    """
    Owns the list of connected keyboard devices (primary + optional secondaries).
    Primary is the real keyboard: drives connection state and all GUI commands.
    Secondaries (e.g. mock) receive overlay broadcasts but no GUI commands.
    """

    def __init__(self, settings: DeviceSettings) -> None:
        self._entries: list[DeviceEntry] = []
        self.device_settings = settings
        # Pool slots at the top of the pool the MRU cache must not use (the agent
        # cards, services/agents). Applied when a cache is created, i.e. at the
        # next connect, because the keyboard's mapping may still point there.
        self.reserved_tail_slots = 0

    def _new_cache(self) -> OverlayMRUCache:
        return OverlayMRUCache(self.device_settings.OVERLAY_MAPPING_CAPACITY
                               - self.reserved_tail_slots)

    def cache_capacity(self) -> int:
        """The capacity the caches have now (0 when there is no entry)."""
        p = self.primary
        return p.cache.capacity if p and p.cache is not None else 0

    def add(self, device: Any, name: str, *, is_primary: bool = False) -> None:
        # The cache is created up front, not lazily on the first reconnect: overlay
        # sends are MRU-only now (the firmware's identity mapping no longer spans
        # the whole flat index space), so an entry without a cache could not send
        # overlays at all.
        self._entries.append(DeviceEntry(
            device=device, name=name, is_primary=is_primary,
            cache=self._new_cache()))

    @property
    def primary(self) -> DeviceEntry | None:
        return next((e for e in self._entries if e.is_primary), None)

    @property
    def all_entries(self) -> list[DeviceEntry]:
        return list(self._entries)

    def connect_primary(self) -> bool:
        p = self.primary
        return p.device.connect() if p else False

    def connect_secondaries(self) -> None:
        for e in self._entries:
            if not e.is_primary:
                e.device.connect()

    def reset_all_caches(self) -> None:
        """Reset MRU caches for all devices — called on primary reconnect since
        a power-cycle means the firmware's overlay pool is gone on every device."""
        for e in self._entries:
            e.cache = self._new_cache()
