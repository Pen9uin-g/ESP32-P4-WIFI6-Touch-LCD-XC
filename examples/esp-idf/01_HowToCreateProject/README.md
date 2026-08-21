# Minimal ESP-IDF Project

[中文](README_ZH.md)

This peripheral-free starting project contains an empty `app_main`. It supports
the ESP32-P4-WIFI6-Touch-LCD-XC 3.4C and 4C variants with ESP-IDF `v5.5.5` and
`v6.0.2`.

## Build and run

Install a supported ESP-IDF environment and connect the board; no project
peripheral configuration is required.

```bash
idf.py set-target esp32p4
idf.py build
idf.py -p PORT flash monitor
```

CI compiles the shared/default configuration on both ESP-IDF lines. It has no
display, touch, storage, audio, or wireless behavior to validate.

See the [Getting Started guide](../../../docs/GETTING_STARTED.md),
[Examples guide](../../README.md), and [CI guide](../../../docs/CI.md).
