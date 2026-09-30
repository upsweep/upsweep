#!/usr/bin/env python3
"""
Generate the upsweep pixel-art avatar and favicons.

A 16x16 tile with a pixel letter "U" and a sweep line below it. Uses only the
Python standard library; writes PNGs, a multi-size favicon.ico and an SVG into
the directory of this script.

    $ python3 static/avatar/generate.py
"""

import os
import struct
import zlib

# Pixel map, 16x16. One character per pixel, see PALETTE.
SPRITE = """
.hhhhhhhhhhhhhh.
hTTTTTTTTTTTTTTs
hTTTTTTTTTTTTTTs
hTTTUUTTTTUUTTTs
hTTTUUdTTTUUdTTs
hTTTUUdTTTUUdTTs
hTTTUUdTTTUUdTTs
hTTTUUdTTTUUdTTs
hTTTUUdTTTUUdTTs
hTTTUUdTTTUUdTTs
hTTTTUUUUUUddTTs
hTTTTTddddddTTTs
hTTTLLLLLLLLTTTs
hTTTTddddddddTTs
hTTTTTTTTTTTTTTs
.ssssssssssssss.
"""

PALETTE = {
    ".": (0, 0, 0, 0),  # transparent (rounded corners)
    "T": (0x1E, 0x29, 0x3B, 0xFF),  # tile
    "h": (0x33, 0x41, 0x55, 0xFF),  # tile highlight edge (top, left)
    "s": (0x0F, 0x17, 0x2A, 0xFF),  # tile shadow edge (bottom, right)
    "d": (0x13, 0x1B, 0x2C, 0xFF),  # drop shadow of letter and line
    "U": (0xF8, 0xFA, 0xFC, 0xFF),  # letter
    "L": (0xF5, 0x9E, 0x0B, 0xFF),  # sweep line (accent)
}

HERE = os.path.dirname(os.path.abspath(__file__))


def load_sprite():
    rows = [line for line in SPRITE.strip().splitlines()]
    assert all(len(r) == len(rows[0]) for r in rows), "ragged sprite"
    return [[PALETTE[c] for c in row] for row in rows]


def scale(pixels, factor):
    """Nearest-neighbour upscale, keeps pixels crisp."""
    out = []
    for row in pixels:
        wide = [px for px in row for _ in range(factor)]
        out.extend([wide] * factor)
    return out


def encode_png(pixels):
    """Encode RGBA pixel rows as PNG bytes."""
    height, width = len(pixels), len(pixels[0])
    raw = b"".join(
        b"\x00" + b"".join(struct.pack("4B", *px) for px in row) for row in pixels
    )

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def encode_ico(images):
    """Build an ICO containing PNG-encoded images, given (size, png_bytes)."""
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for size, png in images:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        blobs += png
        offset += len(png)
    return header + entries + blobs


def encode_svg(pixels):
    height, width = len(pixels), len(pixels[0])
    rects = []
    for y, row in enumerate(pixels):
        x = 0
        while x < width:  # merge horizontal runs of the same color
            px = row[x]
            run = 1
            while x + run < width and row[x + run] == px:
                run += 1
            if px[3]:
                color = "#{:02x}{:02x}{:02x}".format(*px[:3])
                rects.append(
                    f'<rect x="{x}" y="{y}" width="{run}" height="1" fill="{color}"/>'
                )
            x += run
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'shape-rendering="crispEdges">\n  ' + "\n  ".join(rects) + "\n</svg>\n"
    )


def write(name, data):
    path = os.path.join(HERE, name)
    mode = "w" if isinstance(data, str) else "wb"
    with open(path, mode) as f:
        f.write(data)
    print(path)


def main():
    pixels = load_sprite()
    base = len(pixels)

    pngs = {}
    for size in (16, 32, 48, 64, 128, 192, 256, 512):
        pngs[size] = encode_png(scale(pixels, size // base))

    for size in (16, 32, 192):
        write(f"favicon-{size}.png", pngs[size])
    write("avatar.png", pngs[512])
    write("favicon.ico", encode_ico([(s, pngs[s]) for s in (16, 32, 48, 64, 256)]))
    write("avatar.svg", encode_svg(pixels))


if __name__ == "__main__":
    main()
