"""Reassemble the keyboard console stream into whole lines.

⚠️ A console read is a REPORT-SIZED FRAGMENT, not a line: one 250 ms read can end
mid-line and the rest arrives with the next. Anything that classifies console
output must buffer across reads and only look at ``\\n``-terminated lines. Two
scanners need that (crash records and the problem scan), so it lives here once
rather than as two hand-kept copies.
"""
from __future__ import annotations


class LineAssembler:
    """Feed fragments in, get the lines they completed out."""

    MAX_PENDING = 4096   # a fragment that never terminates must not grow forever

    def __init__(self):
        self._pending = ""

    def feed(self, chunk: str) -> list[str]:
        if not chunk:
            return []
        buf = self._pending + chunk
        parts = buf.split("\n")
        self._pending = parts.pop()
        if len(self._pending) > self.MAX_PENDING:
            self._pending = self._pending[-self.MAX_PENDING:]
        return parts
