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

    You need Xiaomi's original `logo.img`. These commands take it straight
    from Xiaomi's official Mi 10 ROM, downloading only the first couple of MB
    instead of the whole 5.5 GB. On Windows, type `curl.exe` instead of `curl`
    and `python` instead of `python3`.

    **With Python:**

    ```sh
    curl -sL https://raw.githubusercontent.com/miercolesv/xiaomi-logo-changer/main/logo_changer.py | python3 - original
    ```

    This saves `logo-original.img` and checks it's the right file.

    **Without Python** (works on Windows 10 and 11, macOS and Linux as they come):

    ```sh
    curl -r 0-2097151 -o part.tgz https://cdnorg.d.miui.com/V14.0.5.0.TJBMIXM/umi_global_images_V14.0.5.0.TJBMIXM_20230517.0000.00_13.0_global_c9af1b1404.tgz
    tar -xzf part.tgz umi_global_images_V14.0.5.0.TJBMIXM_13.0/images/logo.img
    ```

    `tar` ends with an "unexpected end" message. That's expected: only the
    start of the ROM was downloaded, and `logo.img` is in it. The file is at
    `umi_global_images_V14.0.5.0.TJBMIXM_13.0/images/logo.img`.

    **Then flash it**, in fastboot mode (++volume-down+power++ while the phone
    is off):

    ```sh
    fastboot flash logo logo-original.img
    fastboot reboot
    ```

    (Use the path above instead of `logo-original.img` if you took the
    no-Python route.)

!!! question "Something looks wrong?"
    The `logo` partition only holds pictures; the phone's software lives
    elsewhere. Even if a screen looks odd, fastboot mode should still work,
    and the fastboot steps above put the original back.
