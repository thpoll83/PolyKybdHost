import random

import rle_compress


def bytes_to_c_arr(data):
    return [format(b, "#04x") for b in data]


def main():
    rnd_bytes = random.randbytes(60)
    compressed = rle_compress.compress(rnd_bytes)

    print("Original Bytes:")
    print(",".join(bytes_to_c_arr(rnd_bytes)))

    print("")
    print("Compressed Bytes:")
    print(",".join(bytes_to_c_arr(compressed)))


if __name__ == "__main__":
    main()
