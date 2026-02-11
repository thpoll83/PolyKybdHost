from polyhost.device.keys import Modifier
from polyhost.device.overlay_data import OverlayData
from polyhost.device.command_ids import Cmd, HidId


def compose_request(hid_id: HidId, *extra: int) -> bytearray:
    if not extra:
        return bytearray.fromhex(f"{hid_id.value:02x}")
    byte_stream = bytearray.fromhex(f"{hid_id.value:02x}")
    for val in extra:
        byte_stream.extend(bytearray.fromhex(f"{val:02x}"))

    return byte_stream


def compose_cmd_str(cmd: Cmd, text: str) -> bytearray:
    b = bytearray.fromhex(f"{HidId.ID_CUSTOM_SAVE.value:02x}{cmd.value:02x}")
    b.extend(text.encode())
    return b


def compose_cmd(cmd: Cmd, *extra: int) -> bytearray:
    if not extra:
        return bytearray.fromhex(
            f"{HidId.ID_CUSTOM_SAVE.value:02x}{cmd.value:02x}"
        )
    byte_stream = bytearray.fromhex(
        f"{HidId.ID_CUSTOM_SAVE.value:02x}{cmd.value:02x}")
    for val in extra:
        byte_stream.extend(bytearray.fromhex(f"{val:02x}"))

    return byte_stream


def compose_roi_header(
    cmd: Cmd,
    keycode: int,
    mod: Modifier,
    o: OverlayData,
    compressed: bool,
) -> bytearray:                                      # |-MSB------|--------LSB|
    b1 = (mod.value & 0x0f) | ((o.top << 2) & 0xf0)  # 4 bits top  4 bits mods
    b2 = (o.top & 0x03) | (o.bottom << 2)            # 6 bits btm  2 bits top
    b3 = o.left                                      # (1 unused)  7 bits left
    b4 = o.right | 0x80 if compressed else o.right   # 1 bit rle   7 bits right
    return bytearray.fromhex(
        f"{HidId.ID_CUSTOM_SAVE.value:02x}{cmd.value:02x}"
        f"{keycode:02x}{b1:02x}{b2:02x}{b3:02x}{b4:02x}"
    )


def expect(cmd: Cmd) -> bytearray:
    return bytearray(f"P{chr(cmd.value)}", encoding="utf8")


def expectReq(hid_id: HidId) -> bytearray:
    return bytearray(f"{chr(hid_id.value)}", encoding="utf8")

# class Dummy:
#     def __init__(self):
#         self.top =9
#         self.left = 3
#         self.bottom = 37
#         self.right = 71
# d = Dummy()
# print(", ".join(hex(b) for b in compose_roi_header(231,2,d,True)))
