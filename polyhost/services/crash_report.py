"""Keyboard crash records: detection in the console stream, decoding, and the
text a user can hand to a maintainer.

The firmware (``keyboards/polykybd/base/crash_record.c``) records a HardFault,
an unhandled exception or a watchdog timeout into NOLOAD RAM, reboots, and on
the next boot prints ONE line with its boot banner::

    crash: side=master kind=hardfault core=0 pc=0x10012345 lr=0x1000abcd
           sp=0x20040ff0 psr=0x21000003 icsr=0x00000003 phase=3:0x0015
           up=123456ms n=1 reason=0x22 fw=0.18.0

(one line on the wire; wrapped here). The banner is re-emitted a few times for a
late console, so the same record arrives more than once — :class:`CrashScanner`
dedupes by the line itself. The slave's record is pulled over the split link by
the master and printed as ``side=slave``.

The HID command (cmd 39) returns the same record as 48 packed bytes; ``decode_record``
mirrors ``poly_crash_record_t`` field for field. Everything here is Qt-free: the
scanner runs on the HID worker thread inside :class:`PolyCore`, and the dialog
only formats what it is handed.

⚠️ A console read is a REPORT-SIZED FRAGMENT, not a line (the same trap the HIL
rig's ``ConsoleTap`` documents): the crash line can arrive split across two
250 ms reads, so the scanner reassembles across calls and only ever classifies
``\\n``-terminated lines.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass

# Wire layout of poly_crash_record_t (base/crash_record.h), little-endian:
#   u32 magic, u8 kind, u8 core, u8 consecutive, u8 reset_reason,
#   u32 pc, lr, sp, xpsr, icsr, uptime_ms, u16 phase, u16 phase_arg,
#   char fw[8], u32 crc
RECORD_STRUCT = struct.Struct("<IBBBBIIIIIIHH8sI")
RECORD_LEN = RECORD_STRUCT.size          # 48
RECORD_MAGIC = 0xC4A5C0DE
HID_BODY_LEN = 1 + RECORD_LEN            # [flags][record]
HID_FLAG_PRESENT = 1 << 0
HID_FLAG_FRESH = 1 << 1

KIND_NAMES = {
    0: "none",
    1: "hardfault",
    2: "unhandled",
    3: "watchdog",
    4: "halt",
}

# enum crash_phase -- keep in step with base/crash_record.h.
PHASE_NAMES = {
    0: "unknown",
    1: "boot",
    2: "main loop",
    3: "HID command",
    4: "split transaction",
    5: "waiting for core1",
    6: "flash write",
    7: "USB suspend",
    8: "firmware self-apply",
}

RESET_REASON_BITS = (
    (1 << 0, "POR"),
    (1 << 1, "RUN pin"),
    (1 << 2, "PSM restart"),
    (1 << 4, "watchdog timer"),
    (1 << 5, "watchdog forced"),
)

# One `key=value` per field; `side` is the anchor the whole detection keys on.
CRASH_LINE_RE = re.compile(
    r"crash: side=(?P<side>\w+) kind=(?P<kind>\w+) core=(?P<core>\d+) "
    r"pc=0x(?P<pc>[0-9a-fA-F]+) lr=0x(?P<lr>[0-9a-fA-F]+) sp=0x(?P<sp>[0-9a-fA-F]+) "
    r"psr=0x(?P<psr>[0-9a-fA-F]+) icsr=0x(?P<icsr>[0-9a-fA-F]+) "
    r"phase=(?P<phase>\d+):0x(?P<phase_arg>[0-9a-fA-F]+) up=(?P<up>\d+)ms "
    r"n=(?P<n>\d+) reason=0x(?P<reason>[0-9a-fA-F]+) fw=(?P<fw>\S+)")


@dataclass
class CrashRecord:
    side: str
    kind: str
    core: int
    pc: int
    lr: int
    sp: int
    xpsr: int
    icsr: int
    phase: int
    phase_arg: int
    uptime_ms: int
    consecutive: int
    reset_reason: int
    fw: str
    line: str = ""          # the console line as printed (empty when decoded from HID)
    fresh: bool = True      # recorded by the boot before the one that reported it

    # -- helpers -----------------------------------------------------------
    @property
    def phase_name(self) -> str:
        return PHASE_NAMES.get(self.phase, f"phase {self.phase}")

    @property
    def reset_reason_text(self) -> str:
        names = [n for bit, n in RESET_REASON_BITS if self.reset_reason & bit]
        return ", ".join(names) if names else "unknown"

    @property
    def vector(self) -> int:
        """ICSR.VECTACTIVE — which exception was running (0 = thread mode)."""
        return self.icsr & 0x1FF

    def to_dict(self) -> dict:
        """JSON-safe form for the core event / RPC payload."""
        return {
            "side": self.side, "kind": self.kind, "core": self.core,
            "pc": self.pc, "lr": self.lr, "sp": self.sp, "xpsr": self.xpsr,
            "icsr": self.icsr, "phase": self.phase, "phase_arg": self.phase_arg,
            "uptime_ms": self.uptime_ms, "consecutive": self.consecutive,
            "reset_reason": self.reset_reason, "fw": self.fw,
            "line": self.line, "fresh": self.fresh,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CrashRecord":
        return cls(
            side=str(d.get("side", "?")), kind=str(d.get("kind", "none")),
            core=int(d.get("core", 0)), pc=int(d.get("pc", 0)), lr=int(d.get("lr", 0)),
            sp=int(d.get("sp", 0)), xpsr=int(d.get("xpsr", 0)), icsr=int(d.get("icsr", 0)),
            phase=int(d.get("phase", 0)), phase_arg=int(d.get("phase_arg", 0)),
            uptime_ms=int(d.get("uptime_ms", 0)), consecutive=int(d.get("consecutive", 0)),
            reset_reason=int(d.get("reset_reason", 0)), fw=str(d.get("fw", "?")),
            line=str(d.get("line", "")), fresh=bool(d.get("fresh", True)),
        )

    def as_console_line(self) -> str:
        """The firmware's own line shape, for a record decoded from HID."""
        if self.line:
            return self.line
        return (f"crash: side={self.side} kind={self.kind} core={self.core} "
                f"pc=0x{self.pc:08x} lr=0x{self.lr:08x} sp=0x{self.sp:08x} "
                f"psr=0x{self.xpsr:08x} icsr=0x{self.icsr:08x} "
                f"phase={self.phase}:0x{self.phase_arg:04x} up={self.uptime_ms}ms "
                f"n={self.consecutive} reason=0x{self.reset_reason:02x} fw={self.fw}")


def parse_crash_line(line: str) -> CrashRecord | None:
    """Parse one console line; None when it is not a crash line."""
    m = CRASH_LINE_RE.search(line)
    if not m:
        return None
    g = m.groupdict()
    return CrashRecord(
        side=g["side"], kind=g["kind"], core=int(g["core"]),
        pc=int(g["pc"], 16), lr=int(g["lr"], 16), sp=int(g["sp"], 16),
        xpsr=int(g["psr"], 16), icsr=int(g["icsr"], 16),
        phase=int(g["phase"]), phase_arg=int(g["phase_arg"], 16),
        uptime_ms=int(g["up"]), consecutive=int(g["n"]),
        reset_reason=int(g["reason"], 16), fw=g["fw"],
        line=line.strip(), fresh=True,
    )


def decode_record(body: bytes, side: str = "master") -> CrashRecord | None:
    """Decode a cmd-39 reply body ``[flags][48-byte record]``.

    None when the flags say no record is present, the body is short, or the
    magic does not match (an older firmware answering with zeros)."""
    if len(body) < HID_BODY_LEN:
        return None
    flags = body[0]
    if not flags & HID_FLAG_PRESENT:
        return None
    (magic, kind, core, consecutive, reason, pc, lr, sp, xpsr, icsr, uptime,
     phase, phase_arg, fw_raw, _crc) = RECORD_STRUCT.unpack(body[1:1 + RECORD_LEN])
    if magic != RECORD_MAGIC:
        return None
    fw = fw_raw.split(b"\x00", 1)[0].decode("ascii", "replace")
    return CrashRecord(
        side=side, kind=KIND_NAMES.get(kind, f"kind {kind}"), core=core,
        pc=pc, lr=lr, sp=sp, xpsr=xpsr, icsr=icsr, phase=phase, phase_arg=phase_arg,
        uptime_ms=uptime, consecutive=consecutive, reset_reason=reason, fw=fw,
        fresh=bool(flags & HID_FLAG_FRESH),
    )


class CrashScanner:
    """Reassemble console fragments into lines and surface each crash record once.

    ``feed`` takes whatever the 250 ms console read returned and yields the
    records completed by it. A record is reported once per distinct line: the
    boot banner re-emits for ~30 s, and the same line arriving again is noise.
    """

    MAX_PENDING = 4096   # a fragment that never terminates must not grow forever

    def __init__(self):
        self._pending = ""
        self._seen: set[str] = set()

    def feed(self, chunk: str) -> list[CrashRecord]:
        if not chunk:
            return []
        buf = self._pending + chunk
        parts = buf.split("\n")
        self._pending = parts.pop()
        if len(self._pending) > self.MAX_PENDING:
            self._pending = self._pending[-self.MAX_PENDING:]
        out = []
        for line in parts:
            if "crash: side=" not in line:
                continue
            rec = parse_crash_line(line)
            if rec is None or rec.line in self._seen:
                continue
            self._seen.add(rec.line)
            out.append(rec)
        return out

    def forget(self) -> None:
        """Allow every record to be reported again (after a clear)."""
        self._seen.clear()


# ---------------------------------------------------------------------------
# Text for humans
# ---------------------------------------------------------------------------

def summarize(rec: CrashRecord) -> str:
    """One paragraph a user can read without knowing the field names."""
    half = "the keyboard half connected over USB" if rec.side == "master" \
        else "the other (link-side) keyboard half"
    what = {
        "hardfault": "hit a hardware fault (HardFault) and restarted itself",
        "unhandled": "took an unexpected exception and restarted itself",
        "watchdog": "stopped responding and was restarted by its watchdog",
        "halt": "stopped deliberately and restarted itself",
    }.get(rec.kind, f"recorded a crash of kind '{rec.kind}' and restarted itself")
    up = rec.uptime_ms / 1000.0
    text = (f"Firmware {rec.fw} on {half} {what} after {up:.1f} s of uptime, "
            f"while it was in: {rec.phase_name}")
    if rec.phase == 3:
        text += f" (HID command {rec.phase_arg})"
    elif rec.phase == 4:
        text += f" (transaction id {rec.phase_arg})"
    text += "."
    if rec.consecutive > 1:
        text += f" This is crash number {rec.consecutive} in a row."
    if rec.kind in ("hardfault", "unhandled") and rec.pc:
        text += (f" The faulting address is 0x{rec.pc:08x}, which can be mapped to a "
                 f"source line against the {rec.fw} firmware ELF with addr2line.")
    return text


def compose_report_text(records: list[CrashRecord], diagnostics: str = "",
                        host_version: str | None = None) -> str:
    """The clipboard / issue text: summary, the raw line(s), the diagnostics."""
    parts = ["PolyKybd firmware crash report"]
    if host_version:
        parts.append(f"PolyKybdHost {host_version}")
    parts.append("")
    for rec in records:
        parts.append(summarize(rec))
        parts.append("")
        parts.append("    " + rec.as_console_line())
        parts.append("")
        parts.append(f"    reset reason: {rec.reset_reason_text}; exception vector: {rec.vector}")
        parts.append("")
    if diagnostics.strip():
        parts.append("Diagnostics:")
        parts.append(diagnostics.strip())
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def issue_description(records: list[CrashRecord]) -> str:
    """The pre-filled 'What happened' for the Report-a-Problem dialog."""
    lines = ["The keyboard firmware crashed and restarted itself. PolyKybdHost "
             "read this record from the keyboard's console:", ""]
    for rec in records:
        lines.append(summarize(rec))
        lines.append("")
        lines.append("```")
        lines.append(rec.as_console_line())
        lines.append("```")
        lines.append("")
    lines.append("What I was doing at the time: ")
    return "\n".join(lines)


def issue_title(records: list[CrashRecord]) -> str:
    rec = records[0]
    return f"Firmware crash: {rec.kind} on {rec.side} ({rec.fw}) in {rec.phase_name}"
