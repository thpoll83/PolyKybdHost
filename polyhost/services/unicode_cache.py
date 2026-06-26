import json
import os
import pathlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

import requests
from PyQt5.QtGui import QIcon, QImage
from platformdirs import user_config_dir


def _unicode_flag_to_codepoints(flag: str) -> str:
    return '-'.join([f"{ord(c) + 127397:x}" for c in flag.upper()])


class UnicodeCache:
    # Re-attempt a previously failed download only after this window, so a
    # transient outage doesn't permanently blacklist a flag, but a genuinely
    # missing / CDN-blocked one isn't retried on every launch.
    _RETRY_AFTER_S = 7 * 24 * 3600

    def __init__(self, size: int = 32):
        self.APP_NAME = "PolyHost"
        self.flag_dir = Path(os.path.join(pathlib.Path(__file__).parent.parent.resolve(), "res", "flags"))
        self.cache_dir = Path(os.path.join(user_config_dir(self.APP_NAME), "icon_cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.size = size
        # Reuse one keep-alive connection across flag downloads instead of a new
        # TLS handshake per icon.
        self._session = requests.Session()
        # Downloads run OFF the GUI thread so building the language menu never
        # blocks the UI. With the full bundled res/flags set this is rarely hit
        # at all — only for a flag added after this build. QImage (thread-safe)
        # is used for the decode/scale, never QPixmap (GUI-thread-only).
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="flagdl")
        self._lock = threading.Lock()
        # Serialises the negative-cache file writes; kept separate from _lock so
        # the disk I/O never happens while holding the scheduling lock.
        self._io_lock = threading.Lock()
        self._inflight: set[str] = set()
        self._futures: list = []
        # Negative cache {codepoints: last_attempt_epoch}, persisted to disk so an
        # offline / CDN-blocked machine doesn't re-attempt every missing flag on
        # every launch — that synchronous-per-session retry was what stalled the
        # first menu open for seconds.
        self._failed_path = self.cache_dir / "failed_downloads.json"
        self._failed = self._load_failed()

    def _load_failed(self) -> dict:
        try:
            with open(self._failed_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {str(k): float(v) for k, v in data.items()}
        except (OSError, ValueError):
            pass
        return {}

    def _persist_failed(self):
        # Snapshot under the scheduling lock, then write the file under the I/O
        # lock — so a slow/blocked disk can't stall icon scheduling.
        with self._lock:
            snapshot = dict(self._failed)
        with self._io_lock:
            try:
                with open(self._failed_path, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f)
            except OSError as e:
                print(f"[UnicodeCache] Could not persist failed-download cache: {e}")

    def _recently_failed(self, codepoints: str) -> bool:
        ts = self._failed.get(codepoints)
        return ts is not None and (time.time() - ts) < self._RETRY_AFTER_S

    def get_icon_for(self, flag: str) -> QIcon:
        """Return the flag icon for a 2-letter country code. Never blocks: a flag
        that is neither bundled nor already cached schedules a background
        download and returns an empty QIcon for now (it appears on the next
        language-menu rebuild). Runs on the GUI thread."""
        codepoints = _unicode_flag_to_codepoints(flag)
        bundled = self.flag_dir / f"{codepoints}.png"
        if bundled.exists():
            return QIcon(str(bundled))

        cached = self.cache_dir / f"{codepoints}.png"
        if cached.exists():
            return QIcon(str(cached))

        self._schedule_download(codepoints, cached)
        return QIcon()  # fills in on the next rebuild once the download lands

    def _schedule_download(self, codepoints: str, filename: Path):
        with self._lock:
            if codepoints in self._inflight or self._recently_failed(codepoints):
                return
            self._inflight.add(codepoints)
            self._futures.append(
                self._executor.submit(self._download_and_cache, codepoints, filename))

    def _download_and_cache(self, codepoints: str, filename: Path):
        url = f"https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/{codepoints}.png"
        try:
            # Always pass a timeout so a stalled CDN request can't pin a worker
            # thread (and, via flush(), app shutdown) indefinitely.
            response = self._session.get(url, timeout=10)
            response.raise_for_status()
            # QImage is thread-safe; QPixmap is GUI-thread-only and must not be
            # touched here. The menu reads the saved PNG back as a QIcon later.
            image = QImage()
            image.loadFromData(response.content)
            image = image.scaled(self.size, self.size)
            image.save(str(filename))
            with self._lock:
                cleared = self._failed.pop(codepoints, None) is not None
            if cleared:
                self._persist_failed()
            print(f"[UnicodeCache] Cached: {filename.name}")
        except (requests.RequestException, OSError) as e:
            # Only expected network/filesystem failures go into the negative
            # cache — anything else is a bug that should surface.
            with self._lock:
                self._failed[codepoints] = time.time()
            self._persist_failed()
            print(f"[UnicodeCache] Failed to fetch icon {codepoints}: {e}")
        finally:
            with self._lock:
                self._inflight.discard(codepoints)

    def flush(self, timeout: float = 30.0) -> bool:
        """Block until all scheduled downloads finish (best-effort, up to
        timeout). Returns True iff every pending download completed. For tests
        and a clean shutdown; never called on the menu-build path."""
        with self._lock:
            futures = list(self._futures)
            self._futures = []
        if not futures:
            return True
        _done, not_done = wait(futures, timeout=timeout)
        return not not_done

    def shutdown(self, wait: bool = False):
        """Stop the download executor. Best-effort (wait=False) by default so
        application teardown isn't blocked by an in-flight CDN request."""
        self._executor.shutdown(wait=wait)

    def __del__(self):
        # Don't let worker threads linger past teardown (best-effort; __init__
        # may not have created the executor if it raised).
        executor = getattr(self, "_executor", None)
        if executor is not None:
            try:
                executor.shutdown(wait=False)
            except Exception:  # noqa: BLE001 - teardown must never raise
                pass
