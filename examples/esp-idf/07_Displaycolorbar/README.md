# Display Color Bar

[中文](README_ZH.md)

This example initializes the managed board display and shows a MIPI-DSI vertical
color bar. It supports ESP32-P4-WIFI6-Touch-LCD-XC 3.4C and 4C with ESP-IDF
`v5.5.5` and `v6.0.2`; the default is 3.4C (800 × 800).

## Configuration and run

Install a supported ESP-IDF environment and connect the board. Select the 4C
(720 × 720) BSP display type in `menuconfig` when required.

```bash
idf.py set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p PORT flash monitor
```

CI builds explicit 3.4C and 4C overlays on both ESP-IDF lines. A successful
build does not prove panel operation on hardware.

See [Getting Started](../../../docs/GETTING_STARTED.md),
[Hardware Audit](../../../docs/HARDWARE.md), and [CI](../../../docs/CI.md).
