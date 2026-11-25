---
hide:
  - navigation
---

# Changed your mind?

No problem. Here's how to get the original screens back.

=== ":material-cellphone-cog: Magisk or KernelSU"

    Remove the module in the app and restart. The module saved the original
    when it was installed and writes it back when it's removed.

=== ":material-penguin: Linux"

    ```sh
    curl -sL https://raw.githubusercontent.com/miercolesv/xiaomi-logo-changer/main/logo_changer.py | sudo python3 - restore
    ```

    Then restart. It writes back `~/logo-original.img`, saved the first time.

=== ":material-laptop: Fastboot"

    Flash the original `logo.img`:

    1. Get the **official fastboot ROM** for your phone and system version from Xiaomi, and unzip it. `logo.img` is in its `images` folder. (Or use your own backup of the partition, if you have one.)

    2. In fastboot mode (++volume-down+power++ while the phone is off):

        ```sh
        fastboot flash logo logo.img
        fastboot reboot
        ```

!!! question "Something looks wrong?"
    The `logo` partition only holds pictures; the phone's software lives
    elsewhere. Even if a screen looks odd, fastboot mode should still work,
    and the fastboot steps above put the original back.
