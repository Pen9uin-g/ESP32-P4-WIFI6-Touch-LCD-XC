# LVGL 9 Demo

[中文](README_ZH.md)

This LVGL 9 example starts the managed display, enables its backlight, and runs
the LVGL widgets demo. It supports ESP32-P4-WIFI6-Touch-LCD-XC 3.4C and 4C with
ESP-IDF `v5.5.5` and `v6.0.2`.

## Configuration and run

Install a supported ESP-IDF environment and select the matching BSP display type
in `menuconfig` before building.

```bash
idf.py set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p PORT flash monitor
```

CI compiles explicit 3.4C and 4C variants on both ESP-IDF lines. The published
BSP `3.0.1` leaves touch RST and INT unconfigured, probes `0x5D` then `0x14`,
and uses polling without an ISR. Compile coverage is not touch HIL; the
responding address, coordinates, release events, and polling still require real
3.4C and 4C validation.

See [Getting Started](../../../docs/GETTING_STARTED.md),
[Component Ownership](../../../docs/COMPONENTS.md),
[Hardware Audit](../../../docs/HARDWARE.md), and [CI](../../../docs/CI.md).
