---
hide:
  - navigation
---

# Install on a Xiaomi Mi 10

These files are for the **Xiaomi Mi 10 (umi)**. Got another Xiaomi? Head to
the [advanced guide](advanced.md).

## Download your design

| Design | With a computer | Rooted phone |
|---|---|---|
| terminal-green (default) | [fastboot zip](https://github.com/miercolesv/xiaomi-logo-changer/releases/latest/download/mi10-terminal-green-fastboot.zip) | [Magisk / KernelSU zip](https://github.com/miercolesv/xiaomi-logo-changer/releases/latest/download/mi10-terminal-green-magisk.zip) |
| terminal | [fastboot zip](https://github.com/miercolesv/xiaomi-logo-changer/releases/latest/download/mi10-terminal-fastboot.zip) | [Magisk / KernelSU zip](https://github.com/miercolesv/xiaomi-logo-changer/releases/latest/download/mi10-terminal-magisk.zip) |
| outline | [fastboot zip](https://github.com/miercolesv/xiaomi-logo-changer/releases/latest/download/mi10-outline-fastboot.zip) | [Magisk / KernelSU zip](https://github.com/miercolesv/xiaomi-logo-changer/releases/latest/download/mi10-outline-magisk.zip) |
| gradient | [fastboot zip](https://github.com/miercolesv/xiaomi-logo-changer/releases/latest/download/mi10-gradient-fastboot.zip) | [Magisk / KernelSU zip](https://github.com/miercolesv/xiaomi-logo-changer/releases/latest/download/mi10-gradient-magisk.zip) |
| amber | [fastboot zip](https://github.com/miercolesv/xiaomi-logo-changer/releases/latest/download/mi10-amber-fastboot.zip) | [Magisk / KernelSU zip](https://github.com/miercolesv/xiaomi-logo-changer/releases/latest/download/mi10-amber-magisk.zip) |
| console | [fastboot zip](https://github.com/miercolesv/xiaomi-logo-changer/releases/latest/download/mi10-console-fastboot.zip) | [Magisk / KernelSU zip](https://github.com/miercolesv/xiaomi-logo-changer/releases/latest/download/mi10-console-magisk.zip) |
| status | [fastboot zip](https://github.com/miercolesv/xiaomi-logo-changer/releases/latest/download/mi10-status-fastboot.zip) | [Magisk / KernelSU zip](https://github.com/miercolesv/xiaomi-logo-changer/releases/latest/download/mi10-status-magisk.zip) |

Then follow the steps for your way of installing:

=== ":material-laptop: With a computer (fastboot)"

    !!! info "You'll need"
        - a computer with `fastboot` (Google's
          [platform tools](https://developer.android.com/tools/releases/platform-tools))
        - a USB cable
        - an **unlocked bootloader**

    1. Unzip the **fastboot zip**. Inside is `logo.img`.

    2. Turn the phone off. Then hold ++volume-down+power++ until the fastboot screen appears.

    3. Connect the phone, open a terminal in the folder with `logo.img`, and run:

        ```sh
        fastboot flash logo logo.img
        fastboot reboot
        ```

    4. The phone restarts with your new logo.

=== ":material-cellphone-cog: Rooted phone (Magisk or KernelSU)"

    !!! info "You'll need"
        - root with **Magisk** or **KernelSU**

    1. Download the **Magisk / KernelSU zip** on the phone.

    2. Open the Magisk or KernelSU app → **Modules** → **Install from storage**, and pick the zip.

    3. Restart the phone.

    !!! tip "Good to know"
        - Before writing anything, the module checks the phone looks like it
          expects. If not, it stops without changing anything.
        - Removing the module brings the original screens back.
        - To switch designs: remove the module, restart, install the new one.

=== ":material-penguin: On Linux"

    !!! info "You'll need"
        - Linux running on the phone (for example
          [Arch Linux ARM on the Mi 10](https://github.com/miercolesvd/mi10-arch-linux))
        - Python's Pillow: `sudo pacman -S python-pillow` (or your distribution's package)

    1. Run, on the phone:

        ```sh
        curl -sL https://raw.githubusercontent.com/miercolesv/xiaomi-logo-changer/main/logo_changer.py | sudo python3 - install --design terminal-green
        ```

        Swap `terminal-green` for any design name.

    2. Restart.

    !!! tip "Good to know"
        - The first run saves the original to `~/logo-original.img`.
        - To switch designs, just run it again with another name.
