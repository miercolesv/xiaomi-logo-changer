"""A made-up logo partition laid out like a Xiaomi Mi 10's, for tests and
the README pictures. Only plain shapes stand in for the real screens."""

import struct

from PIL import Image, ImageDraw

W, H = 1080, 2340
BLOCK = 4096
SLOT_BLOCKS = 0x73B
FIRST_BLOCK = 5


def bmp(image, bpp=24, top_down=False, extra=2):
    """BMP bytes like Xiaomi's: 24-bit bottom-up, two spare bytes at the end."""
    w, h = image.size
    stride = ((w * bpp + 31) // 32) * 4
    raw = image.convert("RGB").tobytes("raw", "BGR" if bpp == 24 else "BGRX")
    row = w * bpp // 8
    rows = [raw[y * row:(y + 1) * row] + b"\0" * (stride - row) for y in range(h)]
    if not top_down:
        rows.reverse()
    body = b"".join(rows) + b"\0" * extra
    head = struct.pack("<2sIHHI", b"BM", 54 + len(body), 0, 0, 54)
    head += struct.pack("<IiiHHIIiiII", 40, w, -h if top_down else h, 1, bpp, 0, len(body), 2835, 2835, 0, 0)
    return head + body


def screen(kind, w=W, h=H):
    im = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(im)
    u = w / 1080
    if kind in ("logo", "unlocked"):
        d.rounded_rectangle([422 * u, 1012 * h / H, 657 * u, 1247 * h / H], radius=60 * u, fill=(255, 255, 255))
        d.rectangle([450 * u, h * 0.900, 520 * u, h * 0.905], fill=(220, 220, 220))
        d.rectangle([409 * u, h * 0.910, 669 * u, h * 0.928], fill=(255, 255, 255))
        if kind == "unlocked":
            d.rectangle([516 * u, h * 0.041, 563 * u, h * 0.061], outline=(200, 200, 200), width=4)
    elif kind == "fastboot":
        d.rectangle([288 * u, h * 0.485, 792 * u, h * 0.505], fill=(115, 56, 2))
    elif kind == "error":
        d.regular_polygon((540 * u, h * 0.45, 40 * u), 3, fill=(229, 57, 53))
        d.rectangle([300 * u, h * 0.515, 780 * u, h * 0.525], fill=(255, 255, 255))
        d.rectangle([340 * u, h * 0.545, 740 * u, h * 0.552], fill=(150, 150, 150))
    return im


KINDS = ["logo", "fastboot", "unlocked", "error", "logo", "unlocked", "logo", "unlocked"]


def partition(kinds=KINDS, size=64 * 1024 * 1024, **bmp_args):
    data = bytearray(size)
    struct.pack_into("<8s", data, 0x4000, b"LOGO!!!!")
    offsets = []
    for i, kind in enumerate(kinds):
        block = FIRST_BLOCK + i * SLOT_BLOCKS
        blob = bmp(screen(kind), **bmp_args)
        off = block * BLOCK
        data[off:off + len(blob)] = blob
        struct.pack_into("<II", data, 0x4008 + i * 8, block, SLOT_BLOCKS)
        offsets.append((off, len(blob)))
    return bytes(data), offsets


if __name__ == "__main__":
    import sys
    data, _ = partition()
    with open(sys.argv[1] if len(sys.argv) > 1 else "synthetic-logo.img", "wb") as f:
        f.write(data)
