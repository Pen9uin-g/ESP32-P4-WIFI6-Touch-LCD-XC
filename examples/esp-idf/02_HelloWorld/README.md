# Hello World

[中文](README_ZH.md)

This peripheral-free ESP-IDF example prints chip information, counts down, and
restarts. It supports the ESP32-P4-WIFI6-Touch-LCD-XC 3.4C and 4C variants with
ESP-IDF `v5.5.5` and `v6.0.2`.

## Build and run

Install a supported ESP-IDF environment and connect the board; no board
peripheral setup is required.

```bash
idf.py set-target esp32p4
idf.py build
idf.py -p PORT flash monitor
```

CI compiles the shared/default configuration on both ESP-IDF lines. It does not
exercise display, touch, storage, audio, or wireless hardware.

See [Getting Started](../../../docs/GETTING_STARTED.md), the
[Examples guide](../../README.md), and [CI](../../../docs/CI.md).
