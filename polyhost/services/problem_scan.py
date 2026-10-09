"""Spot problems in the keyboard's console and the host's own log, and say so.

A failure that only ever reaches a log file is a failure nobody reports: the
status OLED's ``oled_render offset command failed`` (an I2C write that did not
land) turned up once in a rig probe and nowhere else. This module turns such lines
into a ``problem_detected`` event; the tray raises one dialog per session that
offers the guided *Report a Problem*. Nothing is ever sent by itself.

Two sources, each behind its own setting:

* **The keyboard console.** Firmware lines carry NO severity, and words like
  "fail" also appear in healthy output (the split-link stats line prints
  ``transport_fail=0 giveup=0`` every few seconds), so matching is a CURATED list,
  :data:`CONSOLE_PATTERNS`, each entry with its own severity and a sentence a
  user can read. A new firmware message needs a new entry here, not a firmware
  change.
* **The host's own logging.** :class:`HostLogProblemHandler` is a ``logging``
  handler on the root logger that passes on WARNING and ERROR records.

``problem_scan_level`` picks what counts: ``"errors"`` (the default) or
``"errors_and_warnings"``. Each problem is NEW once per process and source key;
repeats raise its count, because the boot banner and a stuck condition both
repeat a line for as long as they last. A raised count is re-sent as an UPDATE of
the same problem at most once per :data:`UPDATE_INTERVAL_S`, so the dialog and
the report follow it without a stuck line flooding the event stream. The count
they show can therefore lag by the repeats of the last interval.

Qt-free: the console scanner runs on the HID worker thread inside PolyCore, and the
handler on whatever thread logged.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from polyhost.services.console_lines import LineAssembler

LEVEL_ERRORS = "errors"
LEVEL_ERRORS_AND_WARNINGS = "errors_and_warnings"
LEVELS = (LEVEL_ERRORS, LEVEL_ERRORS_AND_WARNINGS)

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

SOURCE_KEYBOARD = "keyboard"
SOURCE_HOST = "host"

MAX_LINE = 300   # a payload carries one line, not a traceback
UPDATE_INTERVAL_S = 10.0   # min gap between two count updates of one problem


def severity_wanted(severity: str, level: str) -> bool:
    """Does ``level`` (a ``problem_scan_level`` value) include ``severity``?"""
    if severity == SEVERITY_ERROR:
        return True
    return severity == SEVERITY_WARNING and level == LEVEL_ERRORS_AND_WARNINGS


@dataclass(frozen=True)
class ConsolePattern:
    """One known-bad console line.

    ``escalate_after`` > 0 makes a WARNING pattern an ERROR once it matches that
    many times within ``escalate_window_s`` seconds, with ``escalated_summary`` as
    its sentence. That is for a line where one occurrence is a glitch the board
    recovers from and a burst is a fault.

    A regex with a named ``instance`` group counts each distinct value of that group
    ONCE: a line repeating an instance already seen neither raises the count nor
    publishes again. That is for a firmware line printed more than once for the same
    event, so a reader that missed the first copy still gets one."""
    id: str
    regex: re.Pattern
    severity: str
    summary: str
    escalate_after: int = 0
    escalate_window_s: float = 0.0
    escalated_summary: str = ""


def _p(pid, regex, severity, summary, escalate_after=0, escalate_window_s=0.0,
       escalated_summary=""):
    return ConsolePattern(pid, re.compile(regex), severity, summary,
                          escalate_after, escalate_window_s, escalated_summary)


# ⚠️ Match the firmware's own wording, and keep each pattern narrow: a broad one
# fires on healthy boards and teaches people to dismiss the dialog. Crash
# records (`crash: side=…`) are NOT here; services/crash_report.py owns them.
CONSOLE_PATTERNS: tuple[ConsolePattern, ...] = (
    # The status OLED. One failed write costs one frame and the next frame
    # repaints it (field report 2026-10-02: one failure in ~7300 idle frames), so a
    # single one is a warning and only a burst is an error. `oled_render … failed`
    # is stock QMK's line; firmware with keyboards/polykybd/oled_i2c.c retries
    # the write first, so there it means the retry failed too, and adds its own
    # `oled_i2c:` lines (wording in base/oled_i2c_diag.c).
    _p("oled_i2c", r"oled_render(90)? (offset command|data) failed", SEVERITY_WARNING,
       "The status display missed one update (I2C write failed).",
       escalate_after=3, escalate_window_s=60.0,
       escalated_summary="The status display keeps rejecting updates (repeated I2C write failures)."),
    _p("oled_i2c_retried", r"oled_i2c: \w+ write failed #\d+ .* - retry ok", SEVERITY_WARNING,
       "The status display rejected an update; the keyboard's retry landed.",
       escalate_after=10, escalate_window_s=60.0,
       escalated_summary="The status display keeps rejecting updates (the keyboard's retries land)."),
    _p("oled_i2c_stuck", r"oled_i2c: status display not responding", SEVERITY_ERROR,
       "The status display stopped responding (I2C writes fail even after a retry)."),
    # Not the `slave status (begin-pending)` snapshot: hid_fw_up.c prints it
    # every ~4 s while the slave is still erasing staging flash at the start of
    # a firmware update. A status read can miss mid-erase, the BEGIN poll goes
    # on, and the update completes (field report 2026-10-05).
    _p("slave_unresponsive", r"^(?!.*slave status \(begin-pending\)).*RPC FAILED .* slave unresponsive",
       SEVERITY_ERROR,
       "The second keyboard half stopped answering over the split link."),
    _p("slave_refused", r"slave REFUSED \(ack=", SEVERITY_ERROR,
       "The second keyboard half rejected data sent to it."),
    _p("slave_status_probe", r"the status probe failed too", SEVERITY_ERROR,
       "The second keyboard half did not answer a status check."),
    _p("fw_staging_write", r"master staging write FAILED", SEVERITY_ERROR,
       "Writing a firmware update to the keyboard's flash failed."),
    _p("fw_staging_offset", r"fw_staging_write_chunk: offset mismatch", SEVERITY_ERROR,
       "A firmware update arrived out of order."),
    _p("fw_apply_refused", r"FWAPPLY refused|APPLY: refusing to overwrite firmware",
       SEVERITY_ERROR, "The keyboard refused to install a staged firmware update."),
    _p("core1_relaunch", r"core1 relaunch timed out", SEVERITY_ERROR,
       "The keyboard's second processor core did not restart; keycap images "
       "may stop updating until the keyboard is unplugged."),
    # multicore_exec.c's stall recovery: core1 owed a decoded keycap image for
    # 500 ms and was reset. Before that recovery existed the same stall shut the
    # keyboard's command channel until a replug (field report 2026-10-09), so even
    # a successful relaunch is a fault worth a report: one keycap image was lost.
    # The firmware prints each recovery up to three times; the ID it repeats,
    # "recovery <n> since boot at <uptime> ms", makes the copies count once.
    _p("core1_stall_failed",
       r"WARNING core1 stalled: .*core1 relaunch FAILED.*\(recovery (?P<instance>\d+ since boot at \d+) ms",
       SEVERITY_ERROR,
       "The keyboard's second processor core stopped and did not restart; keycap "
       "images may stop updating until the keyboard is unplugged."),
    _p("core1_stall",
       r"WARNING core1 stalled: .*core1 relaunched \(recovery (?P<instance>\d+ since boot at \d+) ms",
       SEVERITY_ERROR,
       "The keyboard's second processor core stopped and was restarted; one keycap "
       "image may look wrong until the next app switch."),
    _p("split_link_giveup", r"Split link: .*giveup=[1-9]", SEVERITY_WARNING,
       "Messages between the keyboard halves were lost after retries."),
    _p("eden_core1_timeout", r"Eden idle: core1 job for key \d+ timed out", SEVERITY_WARNING,
       "The idle animation fell back to the main processor core."),
    _p("tutorial_sync", r"Tutorial sync to slave failed", SEVERITY_WARNING,
       "The first-run tutorial could not reach the second keyboard half."),
    _p("overlay_side", r"Could not locate side for keycode", SEVERITY_WARNING,
       "A keycap image was sent for a key the keyboard could not place."),
)


@dataclass
class Problem:
    """One distinct problem, as reported in the event payload."""
    source: str          # SOURCE_KEYBOARD or SOURCE_HOST
    key: str             # dedupe key: pattern id, or logger + message template
    severity: str
    summary: str
    line: str
    count: int = 1
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"source": self.source, "key": self.key, "severity": self.severity,
                "summary": self.summary, "line": self.line, "count": self.count,
                **self.extra}

    @classmethod
    def from_dict(cls, d: dict) -> "Problem":
        known = {"source", "key", "severity", "summary", "line", "count"}
        return cls(source=str(d.get("source", "")), key=str(d.get("key", "")),
                   severity=str(d.get("severity", SEVERITY_ERROR)),
                   summary=str(d.get("summary", "")), line=str(d.get("line", "")),
                   count=int(d.get("count", 1) or 1),
                   extra={k: v for k, v in d.items() if k not in known})


def _clip(text: str) -> str:
    text = (text or "").strip()
    return text if len(text) <= MAX_LINE else text[:MAX_LINE - 1] + "…"


class ConsoleProblemScanner:
    """Reassemble console fragments and match whole lines against the patterns.

    ``feed`` returns the problems to publish: those seen for the FIRST time, and
    known ones whose count rose and whose last publish is at least
    ``update_interval`` seconds old. Serialize them before the next ``feed``,
    which may raise the count again."""

    def __init__(self, patterns=CONSOLE_PATTERNS, update_interval=UPDATE_INTERVAL_S,
                 clock=time.monotonic):
        self._patterns = tuple(patterns)
        self._lines = LineAssembler()
        self._seen: dict[str, Problem] = {}
        self._update_interval = update_interval
        self._clock = clock
        self._sent: dict[str, tuple[int, float]] = {}   # id -> (count, when) last published
        self._totals: dict[str, int] = {}                # id -> matches, at any level
        self._hits: dict[str, deque] = {}                # id -> match times, escalating patterns only
        self._instances: dict[str, set] = {}             # id -> instance values counted

    def feed(self, chunk: str, level: str = LEVEL_ERRORS) -> list[Problem]:
        out: dict[str, Problem] = {}
        now = self._clock()
        for line in self._lines.feed(chunk):
            for pat in self._patterns:
                m = pat.regex.search(line)
                if not m:
                    continue
                instance = m.groupdict().get("instance")
                if instance is not None:
                    seen = self._instances.setdefault(pat.id, set())
                    if instance in seen:
                        break   # a repeat of an event already counted
                    seen.add(instance)
                self._totals[pat.id] = self._totals.get(pat.id, 0) + 1
                severity, summary = self._severity_for(pat, now)
                prior = self._seen.get(pat.id)
                if prior is not None:
                    prior.count += 1
                    if severity == SEVERITY_ERROR and prior.severity != SEVERITY_ERROR:
                        # Escalated: publish at once, whatever the interval says.
                        prior.severity, prior.summary = severity, summary
                        prior.line = _clip(line)
                        out[pat.id] = prior
                        break
                    sent_count, sent_at = self._sent.get(pat.id, (0, now))
                    # Counted at any level, re-sent only at the CURRENT one: a
                    # warning first seen under errors_and_warnings goes quiet
                    # once the user narrows the level to errors.
                    if (severity_wanted(prior.severity, level)
                            and pat.id not in out and prior.count != sent_count
                            and now - sent_at >= self._update_interval):
                        out[pat.id] = prior
                elif severity_wanted(severity, level):
                    # Counted from the first match, including the warnings the
                    # current level did not publish.
                    prob = Problem(SOURCE_KEYBOARD, pat.id, severity, summary,
                                   _clip(line), count=self._totals[pat.id])
                    self._seen[pat.id] = prob
                    out[pat.id] = prob
                break   # one line, one problem
        for pid, prob in out.items():
            self._sent[pid] = (prob.count, now)
        return list(out.values())

    def problems(self) -> list[Problem]:
        return list(self._seen.values())

    def _severity_for(self, pat: ConsolePattern, now: float) -> tuple[str, str]:
        """Record a match of ``pat`` at ``now``; (severity, summary) it counts as."""
        if pat.escalate_after <= 0:
            return pat.severity, pat.summary
        hits = self._hits.setdefault(pat.id, deque())
        hits.append(now)
        while hits and now - hits[0] > pat.escalate_window_s:
            hits.popleft()
        if len(hits) >= pat.escalate_after:
            return SEVERITY_ERROR, pat.escalated_summary or pat.summary
        return pat.severity, pat.summary


class HostLogProblemHandler(logging.Handler):
    """Pass the host's own WARNING/ERROR records to ``on_problem``, once each.

    ``level_cb`` returns the current ``problem_scan_level`` and ``enabled_cb``
    the ``problem_scan_host_logs`` switch; both are read per record, so a settings
    change takes effect without reinstalling the handler. Records are grouped by
    logger and UNFORMATTED message, so one call site logging the same thing with
    different values is one problem. A repeat re-sends that problem with its
    raised count at most once per ``update_interval`` seconds.

    ⚠️ ``on_problem`` usually emits an event, and an event observer that fails is
    logged at ERROR, which would land back here. A per-thread guard drops every
    record logged while the callback runs, so the handler can never feed itself.
    """

    # Loggers whose records are not problems in themselves: the console chunks
    # are relayed text (the console scanner owns them).
    IGNORED_LOGGERS = frozenset({"PolyKybdConsole"})

    def __init__(self, on_problem, level_cb=lambda: LEVEL_ERRORS,
                 enabled_cb=lambda: True, origin="",
                 update_interval=UPDATE_INTERVAL_S, clock=time.monotonic):
        super().__init__(level=logging.WARNING)
        self._update_interval = update_interval
        self._clock = clock
        self._sent_at: dict[str, float] = {}
        self._on_problem = on_problem
        self._level_cb = level_cb
        self._enabled_cb = enabled_cb
        self._origin = origin
        self._seen: dict[str, Problem] = {}
        self._seen_lock = threading.Lock()
        self._busy = threading.local()

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(self._busy, "on", False) or record.name in self.IGNORED_LOGGERS:
            return
        self._busy.on = True
        try:
            if not self._enabled_cb():
                return
            severity = SEVERITY_ERROR if record.levelno >= logging.ERROR else SEVERITY_WARNING
            if not severity_wanted(severity, self._level_cb()):
                return
            key = f"{record.name}:{record.msg}"
            now = self._clock()
            with self._seen_lock:
                prior = self._seen.get(key)
                if prior is not None:
                    prior.count += 1
                    if now - self._sent_at.get(key, now) < self._update_interval:
                        return
                    payload = prior
                else:
                    try:
                        text = record.getMessage()
                    except Exception:  # noqa: BLE001 — a bad format arg is not our problem to raise
                        text = str(record.msg)
                    payload = Problem(
                        SOURCE_HOST, key, severity,
                        f"The {self._origin or 'host'} app logged "
                        f"{'an error' if severity == SEVERITY_ERROR else 'a warning'}.",
                        _clip(text.splitlines()[0] if text else ""),
                        extra={"logger": record.name})
                    self._seen[key] = payload
                self._sent_at[key] = now
            self._on_problem(payload)
        except Exception:  # noqa: BLE001 — logging must never raise into the caller
            pass
        finally:
            self._busy.on = False


def describe_problems(problems) -> str:
    """One entry per problem: where, severity, the sentence, and the raw line."""
    lines = []
    for p in problems:
        where = "Keyboard" if p.source == SOURCE_KEYBOARD else "Host"
        times = f" (seen {p.count}×)" if p.count > 1 else ""
        lines.append(f"- [{where}, {p.severity}] {p.summary}{times}")
        if p.line:
            lines.append(f"    {p.line}")
    return "\n".join(lines)


def compose_report_text(problems) -> tuple[str, str]:
    """(description, title) for the Report-a-Problem dialog."""
    problems = list(problems)
    description = "\n".join([
        "PolyKybd Host noticed the following while running:", "",
        describe_problems(problems), "",
        "What were you doing when this happened?", ""])
    first = problems[0].summary if problems else "Problem detected"
    title = first if len(problems) == 1 else f"{first} (+{len(problems) - 1} more)"
    return description, title
