"""Draws demo.png, a 512x512 grid with a few blocks. No dependencies."""
import struct
import zlib
from pathlib import Path

W = H = 512
px = bytearray((22, 24, 28) * W * H)


def rect(x0, y0, x1, y1, c):
    for y in range(y0, y1):
        row = y * W * 3
        for x in range(x0, x1):
            px[row + x * 3:row + x * 3 + 3] = bytes(c)


for i in range(0, W, 64):
    rect(i, 0, i + 1, H, (40, 44, 50))
    rect(0, i, W, i + 1, (40, 44, 50))
for x0, y0, x1, y1 in ((60, 60, 200, 160), (300, 90, 460, 210), (120, 300, 260, 450), (330, 330, 420, 470)):
    rect(x0, y0, x1, y1, (52, 58, 66))
rect(255, 0, 257, H, (70, 75, 85))
rect(0, 255, W, 257, (70, 75, 85))

raw = b"".join(b"\x00" + bytes(px[y * W * 3:(y + 1) * W * 3]) for y in range(H))


def chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)


png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)) \
    + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
Path(__file__).with_name("demo.png").write_bytes(png)
