#!/usr/bin/env python3
"""xiaomi-logo-changer: replace the boot logo of a Xiaomi phone.

The "logo" partition of a Xiaomi phone holds full-screen BMP pictures in
fixed slots: the boot logo (with and without the "unlocked" padlock), the
fastboot screen and an error screen. This tool finds them, draws new ones
in the same size and format, and writes them back into the same slots, so
the bootloader reads them as before.

  logo_changer.py designs                         list the designs
  logo_changer.py extract logo.img                save the pictures as PNG
  logo_changer.py build logo.img -o new.img       new image for fastboot
  logo_changer.py module logo.img -o logo.zip     Magisk / KernelSU module
  logo_changer.py pull -o logo.img                copy the partition off a rooted phone (adb)
  sudo logo_changer.py install                    on the phone, under Linux
  sudo logo_changer.py restore                    on the phone, under Linux

Needs Python 3.8+ and Pillow.
"""

import argparse
import io
import os
import pwd
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat
except ImportError:
    sys.exit("Pillow is needed: 'pip install pillow', or 'sudo pacman -S python-pillow' (Arch), "
             "or 'sudo apt install python3-pil' (Debian, Ubuntu)")

VERSION = "1.0"
REPO = "https://github.com/miercolesv/xiaomi-logo-changer"
FONT_URL = "https://raw.githubusercontent.com/miercolesv/xiaomi-logo-changer/main/fonts/"
FONTS = {
    "regular": "Inter-Regular.otf",
    "semibold": "Inter-SemiBold.otf",
    "mono": "DejaVuSansMono-Bold.ttf",
}
SS = 4  # supersampling for smooth edges
Image.MAX_IMAGE_PIXELS = 50_000_000


def die(msg):
    sys.exit(f"logo-changer: {msg}")


# --------------------------------------------------------------------------
# Fonts: next to this script, or downloaded once (when run as "curl | python3 -")

_font_dir = None


def font(kind, px):
    global _font_dir
    if _font_dir is None:
        here = os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__", "."))), "fonts")
        if all(os.path.exists(os.path.join(here, f)) for f in FONTS.values()):
            _font_dir = here
        else:
            import urllib.request
            _font_dir = os.path.join(tempfile.gettempdir(), "xiaomi-logo-changer-fonts")
            os.makedirs(_font_dir, exist_ok=True)
            for f in FONTS.values():
                path = os.path.join(_font_dir, f)
                if not os.path.exists(path):
                    with urllib.request.urlopen(FONT_URL + f, timeout=60) as r:
                        data = r.read()
                    with open(path, "wb") as out:
                        out.write(data)
    return ImageFont.truetype(os.path.join(_font_dir, FONTS[kind]), max(1, int(px)))


# --------------------------------------------------------------------------
# Finding the pictures

class Slot:
    """One BMP picture inside the partition."""

    def __init__(self, index, offset, size, width, height, bpp, pixels):
        self.index, self.offset, self.size = index, offset, size
        self.width, self.height, self.bpp, self.pixels = width, height, bpp, pixels
        self.role = None      # "logo", "fastboot", "error" or None (kept)
        self.layout = None    # bounding boxes found by classify()

    def __repr__(self):
        return f"#{self.index} at 0x{self.offset:x}"


def bmp_header(data, off):
    """(size, width, height, bpp, pixel offset) of a plausible BMP at off, else None."""
    if len(data) - off < 54 or data[off:off + 2] != b"BM":
        return None
    size, r1, r2, pix = struct.unpack_from("<IHHI", data, off + 2)
    dib, w, h, planes, bpp, comp = struct.unpack_from("<IiiHHI", data, off + 14)
    if r1 or r2 or planes != 1 or bpp not in (24, 32) or comp not in (0, 3):
        return None
    if dib not in (40, 52, 56, 108, 124) or not (0 < w <= 8192 and 0 < abs(h) <= 8192):
        return None
    if not (14 + dib <= pix < size <= len(data) - off):
        return None
    if size - pix < ((w * bpp + 31) // 32) * 4 * abs(h):
        return None
    return size, w, h, bpp, pix


def find_slots(data):
    slots, off = [], data.find(b"BM")
    while off != -1:
        hdr = bmp_header(data, off)
        if hdr:
            size, w, h, bpp, pix = hdr
            slots.append(Slot(len(slots) + 1, off, size, w, h, bpp, pix))
            off = data.find(b"BM", off + size)
        else:
            off = data.find(b"BM", off + 1)
    return slots


def decode(data, slot):
    return Image.open(io.BytesIO(data[slot.offset:slot.offset + slot.size])).convert("RGB")


def encode(original, image):
    """Pixels of image, in the exact header, size and row order of the original BMP."""
    size, w, h, bpp, pix = bmp_header(original, 0)
    assert image.size == (w, abs(h))
    stride = ((w * bpp + 31) // 32) * 4
    raw = image.convert("RGB").tobytes("raw", "BGR" if bpp == 24 else "BGRX")
    row = w * bpp // 8
    pad = b"\0" * (stride - row)
    rows = [raw[y * row:(y + 1) * row] + pad for y in range(abs(h))]
    if h > 0:  # bottom-up
        rows.reverse()
    body = bytearray(b"".join(rows))
    if bpp == 32:  # keep the original fourth byte of every pixel
        old = original[pix:pix + len(body)]
        body[3::4] = old[3::4]
    out = bytearray(original)
    out[pix:pix + len(body)] = body
    return bytes(out)


# --------------------------------------------------------------------------
# Working out what each picture shows

def bands(image, threshold=28):
    """Bounding boxes of the groups of non-dark rows."""
    w, h = image.size
    mask = image.convert("L").point(lambda v: 255 if v > threshold else 0)
    rows = [mask.crop((0, y, w, y + 1)).getbbox() is not None for y in range(h)]
    gap = max(6, h // 120)
    out, start, last = [], None, None
    for y, lit in enumerate(rows):
        if lit:
            if start is None:
                start = y
            elif y - last > gap:
                out.append((start, last))
                start = y
            last = y
    if start is not None:
        out.append((start, last))
    boxes = []
    for y0, y1 in out:
        x0, _, x1, _ = mask.crop((0, y0, w, y1 + 1)).getbbox()
        boxes.append((x0, y0, x1, y1 + 1))
    return boxes


def mean_color(image, box):
    region = image.crop(box)
    mask = region.convert("L").point(lambda v: 255 if v > 30 else 0)
    if mask.getbbox() is None:
        return (0, 0, 0)
    return tuple(int(c) for c in ImageStat.Stat(region, mask).mean[:3])


def classify(image):
    """("logo" | "fastboot" | "error" | None, layout)."""
    w, h = image.size
    bs = bands(image)
    top = [b for b in bs if b[3] < h * 0.10]
    foot = [b for b in bs if b[1] > h * 0.85]
    mid = [b for b in bs if b not in top and b not in foot]
    layout = {"top": top, "footer": None, "logo": None}
    if foot:
        layout["footer"] = (min(b[0] for b in foot), min(b[1] for b in foot),
                            max(b[2] for b in foot), max(b[3] for b in foot))
    if len(mid) == 1:
        x0, y0, x1, y1 = mid[0]
        cy = (y0 + y1) / 2
        if h * 0.30 < cy < h * 0.70:
            layout["logo"] = mid[0]
            if foot:
                return "logo", layout
            r, g, b = mean_color(image, mid[0])
            if (x1 - x0) > 3 * (y1 - y0) and r > g > b and r > 2 * b + 20:
                return "fastboot", layout  # orange "FASTBOOT"
    if not foot and len(mid) >= 2:
        r, g, b = mean_color(image, mid[0])
        if r > 150 and r > 2 * g and r > 2 * b:
            return "error", layout  # red warning sign and text
    return None, layout


# --------------------------------------------------------------------------
# Drawing

def element(w, h, draw_fn):
    """Draw at SS x size on a transparent canvas, return it scaled down."""
    canvas = Image.new("RGBA", (int(w * SS), int(h * SS)), (0, 0, 0, 0))
    draw_fn(canvas, ImageDraw.Draw(canvas), SS)
    return canvas.resize((int(w), int(h)), Image.LANCZOS)


def paste_center(screen, elem, cx, cy):
    screen.paste(elem, (int(round(cx - elem.width / 2)), int(round(cy - elem.height / 2))), elem)


def text_element(text, kind, px, fill, pad=0.25):
    f = font(kind, px * SS)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = probe.textbbox((0, 0), text, font=f)
    w, h = (r - l) / SS * (1 + pad), (b - t) / SS * (1 + pad * 2)

    def fn(c, d, s):
        d.text(((c.width - (r - l)) / 2 - l, (c.height - (b - t)) / 2 - t), text, font=f, fill=fill)
    return element(w, h, fn)


def prompt_tile(size, fill=None, fg=(0, 0, 0, 255), outline=None, outline_w=0.0,
                gradient=None, stroke=0.085, glow=None):
    """Rounded tile with a '>_' prompt drawn as shapes."""
    margin = 0.3 if glow else 0.0
    box = size * (1 + margin * 2)

    def fn(c, d, s):
        S = size * s
        x0 = y0 = margin * size * s
        rad = S * 0.26
        if gradient:
            n = int(S)
            ramp = Image.linear_gradient("L").resize((n, n))  # top to bottom
            diag = Image.blend(ramp, ramp.transpose(Image.Transpose.ROTATE_90).transpose(Image.Transpose.FLIP_LEFT_RIGHT), 0.5)
            g = ImageOps.colorize(diag, gradient[0], gradient[1]).convert("RGBA")
            m = Image.new("L", g.size, 0)
            ImageDraw.Draw(m).rounded_rectangle([0, 0, n - 1, n - 1], radius=rad, fill=255)
            c.paste(g, (int(x0), int(y0)), m)
        elif fill:
            d.rounded_rectangle([x0, y0, x0 + S, y0 + S], radius=rad, fill=fill)
        if outline:
            d.rounded_rectangle([x0, y0, x0 + S, y0 + S], radius=rad, outline=outline,
                                width=max(1, int(outline_w * s)))
        layer = Image.new("RGBA", c.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        t = S * stroke
        ax, ay = x0 + S * 0.26, y0 + S * 0.33
        bx, by = x0 + S * 0.45, y0 + S * 0.50
        cx, cy = ax, y0 + S * 0.67
        ld.line([(ax, ay), (bx, by), (cx, cy)], fill=fg, width=int(t), joint="curve")
        for px, py in ((ax, ay), (bx, by), (cx, cy)):
            ld.ellipse([px - t / 2, py - t / 2, px + t / 2, py + t / 2], fill=fg)
        ld.rounded_rectangle([x0 + S * 0.52, cy - t / 2, x0 + S * 0.76, cy + t / 2], radius=t / 2, fill=fg)
        if glow:
            halo = layer.filter(ImageFilter.GaussianBlur(S * 0.06))
            c.alpha_composite(halo)
            c.alpha_composite(halo)
        c.alpha_composite(layer)
    return element(box, box, fn)


def console_line(parts, px, cursor=None):
    """Monospace line from (text, colour) parts, with an optional block cursor."""
    f = font("mono", px * SS)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    text = "".join(p[0] for p in parts)
    l, t, r, b = probe.textbbox((0, 0), text + "M", font=f)
    cw = probe.textlength("M", font=f)
    extra = cw * 1.5 if cursor else 0
    width = (probe.textlength(text, font=f) + extra) / SS * 1.1
    height = (b - t) / SS * 1.6

    def fn(c, d, s):
        x = (c.width - (width / 1.1 * s)) / 2
        y = (c.height - (b - t)) / 2 - t
        for txt, col in parts:
            d.text((x, y), txt, font=f, fill=col)
            x += d.textlength(txt, font=f)
        if cursor:
            x += cw * 0.4
            d.rectangle([x, y + t, x + cw, y + b - (b - t) * 0.05], fill=cursor)
    return element(width, height, fn)


GREEN = (80, 250, 123, 255)
WHITE = (255, 255, 255, 255)
LIGHT = (230, 230, 230, 255)
GREY = (190, 190, 190, 255)
AMBER = (255, 176, 0, 255)


class Design:
    name = ""
    about = ""
    accent = WHITE
    fastboot_gap = 40  # between the logo and the "fastboot" label

    def __init__(self, opts):
        self.opts = opts

    def logo(self, u):
        raise NotImplementedError

    def fastboot(self, u):
        """Element for the fastboot screen: the logo, smaller, over a 'fastboot' label."""
        icon = self.logo(u * 0.7)
        label = text_element("fastboot", "mono", 58 * u, self.accent)
        gap = self.fastboot_gap * u
        w = max(icon.width, label.width)
        out = Image.new("RGBA", (w, int(icon.height + gap + label.height)), (0, 0, 0, 0))
        out.paste(icon, ((w - icon.width) // 2, 0), icon)
        out.paste(label, ((w - label.width) // 2, int(icon.height + gap)), label)
        return out


class Terminal(Design):
    name, about = "terminal", "White tile with a black prompt"

    def logo(self, u):
        return prompt_tile(236 * u, fill=WHITE, fg=(0, 0, 0, 255))


class TerminalGreen(Design):
    name, about, accent = "terminal-green", "Dark tile with a green prompt (default)", GREEN

    def logo(self, u):
        return prompt_tile(236 * u, fill=(24, 24, 27, 255), fg=GREEN, outline=(80, 80, 88, 255), outline_w=3 * u)


class Outline(Design):
    name, about = "outline", "Thin white outline, light and minimal"

    def logo(self, u):
        return prompt_tile(236 * u, outline=WHITE, outline_w=7 * u, fg=WHITE, stroke=0.06)


class Gradient(Design):
    name, about, accent = "gradient", "Blue-violet gradient tile, white prompt", (120, 190, 255, 255)

    def logo(self, u):
        return prompt_tile(236 * u, gradient=((106, 92, 255), (0, 194, 255)), fg=WHITE)


class Amber(Design):
    name, about, accent = "amber", "Glowing amber prompt, like an old terminal", AMBER
    fastboot_gap = -40  # the glow leaves room around the prompt already

    def logo(self, u):
        return prompt_tile(300 * u, fg=AMBER, stroke=0.075, glow=True)


class Console(Design):
    name, about = "console", "A console login prompt with a cursor"

    def logo(self, u):
        return console_line([(self.opts.text or "linux login:", LIGHT)], 64 * u, cursor=LIGHT)

    def fastboot(self, u):
        return console_line([("fastboot", LIGHT)], 64 * u, cursor=LIGHT)


class Status(Design):
    name, about, accent = "status", "A boot status line: [  OK  ] Booting Linux", GREEN

    def logo(self, u):
        return console_line([("[  ", LIGHT), ("OK", GREEN), ("  ] ", LIGHT),
                             (self.opts.text or "Booting Linux", LIGHT)], 52 * u)

    def fastboot(self, u):
        return console_line([("[ ", LIGHT), ("WAIT", AMBER), (" ] ", LIGHT), ("Fastboot mode", LIGHT)], 52 * u)


class Picture(Design):
    name, about = "picture", "Your own picture (--image)"

    def logo(self, u):
        pic = Image.open(self.opts.image).convert("RGBA")
        box = 520 * u
        scale = min(box / pic.width, box / pic.height)
        return pic.resize((max(1, int(pic.width * scale)), max(1, int(pic.height * scale))), Image.LANCZOS)


DESIGNS = {d.name: d for d in (TerminalGreen, Terminal, Outline, Gradient, Amber, Console, Status)}
DEFAULT_DESIGN = "terminal-green"


def footer_element(u, word):
    small = text_element("Powered by", "regular", 22 * u, (200, 200, 200, 255), pad=0.1)
    big = text_element(word, "semibold", 40 * u, WHITE, pad=0.1)
    w = max(small.width, big.width)
    gap = 4 * u
    out = Image.new("RGBA", (w, int(small.height + gap + big.height)), (0, 0, 0, 0))
    out.paste(small, ((w - small.width) // 2, 0), small)
    out.paste(big, ((w - big.width) // 2, int(small.height + gap)), big)
    return out


def padlock(u, color=(160, 160, 160, 255)):
    """A plain open padlock, for --redraw-padlock."""
    def fn(c, d, s):
        k = u * s
        sw = 4 * k
        # shackle, open on the right
        d.arc([10 * k, 2 * k, 34 * k, 26 * k], 180, 360, fill=color, width=int(sw))
        d.line([(10 * k, 14 * k), (10 * k, 24 * k)], fill=color, width=int(sw))
        # body
        d.rounded_rectangle([4 * k, 22 * k, 30 * k, 46 * k], radius=4 * k, outline=color, width=int(sw))
    return element(48 * u, 50 * u, fn)


def error_element(u):
    def tri(c, d, s):
        k = u * s
        d.regular_polygon((60 * k, 70 * k, 62 * k), 3, fill=(229, 57, 53, 255))
        d.rounded_rectangle([55 * k, 40 * k, 65 * k, 78 * k], radius=5 * k, fill=WHITE)
        d.ellipse([54.5 * k, 84 * k, 65.5 * k, 95 * k], fill=WHITE)
    t = element(120 * u, 112 * u, tri)
    l1 = text_element("The system can't start", "semibold", 42 * u, WHITE, pad=0.1)
    l2 = text_element("Press the power button to turn the phone off", "regular", 28 * u, (170, 170, 170, 255), pad=0.1)
    w = max(t.width, l1.width, l2.width)
    out = Image.new("RGBA", (w, int(t.height + l1.height + l2.height + 50 * u)), (0, 0, 0, 0))
    out.paste(t, ((w - t.width) // 2, 0), t)
    out.paste(l1, ((w - l1.width) // 2, int(t.height + 36 * u)), l1)
    out.paste(l2, ((w - l2.width) // 2, int(t.height + 36 * u + l1.height + 14 * u)), l2)
    return out


def background(image):
    return image.getpixel((2, image.height // 2))


def render(image, role, layout, design, opts):
    """New picture for a slot."""
    w, h = image.size
    u = w / 1080
    bg = background(image)
    out = image.copy()
    d = ImageDraw.Draw(out)
    if role == "logo":
        x0, y0, x1, y1 = layout["logo"]
        m = 14 * u
        d.rectangle([0, y0 - m, w, y1 + m], fill=bg)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if layout["footer"]:
            fx0, fy0, fx1, fy1 = layout["footer"]
            d.rectangle([0, fy0 - m, w, fy1 + m], fill=bg)
            fcy = (fy0 + fy1) / 2
        else:
            fcy = h * 0.914
        if opts.redraw_padlock:
            for b in layout["top"]:
                d.rectangle([0, b[1] - m, w, b[3] + m], fill=bg)
                paste_center(out, padlock(u), (b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
        paste_center(out, design.logo(u), cx, cy)
        if opts.footer:
            paste_center(out, footer_element(u, opts.footer), w / 2, fcy)
    elif role == "fastboot":
        d.rectangle([0, 0, w, h], fill=bg)
        cy = (layout["logo"][1] + layout["logo"][3]) / 2 if layout.get("logo") else h * 0.48
        paste_center(out, design.fastboot(u), w / 2, cy)
    elif role == "error":
        d.rectangle([0, 0, w, h], fill=bg)
        paste_center(out, error_element(u), w / 2, h * 0.47)
    return out


# --------------------------------------------------------------------------
# Building a new partition image

def plan(data, opts, quiet=False):
    """Find and classify the pictures; apply --logo/--fastboot/--error/--keep."""
    slots = find_slots(data)
    if not slots:
        die("no BMP pictures found; is this a Xiaomi logo partition?")
    forced = {}
    for role, nums in (("logo", opts.logo), ("fastboot", opts.fastboot), ("error", opts.error)):
        for n in nums or []:
            forced[n] = role
    for s in slots:
        role, layout = classify(decode(data, s))
        if s.index in forced:
            role = forced[s.index]
            if role == "logo" and not layout["logo"]:
                die(f"picture #{s.index} has no single centred logo to replace")
        if s.index in (opts.keep or []):
            role = None
        if role == "fastboot" and opts.keep_fastboot:
            role = None
        if role == "error" and opts.keep_error:
            role = None
        s.role, s.layout = role, layout
    if not quiet:
        for s in slots:
            what = {"logo": "boot logo" + (" (unlocked)" if s.layout["top"] else ""),
                    "fastboot": "fastboot screen", "error": "error screen"}.get(s.role, "kept as it is")
            print(f"  #{s.index}  0x{s.offset:08x}  {s.width}x{abs(s.height)}  {what}")
    return slots


def build(data, opts, preview_dir=None, quiet=False):
    """Return (new partition bytes, changed slots)."""
    design_cls = Picture if opts.image else DESIGNS[opts.design]
    design = design_cls(opts)
    slots = plan(data, opts, quiet)
    out = bytearray(data)
    changed = []
    for s in slots:
        img = decode(data, s)
        new = render(img, s.role, s.layout, design, opts) if s.role else img
        if s.role:
            blob = encode(data[s.offset:s.offset + s.size], new)
            if blob != data[s.offset:s.offset + s.size]:
                out[s.offset:s.offset + s.size] = blob
                changed.append(s)
        if preview_dir:
            os.makedirs(preview_dir, exist_ok=True)
            new.save(os.path.join(preview_dir, f"{s.index:02d}-{s.role or 'kept'}.png"))
    if preview_dir:
        thumbs = [Image.open(os.path.join(preview_dir, f"{s.index:02d}-{s.role or 'kept'}.png")) for s in slots]
        tw = 216
        sheet = Image.new("RGB", ((tw + 12) * len(thumbs) + 12, int(tw * 2340 / 1080) + 24), (120, 120, 120))
        for i, t in enumerate(thumbs):
            t = t.resize((tw, int(tw * t.height / t.width)), Image.LANCZOS)
            sheet.paste(t, (12 + i * (tw + 12), 12))
        sheet.save(os.path.join(preview_dir, "overview.png"))
    return bytes(out), changed


# --------------------------------------------------------------------------
# On the phone (Linux)

def phone_partitions():
    base = "/dev/disk/by-partlabel"
    if os.path.exists(f"{base}/logo"):
        return [f"{base}/logo"]
    found = [f"{base}/{p}" for p in ("logo_a", "logo_b") if os.path.exists(f"{base}/{p}")]
    if not found:
        die("no logo partition found (looked for logo, logo_a and logo_b)")
    return found


def partition_size(dev):
    dev = os.path.realpath(dev)
    if os.path.isfile(dev):
        return os.path.getsize(dev)
    with open(f"/sys/class/block/{os.path.basename(dev)}/size") as f:
        return int(f.read()) * 512


def user_home():
    name = os.environ.get("SUDO_USER")
    if name:
        pw = pwd.getpwnam(name)
        return pw.pw_dir, pw.pw_uid, pw.pw_gid
    return os.path.expanduser("~"), os.getuid(), os.getgid()


def write_verified(dev, offset, blob):
    with open(dev, "r+b", buffering=0) as f:
        f.seek(offset)
        f.write(blob)
        os.fsync(f.fileno())
    with open(dev, "rb", buffering=0) as f:
        os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
        f.seek(offset)
        if f.read(len(blob)) != blob:
            die(f"read-back of {dev} at 0x{offset:x} does not match; run 'restore'")


def cmd_install(opts):
    if os.geteuid() != 0:
        die("run it as root (sudo)")
    home, uid, gid = user_home()
    for part in phone_partitions():
        dev = os.path.realpath(part)
        name = os.path.basename(part)
        with open(dev, "rb") as f:
            current = f.read()
        backup = os.path.join(home, f"{name}-original.img")
        if os.path.exists(backup):
            # Always draw on the original pictures, so changing designs never
            # builds on an earlier result
            with open(backup, "rb") as f:
                original = f.read()
            if len(original) != len(current):
                die(f"{backup} is not the size of the {name} partition")
            print(f"{name} (drawing on the original saved in {backup}):")
        else:
            original = current
            print(f"{name}:")
        new, _ = build(original, opts)
        todo = [s for s in find_slots(new) if new[s.offset:s.offset + s.size] != current[s.offset:s.offset + s.size]]
        if not todo:
            print("  already up to date")
            continue
        if not os.path.exists(backup):
            with open(backup, "wb") as f:
                f.write(current)
            os.chown(backup, uid, gid)
            print(f"  saved the original to {backup}")
        for s in todo:
            write_verified(dev, s.offset, new[s.offset:s.offset + s.size])
        print(f"  {len(todo)} pictures written and verified")
    print("Done. The new logo shows at the next restart.")


def cmd_restore(opts):
    if os.geteuid() != 0:
        die("run it as root (sudo)")
    home, _, _ = user_home()
    for part in phone_partitions():
        dev = os.path.realpath(part)
        name = os.path.basename(part)
        backup = opts.backup or os.path.join(home, f"{name}-original.img")
        if not os.path.exists(backup):
            die(f"no backup at {backup}")
        with open(backup, "rb") as f:
            data = f.read()
        if len(data) != partition_size(dev) or not find_slots(data):
            die(f"{backup} does not match the {name} partition; not writing it")
        write_verified(dev, 0, data)
        print(f"{name}: restored from {backup}")


# --------------------------------------------------------------------------
# Magisk / KernelSU module

UPDATE_BINARY = """#!/sbin/sh
umask 022
ui_print() { echo "$1"; }
OUTFD=$2
ZIPFILE=$3
mount /data 2>/dev/null
[ -f /data/adb/magisk/util_functions.sh ] || { ui_print "Install this from the Magisk app"; exit 1; }
. /data/adb/magisk/util_functions.sh
install_module
exit 0
"""

CUSTOMIZE = r"""# xiaomi-logo-changer: writes new pictures into the logo partition.
# The original partition is saved first; removing the module restores it.
SKIPUNZIP=0
BK=/data/adb/xiaomi-logo-changer

find_part() {
  for d in /dev/block/by-name /dev/block/bootdevice/by-name; do
    for p in logo logo$(getprop ro.boot.slot_suffix); do
      [ -e "$d/$p" ] && { echo "$d/$p"; return; }
    done
  done
}

BLK=$(find_part)
[ -n "$BLK" ] || abort "! No logo partition found"
ui_print "- Logo partition: $BLK"

# Every slot must hold a picture of the expected size and format
while read -r off file len head; do
  [ -z "$off" ] && continue
  cur=$(dd if="$BLK" bs=1 skip="$off" count=30 2>/dev/null | od -An -tx1 | tr -d ' \n')
  [ "$cur" = "$head" ] || abort "! The logo partition is laid out differently on this phone; nothing was changed"
done < "$MODPATH/logo/slots.txt"

mkdir -p "$BK"
if [ ! -f "$BK/logo-original.img" ]; then
  dd if="$BLK" of="$BK/logo-original.img" bs=1048576 2>/dev/null || abort "! Could not save the original"
  ui_print "- Saved the original to $BK/logo-original.img"
fi
echo "$BLK" > "$BK/partition"

while read -r off file len head; do
  [ -z "$off" ] && continue
  dd if="$MODPATH/logo/$file" of="$BLK" bs=4096 seek=$((off / 4096)) conv=notrunc 2>/dev/null \
    || abort "! Writing $file failed; remove the module to restore the original"
  want=$(sha256sum "$MODPATH/logo/$file" | cut -d' ' -f1)
  got=$(dd if="$BLK" bs=4096 skip=$((off / 4096)) count=$(( (len + 4095) / 4096 )) 2>/dev/null | head -c "$len" | sha256sum | cut -d' ' -f1)
  [ "$want" = "$got" ] || abort "! $file did not verify; remove the module to restore the original"
  ui_print "- Wrote $file"
done < "$MODPATH/logo/slots.txt"

rm -f "$MODPATH"/logo/*.bmp
touch "$MODPATH/skip_mount"
ui_print "- Done. The new logo shows at the next restart."
ui_print "  Removing this module puts the original back."
"""

UNINSTALL = """# Put the original logo partition back
BK=/data/adb/xiaomi-logo-changer
[ -f "$BK/logo-original.img" ] && [ -f "$BK/partition" ] && \\
  dd if="$BK/logo-original.img" of="$(cat "$BK/partition")" bs=1048576 2>/dev/null && \\
  rm -rf "$BK"
"""


def cmd_module(opts):
    data = read_source(opts.source)
    new, changed = build(data, opts)
    if not changed:
        die("nothing to change")
    for s in changed:
        if s.offset % 4096:
            die(f"picture #{s.index} is not 4 KiB aligned; use the fastboot route for this phone")
    design = "picture" if opts.image else opts.design
    prop = (f"id=xiaomi-logo-changer\nname=Xiaomi logo changer ({design})\nversion=v{VERSION}\n"
            f"versionCode=1\nauthor=xiaomi-logo-changer\n"
            f"description=Replaces the boot logo{', fastboot and error screens' if any(s.role != 'logo' for s in changed) else ''}. "
            f"Remove the module to restore the original.\n")
    lines = []
    with zipfile.ZipFile(opts.output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("META-INF/com/google/android/update-binary", UPDATE_BINARY)
        z.writestr("META-INF/com/google/android/updater-script", "#MAGISK\n")
        z.writestr("module.prop", prop)
        z.writestr("customize.sh", CUSTOMIZE)
        z.writestr("uninstall.sh", UNINSTALL)
        for s in changed:
            blob = new[s.offset:s.offset + s.size]
            file = f"slot{s.index:02d}.bmp"
            z.writestr(f"logo/{file}", blob)
            lines.append(f"{s.offset} {file} {s.size} {data[s.offset:s.offset + 30].hex()}")
        z.writestr("logo/slots.txt", "\n".join(lines) + "\n")
    print(f"Wrote {opts.output} ({os.path.getsize(opts.output) // 1024} KiB). "
          "Install it from the Magisk or KernelSU app, then restart.")


# --------------------------------------------------------------------------
# Commands for files and adb

def read_source(src):
    if src in (None, "phone"):
        part = phone_partitions()[0]
        with open(os.path.realpath(part), "rb") as f:
            return f.read()
    if not os.path.exists(src):
        die(f"{src} not found")
    with open(src, "rb") as f:
        return f.read()


def cmd_extract(opts):
    data = read_source(opts.source)
    out = opts.output or "logo-pictures"
    os.makedirs(out, exist_ok=True)
    slots = plan(data, opts)
    for s in slots:
        decode(data, s).save(os.path.join(out, f"{s.index:02d}-at-0x{s.offset:x}.png"))
    print(f"{len(slots)} pictures saved to {out}/")


def cmd_build(opts):
    data = read_source(opts.source)
    preview = opts.preview or os.path.splitext(opts.output)[0] + "-preview"
    new, changed = build(data, opts, preview_dir=preview)
    with open(opts.output, "wb") as f:
        f.write(new)
    print(f"Wrote {opts.output}: {len(changed)} pictures changed. Previews in {preview}/")
    print(f"Flash it from fastboot mode with:  fastboot flash logo {opts.output}")


def adb(*args, binary=False):
    r = subprocess.run(["adb", *args], capture_output=True)
    if r.returncode:
        die(f"adb {' '.join(args)} failed: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout if binary else r.stdout.decode(errors="replace").strip()


def cmd_pull(opts):
    if not shutil.which("adb"):
        die("adb not found (Android platform tools)")
    find = ("for d in /dev/block/by-name /dev/block/bootdevice/by-name; do "
            "for p in logo logo$(getprop ro.boot.slot_suffix); do "
            "[ -e $d/$p ] && { echo $d/$p; exit; }; done; done")
    part = adb("shell", f"su -c '{find}'")
    if not part.startswith("/dev/"):
        die("no logo partition found, or no root (su) on the phone")
    tmp = "/data/local/tmp/logo-pull.img"
    adb("shell", f"su -c 'dd if={part} of={tmp} && chmod 644 {tmp}'")
    adb("pull", tmp, opts.output)
    adb("shell", f"su -c 'rm -f {tmp}'")
    print(f"Saved {part} to {opts.output}")


def cmd_designs(opts):
    for name, d in DESIGNS.items():
        print(f"  {name:15} {d.about}")
    print(f"  {'(--image FILE)':15} {Picture.about}")


def main():
    p = argparse.ArgumentParser(prog="logo_changer.py", description="Replace the boot logo of a Xiaomi phone.")
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="cmd", required=True)

    def design_opts(sp):
        sp.add_argument("--design", choices=list(DESIGNS), default=DEFAULT_DESIGN)
        sp.add_argument("--image", help="use your own picture (PNG/JPEG) instead of a design")
        sp.add_argument("--text", help="text for the console and status designs")
        sp.add_argument("--footer", default="Linux", help='word under "Powered by" (empty: no footer)')
        sp.add_argument("--redraw-padlock", action="store_true", help="draw a new unlocked padlock instead of keeping the phone's")
        sp.add_argument("--keep-fastboot", action="store_true", help="leave the fastboot screen as it is")
        sp.add_argument("--keep-error", action="store_true", help="leave the error screen as it is")
        sp.add_argument("--logo", type=int, nargs="+", metavar="N", help="treat picture N as a boot logo")
        sp.add_argument("--fastboot", type=int, nargs="+", metavar="N", help="treat picture N as the fastboot screen")
        sp.add_argument("--error", type=int, nargs="+", metavar="N", help="treat picture N as the error screen")
        sp.add_argument("--keep", type=int, nargs="+", metavar="N", help="leave picture N as it is")

    sub.add_parser("designs", help="list the designs").set_defaults(fn=cmd_designs)
    sp = sub.add_parser("extract", help="save the pictures of a logo image as PNG")
    sp.add_argument("source", nargs="?", help="logo.img (default: this phone's partition)")
    sp.add_argument("-o", "--output", help="folder (default: logo-pictures)")
    design_opts(sp)
    sp.set_defaults(fn=cmd_extract)
    sp = sub.add_parser("build", help="write a new logo image, to flash with fastboot")
    sp.add_argument("source", help="the original logo.img")
    sp.add_argument("-o", "--output", required=True)
    sp.add_argument("--preview", help="folder for previews (default: <output>-preview)")
    design_opts(sp)
    sp.set_defaults(fn=cmd_build)
    sp = sub.add_parser("module", help="make a Magisk / KernelSU module")
    sp.add_argument("source", help="the original logo.img")
    sp.add_argument("-o", "--output", required=True)
    design_opts(sp)
    sp.set_defaults(fn=cmd_module)
    sp = sub.add_parser("pull", help="copy the logo partition off a rooted Android phone with adb")
    sp.add_argument("-o", "--output", default="logo.img")
    sp.set_defaults(fn=cmd_pull)
    sp = sub.add_parser("install", help="on the phone under Linux: replace the logo (as root)")
    design_opts(sp)
    sp.set_defaults(fn=cmd_install)
    sp = sub.add_parser("restore", help="on the phone under Linux: put the original back (as root)")
    sp.add_argument("--backup", help="backup file (default: ~/logo-original.img)")
    sp.set_defaults(fn=cmd_restore)

    opts = p.parse_args()
    if getattr(opts, "image", None) and not os.path.exists(opts.image):
        die(f"{opts.image} not found")
    opts.fn(opts)


if __name__ == "__main__":
    main()
