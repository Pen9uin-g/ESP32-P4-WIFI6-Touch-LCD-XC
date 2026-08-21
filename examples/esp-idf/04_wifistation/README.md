# Wi-Fi Station

[中文](README_ZH.md)

This example connects as a Wi-Fi station through the board's ESP32-C6 Hosted
runtime dependency. It supports ESP32-P4-WIFI6-Touch-LCD-XC 3.4C and 4C with
ESP-IDF `v5.5.5` and `v6.0.2`.

## Configuration and run

Set the SSID and password in `idf.py menuconfig` before building. The manifest
selects `esp_wifi_remote` `0.14.*` and `esp_hosted` `1.4.*` for IDF below 6.0,
or remote `>=1.6,<2.0` and hosted `>=2.12,<3.0` for IDF 6.0 or later.

```bash
idf.py set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p PORT flash monitor
```

CI compiles the shared/default configuration on both ESP-IDF lines. The C6 image
is a runtime dependency; this repository does not identify its exact image,
version, hash, source, or build metadata. Widening either range requires that
exact metadata, both-IDF compilation, and real Wi-Fi HIL validation.

See [Getting Started](../../../docs/GETTING_STARTED.md),
[Component Ownership](../../../docs/COMPONENTS.md), and [CI](../../../docs/CI.md).
