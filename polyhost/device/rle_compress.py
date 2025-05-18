def write(encoded, count, current_bit):
    while count > 127:
        encoded.append(127 if current_bit == 0 else 255)
        count -= 127
    encoded.append(count if current_bit == 0 else 128 + count)


def compress(byte_stream):
    encoded = []
    current_bit = 0x00
    count = 0

    for byte in byte_stream:
        for _ in range(0, 8):
            if (byte & 0x80) == current_bit:
                count += 1
            else:
                write(encoded, count, current_bit)
                current_bit = byte & 0x80
                count = 1
            byte <<= 1
    write(encoded, count, current_bit)
    return bytearray(encoded)
