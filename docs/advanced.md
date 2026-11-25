---
hide:
  - navigation
---

# Advanced guide

For other Xiaomi phones, your own pictures, and everything the tool can do.

## Setup

You need Python 3.8 or newer and Pillow:

```sh
git clone https://github.com/miercolesv/xiaomi-logo-changer
cd xiaomi-logo-changer
pip install pillow
```

## Other Xiaomi phones

### 1. Get the original `logo.img`

Always start from the phone's **original** logo image, either:

- `images/logo.img` from the official fastboot ROM for your phone and system
  version. You don't need the whole ROM: `python3 logo_changer.py original
  --rom <link to the .tgz>` downloads only the start of it, where `logo.img`
  is. Or
- a copy of the partition from a rooted phone, with USB debugging on:

  ```sh
  python3 logo_changer.py pull -o logo.img
  ```

### 2. Build and preview

```sh
python3 logo_changer.py build logo.img -o logo-new.img --design amber
```

It prints what it thinks each picture is:

```
  #1  0x00005000  1080x2340  boot logo
  #2  0x00740000  1080x2340  fastboot screen
  #3  0x00e7b000  1080x2340  boot logo (unlocked)
  #4  0x015b6000  1080x2340  error screen
  ...
```

and writes previews to `logo-new-preview/`. **Open `overview.png` and check
every screen before flashing.** The tool was only tested on the Mi 10. If it
reads a picture wrongly, tell it what the picture is, using the numbers it
printed:

```sh
python3 logo_changer.py build logo.img -o logo-new.img --fastboot 2 --keep 4
```

### 3. Flash

```sh
fastboot flash logo logo-new.img
```

On A/B phones (with `logo_a` and `logo_b` partitions), flash both:
`fastboot flash logo_a logo-new.img` and `fastboot flash logo_b logo-new.img`.

Or make a module for a rooted phone instead:

```sh
python3 logo_changer.py module logo.img -o logo-module.zip --design amber
```

## Your own picture

```sh
python3 logo_changer.py build logo.img -o logo-new.img --image my-logo.png
```

The picture is scaled to fit a box about half the screen wide, centred where
the Mi logo was. PNGs with transparency work best. The fastboot screen gets a
smaller copy of it.

## All commands

| Command | What it does |
|---|---|
| `designs` | List the designs |
| `extract logo.img` | Save every picture as a PNG, without changing anything |
| `build logo.img -o new.img` | Write a new logo image, to flash with fastboot |
| `module logo.img -o logo.zip` | Make a Magisk / KernelSU module |
| `pull -o logo.img` | Copy the logo partition off a rooted Android phone (adb) |
| `original` | Download Xiaomi's original Mi 10 `logo.img` from the official ROM (only the first few hundred KB of it). `--rom URL` does the same for another phone's official fastboot ROM |
| `install` | On a phone running Linux: replace the screens (as root) |
| `restore` | On a phone running Linux: put the original back (as root) |

## All options

| Option | Effect |
|---|---|
| `--design NAME` | `terminal-green` (default), `terminal`, `outline`, `gradient`, `amber`, `console`, `status` |
| `--image FILE` | Your own picture instead of a design |
| `--os NAME` | `android` (default), `linux` (default for `install`) or `none`: sets "Powered by …" and the `console` / `status` text |
| `--text TEXT` | Text for `console` and `status`, e.g. `--text "mi10 login:"` |
| `--footer TEXT` | Word under "Powered by", overriding `--os` (`""` removes the line) |
| `--redraw-padlock` | Draw a new unlocked padlock instead of keeping the phone's |
| `--keep-fastboot`, `--keep-error` | Leave those screens as they are |
| `--logo N`, `--fastboot N`, `--error N`, `--keep N` | Say what picture N is |

## How it works

A Xiaomi `logo` partition has a small table at 16 KiB (it starts with
`LOGO!!!!`) and full-screen BMP pictures in fixed slots. On the Mi 10 there
are eight, at 1080×2340: the boot logo with and without the padlock (three
copies each), the fastboot screen and an error screen.

The tool finds every picture and works out what it shows from where its
bright areas are: a logo in the middle with a line of text near the bottom is
a boot logo; one wide orange line is the fastboot screen; a red sign with text
is the error screen. It then redraws the picture and writes it back in the
original's exact BMP format and size, so the table and the rest of the
partition stay exactly as they were.

## Inside the Magisk module

The module carries only the new pictures, plus a list of where each one goes
and what the start of the old picture at that spot looks like. When it's
installed, it:

1. finds the `logo` partition, and checks that every spot holds a picture of
   the expected size and format. If one doesn't, it stops without changing
   anything;
2. saves the whole partition to
   `/data/adb/xiaomi-logo-changer/logo-original.img`;
3. writes each picture and reads it back to check it.

When it's removed, it writes the saved copy back.

## Development

```sh
python3 -m unittest discover tests     # tests, on a made-up partition
python3 tools/make_gallery.py          # pictures for the README and this site
```

The tests and the pictures never use a real phone's artwork:
`tests/synthetic.py` builds a partition with the Mi 10's layout out of plain
shapes.
