
def compose_cmd_str(cmd, text):
    b = bytearray.fromhex(f"09{cmd.value:02x}")
    b.extend(text.encode())
    return b


def compose_cmd(cmd, *extra):
    if not extra:
        return bytearray.fromhex(f"09{cmd.value:02x}")

    byte_stream = bytearray.fromhex(f"09{cmd.value:02x}")
    for val in extra:
        byte_stream.extend(bytearray.fromhex(f"{val:02x}"))

    return byte_stream

def compose_roi_header(cmd, keycode, modifier, overlay, compressed):    # |-MSB--------|-----------LSB|
    b1 = (modifier & 0x0f) | ((overlay.top<<2)&0xf0)                    #   4 bits top   4 bits mods
    b2 = (overlay.top & 0x03) | (overlay.bottom<<2)                     #  6 bits bottom     2 bits top
    b3 = overlay.left                                                   #   (1 unused)    7 bits left
    b4 = overlay.right | 0x80  if compressed else overlay.right         #   1 bit rle     7 bits right
    return bytearray.fromhex(f"09{cmd.value:02x}{keycode:02x}{b1:02x}{b2:02x}{b3:02x}{b4:02x}")


def expect(cmd):
    return f"P{chr(cmd.value)}"


def split_by_n_chars(text, n):
    return [text[i : i + n] for i in range(0, len(text), n)]


# class Dummy:
#     def __init__(self):
#         self.top =9
#         self.left = 3
#         self.bottom = 37
#         self.right = 71
# d = Dummy()
# print(", ".join(hex(b) for b in compose_roi_header(231,2,d,True)))