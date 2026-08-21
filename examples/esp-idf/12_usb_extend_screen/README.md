# USB Extended Screen

[中文](README_ZH.md)

This ESP32-P4-WIFI6-Touch-LCD-XC 3.4C/4C example uses USB OTG device mode only
and supports ESP-IDF `v5.5.5` and `v6.0.2`. Its default configuration enables
vendor transport, HID touch reports, and UAC audio.

## Configuration and run

Connect the USB OTG interface as a device and select the matching display type
in `menuconfig` before building. This repository does not include a PC sender or
client implementation.

```bash
idf.py set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p PORT flash monitor
```

CI builds both displays on both ESP-IDF lines for default and CI-only
`vendor-only` configurations. Vendor-only disables HID touch and UAC audio and
omits the managed UAC component; it is not the normal-device configuration.
Build coverage does not replace USB, display, touch, or audio HIL.

See [Getting Started](../../../docs/GETTING_STARTED.md),
[Component Ownership](../../../docs/COMPONENTS.md),
[Hardware Audit](../../../docs/HARDWARE.md), and [CI](../../../docs/CI.md).
