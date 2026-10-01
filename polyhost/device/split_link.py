"""Recognise "the USB half answers, the other half does not" from the host side.

A firmware update and a font-pack flash both start by erasing a region on BOTH
halves. The USB half replies ``~`` ("still erasing") to every BEGIN poll until
the other half ACKs its own erase over the split link (qmk ``hid_fw_up.c``,
``CMD_FW_UP_BEGIN``). So ``~`` replies right up to the 90 s deadline mean the
USB half is alive and the other half never confirmed: the cable between the
halves is loose, or that half is not running firmware at all, for example
sitting in BOOTSEL after a ``.uf2`` the boot ROM ignored.

The host cannot tell those apart, and it can only fix neither, so the message
says what to check and the GUI offers the firmware ``.uf2`` for a manual
flash. The check works on any firmware that has the BEGIN poll, which is what
matters: the boards that hit this are the ones that cannot be updated over HID.

⚠️ The marker is matched as TEXT because the message is the only thing that
crosses the daemon -> GUI event boundary for a firmware flash (``fw_flash_done``
carries ``msg``). Keep ``SPLIT_LINK_MARK`` inside every message built here, and
build them only through ``split_link_timeout_message()``.
"""

SPLIT_LINK_MARK = "the other keyboard half did not confirm"


def split_link_timeout_message(prefix: str, what: str) -> str:
    """The user-facing text for a BEGIN that timed out on ``~`` replies."""
    return (f"{prefix} — the USB half answered, but {SPLIT_LINK_MARK} that it had "
            f"erased the {what} within 90 s. Check the cable between the two halves. "
            "If the other half stays dark, it is not running firmware and needs the "
            "firmware .uf2 copied onto it by hand.")


def is_split_link_failure(msg) -> bool:
    """True when ``msg`` came from ``split_link_timeout_message()``."""
    return isinstance(msg, str) and SPLIT_LINK_MARK in msg
