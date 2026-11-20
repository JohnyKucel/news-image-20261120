import os
import struct
import zlib

ROOT = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(
    os.environ.get("MAKEFUN_OUTPUT_DIR", os.path.join(ROOT, "out")),
    "entry.png",
)
ASSETS = os.path.join(ROOT, "assets")

PAGE_W, PAGE_H = 1024, 1024

BG = (23, 19, 16)
CREAM = (242, 237, 227)
HAIRLINE = (139, 130, 112)
RED = (192, 57, 43)
RED_HI = (231, 76, 60)

PHOTOS = [
    ("hero_976x420.png", 24, 211),
    ("gta_232x80.png", 24, 671),
    ("akvan_232x80.png", 272, 671),
    ("voyager_232x80.png", 520, 671),
    ("hayabusa_232x80.png", 768, 671),
]

TEXTS = [
    ("t_volume.png", 449, 7),
    ("t_masthead.png", 325, 30),
    ("t_dateline.png", 369, 85),
    ("t_hero_kicker.png", 24, 116),
    ("t_chip.png", 842, 111),
    ("t_hero_head.png", 24, 140),
    ("t_deck.png", 25, 641),
    ("t_arc.png", 336, 657),
    ("t_card0.png", 24, 761),
    ("t_card1.png", 272, 761),
    ("t_card2.png", 520, 761),
    ("t_card3.png", 768, 761),
    ("t_digest.png", 24, 884),
    ("t_foot_l.png", 24, 985),
    ("t_foot_c.png", 204, 986),
    ("t_foot_r.png", 849, 985),
]

HLINES = [
    (24, 1000, 75, 1, HAIRLINE),
    (24, 1000, 105, 1, RED_HI),
    (24, 1000, 106, 2, RED),
    (24, 1000, 667, 1, HAIRLINE),
    (24, 1000, 978, 2, HAIRLINE),
]

VLINES = [
    (264, 675, 873, HAIRLINE),
    (512, 675, 873, HAIRLINE),
    (760, 675, 873, HAIRLINE),
    (346, 898, 949, HAIRLINE),
    (676, 898, 949, HAIRLINE),
]

OUTLINES = [
    (24, 211, 999, 630),
    (24, 671, 255, 750),
    (272, 671, 503, 750),
    (520, 671, 751, 750),
    (768, 671, 999, 750),
]


def read_png(path):
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG: " + path)
    pos = 8
    width = height = None
    bit_depth = color_type = interlace = None
    idat = bytearray()
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            (width, height, bit_depth, color_type, _comp, _filt,
             interlace) = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break
        pos += 12 + length
    if bit_depth != 8 or interlace != 0 or color_type not in (0, 2, 6):
        raise ValueError("unsupported PNG: " + path)
    channels = {0: 1, 2: 3, 6: 4}[color_type]
    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    out = bytearray(width * height * channels)
    prev = bytearray(stride)
    src = 0
    for y in range(height):
        filt = raw[src]
        src += 1
        line = bytearray(raw[src:src + stride])
        src += stride
        if filt == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 255
        elif filt == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif filt == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif filt == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                if pa <= pb and pa <= pc:
                    pred = a
                elif pb <= pc:
                    pred = b
                else:
                    pred = c
                line[i] = (line[i] + pred) & 255
        elif filt != 0:
            raise ValueError("bad PNG filter %d in %s" % (filt, path))
        prev = line
        row = y * width * channels
        if channels == 3:
            out[row:row + width * 3] = line
        elif channels == 4:
            out[row:row + width * 4] = line
        else:
            for x in range(width):
                o = row + x * 3
                out[o] = out[o + 1] = out[o + 2] = line[x]
    return width, height, out, channels


def chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))


def write_png(path, width, height, rgb):
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    stride = width * 3
    best = None
    for filt in (0, 2):
        body = bytearray()
        prev = bytes(stride)
        for y in range(height):
            line = rgb[y * stride:(y + 1) * stride]
            body.append(filt)
            if filt == 0:
                body += line
            else:
                body += bytes((c - p) & 255 for c, p in zip(line, prev))
            prev = line
        packed = zlib.compress(bytes(body), 9)
        if best is None or len(packed) < len(best):
            best = packed
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", best) + chunk(b"IEND", b"")
    with open(path, "wb") as handle:
        handle.write(png)


def paste(page, img, img_w, img_h, at_x, at_y, channels):
    if channels == 3:
        for y in range(img_h):
            d = ((at_y + y) * PAGE_W + at_x) * 3
            s = y * img_w * 3
            page[d:d + img_w * 3] = img[s:s + img_w * 3]
        return
    for y in range(img_h):
        page_row = (at_y + y) * PAGE_W * 3
        img_row = y * img_w * 4
        for x in range(img_w):
            s = img_row + x * 4
            alpha = img[s + 3]
            if alpha == 0:
                continue
            d = page_row + (at_x + x) * 3
            if alpha == 255:
                page[d] = img[s]
                page[d + 1] = img[s + 1]
                page[d + 2] = img[s + 2]
            else:
                inv = 255 - alpha
                page[d] = (img[s] * alpha + page[d] * inv + 127) // 255
                page[d + 1] = (img[s + 1] * alpha + page[d + 1] * inv + 127) // 255
                page[d + 2] = (img[s + 2] * alpha + page[d + 2] * inv + 127) // 255


def fill_rect(page, x0, y0, x1, y1, color):
    for y in range(y0, y1 + 1):
        row = y * PAGE_W * 3
        for x in range(x0, x1 + 1):
            d = row + x * 3
            page[d] = color[0]
            page[d + 1] = color[1]
            page[d + 2] = color[2]


def outline_rect(page, x0, y0, x1, y1):
    inv = 255 - 56
    for x in range(x0, x1 + 1):
        for y in (y0, y1):
            d = (y * PAGE_W + x) * 3
            page[d] = (CREAM[0] * 56 + page[d] * inv + 127) // 255
            page[d + 1] = (CREAM[1] * 56 + page[d + 1] * inv + 127) // 255
            page[d + 2] = (CREAM[2] * 56 + page[d + 2] * inv + 127) // 255
    for y in range(y0 + 1, y1):
        for x in (x0, x1):
            d = (y * PAGE_W + x) * 3
            page[d] = (CREAM[0] * 56 + page[d] * inv + 127) // 255
            page[d + 1] = (CREAM[1] * 56 + page[d + 1] * inv + 127) // 255
            page[d + 2] = (CREAM[2] * 56 + page[d + 2] * inv + 127) // 255


def main():
    page = bytearray(PAGE_W * PAGE_H * 3)
    for i in range(0, len(page), 3):
        page[i] = BG[0]
        page[i + 1] = BG[1]
        page[i + 2] = BG[2]

    gw, gh, grain, gch = read_png(os.path.join(ASSETS, "grain_256.png"))
    for gy in range(0, PAGE_H, gh):
        for gx in range(0, PAGE_W, gw):
            paste(page, grain, gw, gh, gx, gy, gch)

    for name, x, y in PHOTOS:
        w, h, img, ch = read_png(os.path.join(ASSETS, name))
        paste(page, img, w, h, x, y, ch)

    for x0, x1, y, height, color in HLINES:
        top = y - (height - 1) // 2
        fill_rect(page, x0, top, x1, top + height - 1, color)
    for x, y0, y1, color in VLINES:
        fill_rect(page, x, y0, x, y1, color)

    for name, x, y in TEXTS:
        w, h, img, ch = read_png(os.path.join(ASSETS, name))
        paste(page, img, w, h, x, y, ch)

    for x0, y0, x1, y1 in OUTLINES:
        outline_rect(page, x0, y0, x1, y1)

    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    write_png(DEST, PAGE_W, PAGE_H, bytes(page))
    print("wrote", DEST)


if __name__ == "__main__":
    main()
