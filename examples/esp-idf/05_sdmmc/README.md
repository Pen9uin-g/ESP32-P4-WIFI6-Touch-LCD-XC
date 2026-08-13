# SDMMC Card

[中文](README_ZH.md)

This SDMMC example supports ESP32-P4-WIFI6-Touch-LCD-XC 3.4C and 4C with
ESP-IDF `v5.5.5` and `v6.0.2`. Its P4 defaults are D0..D3 GPIO39..GPIO42,
CLK GPIO43, and CMD GPIO44; four-bit mode is the default.

## Configuration and run

Insert a compatible microSD card and use `menuconfig` to choose one- or
four-bit mode and optional diagnostics. Both format-on-mount-failure and
explicit card formatting are opt-in and default off.

```bash
idf.py set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p PORT flash monitor
```

CI compiles the shared/default configuration on both ESP-IDF lines; it does not
validate a card or authorize formatting media.

See [Getting Started](../../../docs/GETTING_STARTED.md),
[Hardware Audit](../../../docs/HARDWARE.md), and [CI](../../../docs/CI.md).
