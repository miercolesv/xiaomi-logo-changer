"""Render docs/designs/gallery.png for the README, from a synthetic partition
(so no phone maker's artwork ends up in it)."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "tests"))

from PIL import Image, ImageDraw  # noqa: E402

import logo_changer as lc  # noqa: E402
import synthetic  # noqa: E402

OUT = os.path.join(HERE, "..", "docs", "designs")
TW, COLS, GAP, LABEL = 260, 4, 20, 40
BG = (22, 22, 26)


def opts(design):
    return argparse.Namespace(design=design, image=None, text=None, footer=None, os="android", redraw_padlock=True,
                              keep_fastboot=False, keep_error=False, logo=None, fastboot=None, error=None, keep=None)


def dashed_box(d, box, color, dash=18, width=4):
    x0, y0, x1, y1 = box
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        length = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
        for t in range(0, int(length), dash * 2):
            t0, t1 = t / length, min(t + dash, length) / length
            d.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                    (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], fill=color, width=width)


def label(d, cx, cy, text, size, color, kind="regular"):
    f = lc.font(kind, size)
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    d.text((cx - (r - l) / 2 - l, cy - (b - t) / 2 - t), text, font=f, fill=color)


def stock(kind):
    """Outline of a stock screen: labelled placeholders, not the real artwork."""
    im = Image.new("RGB", (1080, 2340), (0, 0, 0))
    d = ImageDraw.Draw(im)
    grey = (150, 150, 155)
    if kind == "boot":
        dashed_box(d, (422, 1012, 658, 1248), grey)
        label(d, 540, 1130, "Mi logo", 40, grey, "semibold")
        dashed_box(d, (380, 2096, 700, 2180), grey)
        label(d, 540, 2138, "Powered by android", 26, grey)
    else:
        dashed_box(d, (270, 1092, 810, 1188), (150, 90, 40))
        label(d, 540, 1140, "FASTBOOT", 56, (200, 110, 30), "semibold")
    return im


def before_after(src):
    new, _ = lc.build(src, opts(lc.DEFAULT_DESIGN), quiet=True)
    slots = lc.find_slots(new)
    shots = [("Stock boot screen", stock("boot")), ("New boot screen", lc.decode(new, slots[0])),
             ("Stock fastboot", stock("fastboot")), ("New fastboot", lc.decode(new, slots[1]))]
    w = 230
    crops = []
    for name, im in shots:
        im = im.crop((0, int(im.height * 0.38), im.width, int(im.height * 0.96)))
        crops.append((name, im.resize((w, int(w * im.height / im.width)), Image.LANCZOS)))
    h = crops[0][1].height
    arrow, pairgap = 56, 70
    width = 4 * w + 2 * arrow + pairgap + 2 * GAP
    sheet = Image.new("RGB", (width, h + LABEL + 2 * GAP), BG)
    d = ImageDraw.Draw(sheet)
    x = GAP
    for i, (name, im) in enumerate(crops):
        sheet.paste(im, (x, GAP))
        label(d, x + w / 2, GAP + h + 22, name, 20, (200, 200, 205))
        x += w
        if i % 2 == 0:
            label(d, x + arrow / 2, GAP + h / 2, "→", 40, (200, 200, 205))
            x += arrow
        elif i == 1:
            x += pairgap
    sheet.save(os.path.join(OUT, "before-after.png"), optimize=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    src, _ = synthetic.partition()
    tiles = []
    for name in lc.DESIGNS:
        new, _ = lc.build(src, opts(name), quiet=True)
        im = lc.decode(new, lc.find_slots(new)[0])
        im = im.crop((0, int(im.height * 0.38), im.width, int(im.height * 0.585)))  # the logo
        tiles.append((name, im.resize((TW, int(TW * im.height / im.width)), Image.LANCZOS)))
    th = tiles[0][1].height
    rows = (len(tiles) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * TW + (COLS + 1) * GAP, rows * (th + LABEL) + (rows + 1) * GAP), BG)
    d = ImageDraw.Draw(sheet)
    f = lc.font("regular", 22)
    for i, (name, im) in enumerate(tiles):
        r, c = divmod(i, COLS)
        if r == rows - 1:  # centre the last row
            c += (COLS - (len(tiles) - r * COLS)) / 2
        x, y = int(GAP + c * (TW + GAP)), GAP + r * (th + LABEL + GAP)
        sheet.paste(im, (x, y))
        w = d.textlength(name, font=f)
        d.text((x + (TW - w) / 2, y + th + 12), name, font=f, fill=(200, 200, 205))
    sheet.save(os.path.join(OUT, "gallery.png"), optimize=True)
    before_after(src)


main()
