#!/usr/bin/env python3
"""Generate a 256x256 crescent-moon + star icon for Quran Radio.

Works with PIL/Pillow if available; otherwise falls back to a stdlib-only
PNG writer.
"""

import math
import os
import struct
import zlib

OUT  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
SIZE = 256

# Islamic green on transparent background
GREEN = (27, 107, 58, 255)
CLEAR = (0, 0, 0, 0)


# ── Pillow path ────────────────────────────────────────────────────────────────
def _try_pillow() -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        return False

    img  = Image.new("RGBA", (SIZE, SIZE), CLEAR)
    draw = ImageDraw.Draw(img)

    def bbox(cx, cy, r):
        return [cx - r, cy - r, cx + r, cy + r]

    # Crescent: large circle minus offset inner circle
    cx, cy = 108, 128
    r_outer = 88
    r_inner = 70
    offset  = 38

    draw.ellipse(bbox(cx, cy, r_outer), fill=GREEN)
    draw.ellipse(bbox(cx + offset, cy - 8, r_inner), fill=CLEAR)

    # Five-pointed star
    scx, scy = 192, 72
    ro, ri = 30, 12
    pts = []
    for i in range(10):
        angle = math.radians(i * 36 - 90)
        r = ro if i % 2 == 0 else ri
        pts.append((scx + r * math.cos(angle), scy + r * math.sin(angle)))
    draw.polygon(pts, fill=GREEN)

    # Slight smooth pass to clean up pixel edges
    img = img.filter(ImageFilter.SMOOTH_MORE)
    img.save(OUT, "PNG")
    return True


# ── Stdlib-only path ───────────────────────────────────────────────────────────
def _write_png(pixels: list, path: str):
    width = height = SIZE

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = b""
    for row in pixels:
        raw += b"\x00"
        for r, g, b, a in row:
            raw += bytes([r, g, b, a])

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)


def _rasterise() -> list:
    pixels = [[CLEAR] * SIZE for _ in range(SIZE)]

    def dist(x, y, cx, cy):
        return math.sqrt((x - cx) ** 2 + (y - cy) ** 2)

    # Crescent
    cx, cy, r_outer, r_inner, offset = 108, 128, 88, 70, 38
    for y in range(SIZE):
        for x in range(SIZE):
            if dist(x, y, cx, cy) <= r_outer and dist(x, y, cx + offset, cy - 8) > r_inner:
                pixels[y][x] = GREEN

    # Five-pointed star (scanline fill)
    scx, scy = 192, 72
    ro, ri   = 30, 12
    star_pts = []
    for i in range(10):
        angle = math.radians(i * 36 - 90)
        r = ro if i % 2 == 0 else ri
        star_pts.append((scx + r * math.cos(angle), scy + r * math.sin(angle)))

    min_sy = int(min(p[1] for p in star_pts))
    max_sy = int(max(p[1] for p in star_pts)) + 1
    n = len(star_pts)
    for sy in range(max(0, min_sy), min(SIZE, max_sy + 1)):
        xs = []
        for i in range(n):
            x1, y1 = star_pts[i]
            x2, y2 = star_pts[(i + 1) % n]
            if (y1 <= sy < y2) or (y2 <= sy < y1):
                xs.append(x1 + (sy - y1) / (y2 - y1) * (x2 - x1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            for sx in range(int(xs[k]), int(xs[k + 1]) + 1):
                if 0 <= sx < SIZE:
                    pixels[sy][sx] = GREEN

    return pixels


if __name__ == "__main__":
    if not _try_pillow():
        _write_png(_rasterise(), OUT)
    print(f"Icon saved → {OUT}  ({SIZE}x{SIZE})")
