#!/usr/bin/env python3
"""
Generate the upsweep pixel-art avatar and favicons.

A 16x16 tile with a pixel letter "U" and a sweep line below it. Uses only the
Python standard library; writes PNGs, a multi-size favicon.ico and an SVG into
the directory of this script.

    $ python3 static/avatar/generate.py                  # default theme
    $ python3 static/avatar/generate.py --theme phosphor
    $ python3 static/avatar/generate.py --line trail
    $ python3 static/avatar/generate.py --list           # show themes and lines
    $ python3 static/avatar/generate.py --preview        # all combinations
"""

import argparse
import os
import struct
import zlib

# Pixel map, 16x16. One character per pixel, see THEMES. The sweep line (row
# LINE_ROW) and its glow (the row below) are replaced by one of LINES.
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

# Sprite characters:
#   T  tile             h  tile edge, top and left
#   U  letter           s  tile edge, bottom and right
#   L  sweep line       d  offset below/right of letter and line (glow/shadow)
#   l  dim sweep line   .  transparent (rounded corners)
#
# Colors are hex RGB. Tinting "d" towards the accent gives a faint neon glow.
# "l" is optional, it defaults to "L" blended halfway into the tile.
THEMES = {
    "void": dict(  # near-black, ice white, cyan beam
        T="0b0f17", h="161d2b", s="06080d", d="0c2530", U="e6fbff", L="22d3ee"
    ),
    "phosphor": dict(  # green terminal / CRT
        T="050b07", h="0f1c13", s="020503", d="0b2a16", U="c8ffd8", L="39ff88"
    ),
    "ion": dict(  # deep indigo, violet drive glow
        T="0d0b1a", h="1a1730", s="07060f", d="1e1640", U="ece9ff", L="a78bfa"
    ),
    "hud": dict(  # cockpit display, amber readout
        T="0a0c10", h="171b22", s="050608", d="2a1d05", U="e8eef5", L="ffb000"
    ),
    "synth": dict(  # magenta letter, cyan line
        T="0c0814", h="1c1428", s="06040a", d="2a0f2e", U="ff7ae0", L="00e5ff"
    ),
    "frost": dict(  # light variant, clean lab white
        T="e9eef4", h="f8fafc", s="c9d2dd", d="cfe6f3", U="0b1220", L="0ea5e9"
    ),
    "mono": dict(  # low profile, no accent color at all
        T="111111", h="1c1c1c", s="0a0a0a", d="1a1a1a", U="eeeeee", L="777777"
    ),
    "classic": dict(  # the original slate/amber
        T="1e293b", h="334155", s="0f172a", d="131b2c", U="f8fafc", L="f59e0b"
    ),
}

# Sweep line patterns, drawn from the letter's left edge. The letter is 8 pixels
# wide; 8 / phi = 4.9, so 5 swept and 3 still scanning (5 : 3 : 8, Fibonacci).
#   L  swept (solid)    l  still scanning (dim)    .  gap
LINES = {
    "solid": "LLLLLLLL",  # done
    "golden": "LLLLL.l.",  # 5 swept, 3 scanning, within the letter width
    "trail": "LLLLL.l.l",  # scan runs past the letter, towards the edge
    "dot": "LLLLL.L.",  # like golden, but the dot at full brightness
}

DEFAULT_THEME = "void"
DEFAULT_LINE = "golden"

LINE_ROW, LINE_COL = 12, 4

HERE = os.path.dirname(os.path.abspath(__file__))


def palette(theme):
    pal = {".": (0, 0, 0, 0)}
    for key, hexcolor in THEMES[theme].items():
        pal[key] = tuple(bytes.fromhex(hexcolor)) + (0xFF,)
    if "l" not in pal:
        pal["l"] = tuple((a + b) // 2 for a, b in zip(pal["L"], pal["T"]))
    return pal


def sprite_rows(line=DEFAULT_LINE):
    """Sprite as rows of characters, with the given sweep line drawn in."""
    rows = [list(row) for row in SPRITE.strip().splitlines()]
    assert all(len(r) == len(rows[0]) for r in rows), "ragged sprite"
    pattern = LINES[line]
    assert LINE_COL + len(pattern) < len(rows[0]) - 2, "line too long"
    beam, glow = rows[LINE_ROW], rows[LINE_ROW + 1]
    for x in range(1, len(beam) - 1):
        beam[x] = glow[x] = "T"
    for i, c in enumerate(pattern):
        x = LINE_COL + i
        if c != ".":
            beam[x] = c
        if c == "L":  # only the swept part glows
            glow[x + 1] = "d"
    return rows


def load_sprite(theme=DEFAULT_THEME, line=DEFAULT_LINE):
    pal = palette(theme)
    return [[pal[c] for c in row] for row in sprite_rows(line)]


def preview_sheet(factor=8, gap=2):
    """Grid of all lines (rows) by themes (columns), transparent background."""
    blank = (0, 0, 0, 0)
    rows = []
    for j, line in enumerate(LINES):
        if j:
            rows.extend([[blank] * len(rows[0])] * gap)
        sprites = [load_sprite(theme, line) for theme in THEMES]
        for y in range(len(sprites[0])):
            row = []
            for i, sprite in enumerate(sprites):
                if i:
                    row.extend([blank] * gap)
                row.extend(sprite[y])
            rows.append(row)
    return scale(rows, factor)


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


def write(outdir, name, data):
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, name)
    mode = "w" if isinstance(data, str) else "wb"
    with open(path, mode) as f:
        f.write(data)
    print(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "-t",
        "--theme",
        default=DEFAULT_THEME,
        choices=sorted(THEMES),
        help="color theme (default: %(default)s)",
    )
    parser.add_argument(
        "-L",
        "--line",
        default=DEFAULT_LINE,
        choices=list(LINES),
        help="sweep line style (default: %(default)s)",
    )
    parser.add_argument(
        "-o", "--outdir", default=HERE, help="output directory (default: %(default)s)"
    )
    parser.add_argument(
        "-p",
        "--preview",
        action="store_true",
        help="only write preview.png, all lines (rows) by themes (columns)",
    )
    parser.add_argument(
        "-l", "--list", action="store_true", help="list themes and lines"
    )
    args = parser.parse_args()

    if args.list:
        print("themes:")
        for name in THEMES:
            print("  " + name + (" (default)" if name == DEFAULT_THEME else ""))
        print("lines:")
        for name, pattern in LINES.items():
            default = " (default)" if name == DEFAULT_LINE else ""
            print(f"  {name:<8} {pattern}{default}")
        return
    if args.preview:
        write(args.outdir, "preview.png", encode_png(preview_sheet()))
        return

    pixels = load_sprite(args.theme, args.line)
    base = len(pixels)

    pngs = {}
    for size in (16, 32, 48, 64, 128, 192, 256, 512):
        pngs[size] = encode_png(scale(pixels, size // base))

    for size in (16, 32, 192):
        write(args.outdir, f"favicon-{size}.png", pngs[size])
    write(args.outdir, "avatar.png", pngs[512])
    write(
        args.outdir,
        "favicon.ico",
        encode_ico([(s, pngs[s]) for s in (16, 32, 48, 64, 256)]),
    )
    write(args.outdir, "avatar.svg", encode_svg(pixels))


if __name__ == "__main__":
    main()
