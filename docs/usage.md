# Usage

```
logo_changer.py designs                         list the designs
logo_changer.py extract logo.img                save the pictures as PNG
logo_changer.py build logo.img -o new.img       new image for fastboot
logo_changer.py module logo.img -o logo.zip     Magisk / KernelSU module
logo_changer.py pull -o logo.img                copy the partition off a rooted phone (adb)
sudo logo_changer.py install                    on the phone, under Linux
sudo logo_changer.py restore                    on the phone, under Linux
```

Always start from the phone's *original* `logo.img`: the official fastboot
ROM's `images/logo.img`, or `pull` from a rooted phone.

## Options

| Option | Effect |
|---|---|
| `--design NAME` | `terminal-green` (default), `terminal`, `outline`, `gradient`, `amber`, `console`, `status` |
| `--image FILE` | Your own picture (PNG or JPEG) instead of a design |
| `--text TEXT` | Text for `console` and `status`, e.g. `--text "mi10 login:"` |
| `--footer TEXT` | Word under "Powered by" (default `Linux`; `""` removes it) |
| `--redraw-padlock` | Draw a new unlocked padlock instead of keeping the phone's |
| `--keep-fastboot`, `--keep-error` | Leave those screens as they are |
| `--logo N`, `--fastboot N`, `--error N`, `--keep N` | Say what picture N is, if it was read wrongly |

## Notes

- **A/B phones:** flash both `logo_a` and `logo_b`.
- **Magisk module:** checks every picture is where it expects before
  writing, and saves the original to
  `/data/adb/xiaomi-logo-changer/logo-original.img`. To switch designs,
  remove the module, restart, then install the other one.
- **Linux on the phone:** the first `install` saves the partition to
  `~/logo-original.img`, and later runs always draw on that, so switching
  designs is just another `install`.
- **Undo with fastboot:** flash `logo.img` from the official fastboot ROM.

## How it works

A Xiaomi `logo` partition has a small table (`LOGO!!!!`) and full-screen BMP
pictures in fixed slots: on the Mi 10, eight at 1080×2340 (the boot logo with
and without the padlock, three copies each, the fastboot screen and an error
screen). The tool works out what each picture shows from where its bright
areas are, redraws it, and writes it back in the original's exact format and
size. The table and the rest of the partition don't change.
