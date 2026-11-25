import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from PIL import Image  # noqa: E402

import logo_changer as lc  # noqa: E402
import synthetic  # noqa: E402


def opts(**kw):
    a = argparse.Namespace(design=lc.DEFAULT_DESIGN, image=None, text=None, footer=None, os=None,
                           redraw_padlock=False, keep_fastboot=False, keep_error=False,
                           logo=None, fastboot=None, error=None, keep=None)
    for k, v in kw.items():
        setattr(a, k, v)
    return a


class LogoChanger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src, cls.offsets = synthetic.partition()

    def test_finds_and_classifies(self):
        slots = lc.plan(self.src, opts(), quiet=True)
        self.assertEqual([s.offset for s in slots], [o for o, _ in self.offsets])
        self.assertEqual([s.role for s in slots],
                         ["logo", "fastboot", "logo", "error", "logo", "logo", "logo", "logo"])
        self.assertEqual([bool(s.layout["top"]) for s in slots],
                         [False, False, True, False, False, True, False, True])

    def test_only_the_pictures_change(self):
        new, changed = lc.build(self.src, opts(), quiet=True)
        self.assertEqual(len(new), len(self.src))
        self.assertEqual(len(changed), 8)
        spans = [(s.offset, s.offset + s.size) for s in changed]
        for i in range(0, len(new), 4096):
            if new[i:i + 4096] != self.src[i:i + 4096]:
                self.assertTrue(any(a <= i < b for a, b in spans), f"unexpected change at 0x{i:x}")
        # the picture table and every BMP header stay as they were
        self.assertEqual(new[0x4000:0x5000], self.src[0x4000:0x5000])
        for s in changed:
            self.assertEqual(new[s.offset:s.offset + 54], self.src[s.offset:s.offset + 54])
            Image.open(io.BytesIO(new[s.offset:s.offset + s.size])).load()

    def test_same_input_same_output(self):
        a, _ = lc.build(self.src, opts(), quiet=True)
        b, _ = lc.build(self.src, opts(), quiet=True)
        self.assertEqual(a, b)

    def test_tile_designs_are_stable_on_their_own_output(self):
        """Building again on a result moves nothing by more than a pixel."""
        for name in ("terminal-green", "terminal", "outline", "gradient"):
            new, _ = lc.build(self.src, opts(design=name), quiet=True)
            again, _ = lc.build(new, opts(design=name), quiet=True)
            for s in lc.find_slots(new)[:3:2]:  # a locked and an unlocked boot logo
                logo_a = lc.classify(lc.decode(new, s))[1]["logo"]
                logo_b = lc.classify(lc.decode(again, s))[1]["logo"]
                self.assertEqual(logo_a, logo_b, name)

    def test_keep_options(self):
        new, changed = lc.build(self.src, opts(keep_fastboot=True, keep_error=True, keep=[7]), quiet=True)
        self.assertEqual(sorted(s.index for s in changed), [1, 3, 5, 6, 8])
        for i in (1, 3, 6):  # #2 fastboot, #4 error, #7 logo kept
            off, size = self.offsets[i]
            self.assertEqual(new[off:off + size], self.src[off:off + size])

    def test_padlock_is_kept_unless_redrawn(self):
        slot = lc.find_slots(self.src)[2]
        top = (450, 60, 630, 170)
        for redraw, same in ((False, True), (True, False)):
            new, _ = lc.build(self.src, opts(redraw_padlock=redraw), quiet=True)
            a, b = lc.decode(self.src, slot).crop(top), lc.decode(new, slot).crop(top)
            self.assertEqual(a.tobytes() == b.tobytes(), same)

    def test_os_defaults(self):
        self.assertEqual(lc.resolve(opts()).footer, "Android")
        self.assertEqual(lc.resolve(opts(), "linux").footer, "Linux")
        self.assertEqual(lc.resolve(opts(os="none")).footer, "")
        self.assertEqual(lc.resolve(opts(os="linux", footer="Arch Linux")).footer, "Arch Linux")
        a, _ = lc.build(self.src, opts(os="android"), quiet=True)
        b, _ = lc.build(self.src, opts(os="linux"), quiet=True)
        self.assertNotEqual(a, b)

    def test_every_design_and_a_picture(self):
        pic = os.path.join(tempfile.mkdtemp(), "pic.png")
        Image.new("RGBA", (300, 120), (200, 30, 90, 255)).save(pic)
        for name in lc.DESIGNS:
            _, changed = lc.build(self.src, opts(design=name), quiet=True)
            self.assertEqual(len(changed), 8, name)
        new, changed = lc.build(self.src, opts(image=pic, footer=""), quiet=True)
        centre = lc.decode(new, changed[0]).getpixel((540, 1130))
        self.assertEqual(centre, (200, 30, 90))

    def test_other_formats_round_trip(self):
        """32-bit, top-down, another resolution."""
        im = synthetic.screen("logo", 720, 1600)
        for bpp, top_down in ((32, True), (32, False), (24, True)):
            blob = synthetic.bmp(im, bpp=bpp, top_down=top_down, extra=0)
            data = b"\0" * 8192 + blob
            slot = lc.find_slots(data)[0]
            self.assertEqual((slot.width, abs(slot.height), slot.bpp), (720, 1600, bpp))
            role, _ = lc.classify(lc.decode(data, slot))
            self.assertEqual(role, "logo")
            changed = Image.new("RGB", (720, 1600), (10, 20, 30))
            out = lc.encode(blob, changed)
            self.assertEqual(len(out), len(blob))
            self.assertEqual(Image.open(io.BytesIO(out)).convert("RGB").tobytes(), changed.tobytes())


@unittest.skipUnless(shutil.which("sh") and shutil.which("dd") and shutil.which("od"), "needs a POSIX shell")
class Module(unittest.TestCase):
    def test_install_and_uninstall(self):
        src, _ = synthetic.partition()
        tmp = tempfile.mkdtemp()
        img = os.path.join(tmp, "logo.img")
        with open(img, "wb") as f:
            f.write(src)
        z = os.path.join(tmp, "module.zip")
        o = opts(source=img, output=z)
        lc.cmd_module(o)
        expected, _ = lc.build(src, opts(), quiet=True)

        modpath = os.path.join(tmp, "mod")
        with zipfile.ZipFile(z) as zf:
            zf.extractall(modpath)
            self.assertIn("module.prop", zf.namelist())
        blk = os.path.join(tmp, "blk")
        with open(blk, "wb") as f:
            f.write(src)
        bk = os.path.join(tmp, "bk")

        def run(script):
            with open(os.path.join(modpath, script)) as f:
                text = f.read()
            text = text.replace("/data/adb/xiaomi-logo-changer", bk)
            text = text.replace("BLK=$(find_part)", f"BLK={blk}")
            prelude = 'ui_print() { echo "$1"; }\nabort() { echo "$1"; exit 1; }\n'
            r = subprocess.run(["sh", "-c", prelude + text], env={**os.environ, "MODPATH": modpath},
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            return r.stdout

        out = run("customize.sh")
        self.assertIn("Done", out)
        with open(blk, "rb") as f:
            self.assertEqual(f.read(), expected)
        self.assertFalse([n for n in os.listdir(os.path.join(modpath, "logo")) if n.endswith(".bmp")])
        run("uninstall.sh")
        with open(blk, "rb") as f:
            self.assertEqual(f.read(), src)

    def test_refuses_another_layout(self):
        src, _ = synthetic.partition()
        tmp = tempfile.mkdtemp()
        img = os.path.join(tmp, "logo.img")
        with open(img, "wb") as f:
            f.write(src)
        z = os.path.join(tmp, "module.zip")
        lc.cmd_module(opts(source=img, output=z))
        modpath = os.path.join(tmp, "mod")
        with zipfile.ZipFile(z) as zf:
            zf.extractall(modpath)
        other = bytearray(src)
        other[0x740000:0x740000 + 54] = b"\0" * 54  # picture #2 is somewhere else
        blk = os.path.join(tmp, "blk")
        with open(blk, "wb") as f:
            f.write(other)
        with open(os.path.join(modpath, "customize.sh")) as f:
            text = f.read()
        text = text.replace("/data/adb/xiaomi-logo-changer", os.path.join(tmp, "bk")).replace("BLK=$(find_part)", f"BLK={blk}")
        prelude = 'ui_print() { echo "$1"; }\nabort() { echo "$1"; exit 1; }\n'
        r = subprocess.run(["sh", "-c", prelude + text], env={**os.environ, "MODPATH": modpath},
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("laid out differently", r.stdout)
        with open(blk, "rb") as f:
            self.assertEqual(f.read(), bytes(other))


if __name__ == "__main__":
    unittest.main()
