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
    return argparse.Namespace(design=design, image=None, text=None, footer="Linux", redraw_padlock=True,
                              keep_fastboot=False, keep_error=False, logo=None, fastboot=None, error=None, keep=None)


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


main()
