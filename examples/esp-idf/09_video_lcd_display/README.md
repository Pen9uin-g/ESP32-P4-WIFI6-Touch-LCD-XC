| Supported Targets | ESP32-P4 |
| ----------------- | -------- |

# Camera-to-LCD Video Example

[中文](README_ZH.md)

This example uses the Waveshare board-support component and Espressif's
`esp_video` component to capture frames from a MIPI-CSI camera and display them
on the round MIPI-DSI LCD of the ESP32-P4-WIFI6-Touch-LCD-XC.

## Hardware

- ESP32-P4-WIFI6-Touch-LCD-XC board with the 3.4C or 4C display;
- a compatible MIPI-CSI camera module. The checked-in default configuration
  selects the OV5647 RAW8 camera path;
- a USB-C cable connected to the board's USB-UART interface.

Do not copy the pin table from another ESP32-P4 board. Use the repository
[hardware audit](../../../docs/HARDWARE.md) and
[board schematic](../../../hardware/schematics/ESP32-P4-WIFI6-Touch-LCD-XC-Schematic.pdf)
when changing camera, display, reset, or power configuration.

## Configure

The default `sdkconfig.defaults` selects an OV5647 MIPI camera format. Run
`idf.py menuconfig` to review the camera sensor and display options before
building a different camera or display variant.

## Build and flash

```bash
idf.py set-target esp32p4
idf.py build
idf.py -p PORT flash monitor
```

Replace `PORT` with the board's serial port. Type `Ctrl-]` to exit the monitor.
The first build may download registry components into the ignored
`managed_components/` directory.

## Dependencies and validation

The project manifest declares `esp_video` and the Waveshare XC BSP. The example
is included in the repository's ESP-IDF `v5.5.5` and `v6.0.2` example matrix.
CI proves that the selected source/configuration compiles; it does not replace
a physical camera/display test.
