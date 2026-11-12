"""The agent registry across host restarts.

A hook reports only on an agent's events, so an agent that waits or sits idle
sends nothing until its next one. Without this file a restarted host showed no
agents at all until each of them reported again. `AgentStore` writes the
hook-reported agents to `agents.json` in the config folder when something
changed, and puts them back at start (AgentRegistry.export / restore).

The file holds what `polyctl agents list` shows (vendor, session id, state,
title, folder, process id, computer name), never a prompt or a transcript.
"""
import json
import logging
import os
import threading
import time

FILE_NAME = "agents.json"
FORMAT = 1


class AgentStore:
    def __init__(self, registry, path, log=None, wall_clock=time.time):
        self._registry = registry
        self._path = path
        self._log = log or logging.getLogger(__name__)
        self._wall = wall_clock
        self._saved = None          # (version, edits) at the last save
        self._lock = threading.Lock()   # the periodic save and the shutdown save

    def load(self) -> int:
        """Restore the agents of the last run. A missing or broken file restores
        nothing. Returns how many agents came back."""
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return 0
        except (OSError, ValueError) as e:
            self._log.warning("Agents: could not read %s: %s", self._path, e)
            return 0
        if not isinstance(data, dict) or data.get("format") != FORMAT:
            return 0
        try:
            offline = self._wall() - float(data.get("saved_at", 0))
            restored = self._registry.restore(data, offline)
        except Exception as e:      # an optional cache must never stop the start
            self._log.warning("Agents: could not restore %s: %s", self._path, e)
            return 0
        with self._lock:
            self._saved = self._mark()
        return restored

    def save_if_changed(self) -> bool:
        """Write the file when the registry changed since the last write. Never
        raises. Returns whether it wrote."""
        with self._lock:
            return self._save_locked()

    def _save_locked(self) -> bool:
        mark = self._mark()
        if mark == self._saved:
            return False
        data = self._registry.export()
        data["format"] = FORMAT
        data["saved_at"] = self._wall()
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self._path)
        except OSError as e:
            self._log.warning("Agents: could not write %s: %s", self._path, e)
            return False
        self._saved = mark
        return True

    def _mark(self):
        return (self._registry.version, self._registry.edits)
