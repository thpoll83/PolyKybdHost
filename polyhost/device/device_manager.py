from dataclasses import dataclass, field
from typing import Any

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

    def __init__(self) -> None:
        self._entries: list[DeviceEntry] = []

    def add(self, device: Any, name: str, *, is_primary: bool = False) -> None:
        self._entries.append(DeviceEntry(device=device, name=name, is_primary=is_primary))

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

    def reset_all_caches(self, capacity: int) -> None:
        """Reset MRU caches for all devices — called on primary reconnect since
        a power-cycle means the firmware's overlay pool is gone on every device."""
        for e in self._entries:
            e.cache = OverlayMRUCache(capacity)
