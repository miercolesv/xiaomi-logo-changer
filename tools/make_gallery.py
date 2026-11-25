"""Render the design pictures used in the README (from a synthetic partition,
so no phone maker's artwork ends up in them)."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "tests"))

from PIL import Image  # noqa: E402

import logo_changer as lc  # noqa: E402
import synthetic  # noqa: E402

OUT = os.path.join(HERE, "..", "docs", "designs")
TW = 270  # thumbnail width


def opts(design, **kw):
    a = argparse.Namespace(design=design, image=None, text=None, footer="Linux", redraw_padlock=True,
                           keep_fastboot=False, keep_error=False, logo=None, fastboot=None, error=None, keep=None)
    for k, v in kw.items():
        setattr(a, k, v)
    return a


def thumb(data, slot):
    im = lc.decode(data, slot)
    return im.resize((TW, int(TW * im.height / im.width)), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    src, _ = synthetic.partition()
    row = []
    for name in lc.DESIGNS:
        new, _ = lc.build(src, opts(name), quiet=True)
        slots = lc.find_slots(new)
        boot, fast = thumb(new, slots[2]), thumb(new, slots[1])  # unlocked boot logo, fastboot
        pair = Image.new("RGB", (TW * 2 + 16, boot.height), (40, 40, 44))
        pair.paste(boot, (0, 0))
        pair.paste(fast, (TW + 16, 0))
        pair.save(os.path.join(OUT, f"{name}.png"), optimize=True)
        row.append(thumb(new, slots[0]))
    # error screen (the same for every design)
    new, _ = lc.build(src, opts(lc.DEFAULT_DESIGN), quiet=True)
    thumb(new, lc.find_slots(new)[3]).save(os.path.join(OUT, "error.png"), optimize=True)
    # all boot logos in one row, cropped to the middle
    crop = [t.crop((0, int(t.height * 0.30), TW, int(t.height * 0.97))) for t in row]
    strip = Image.new("RGB", (len(crop) * (TW + 10) - 10, crop[0].height), (40, 40, 44))
    for i, t in enumerate(crop):
        strip.paste(t, (i * (TW + 10), 0))
    strip.save(os.path.join(OUT, "all.png"), optimize=True)
    print("wrote", sorted(os.listdir(OUT)))


main()
