# Getting Started

[中文](GETTING_STARTED_ZH.md)

This guide describes the shortest path from a fresh checkout to a running
ESP-IDF example on the ESP32-P4-WIFI6-Touch-LCD-XC board.

## Requirements

- ESP-IDF `v5.5.5` or `v6.0.2`, which are the two versions covered by the
  repository's example CI matrix.
- Python and Git as required by ESP-IDF.
- USB-C cable connected to the board USB-UART port.
- Optional peripherals required by the selected example, such as an SD card or
  camera module.

The board schematic is available at
[`hardware/schematics/ESP32-P4-WIFI6-Touch-LCD-XC-Schematic.pdf`](../hardware/schematics/ESP32-P4-WIFI6-Touch-LCD-XC-Schematic.pdf).
Use the [hardware audit](HARDWARE.md) together with the schematic when a
change touches board pins, display, touch, camera, audio, storage, or USB.

## Build An ESP-IDF Example

Start with the basic hello world example:

```bash
cd examples/esp-idf/02_HelloWorld
idf.py set-target esp32p4
idf.py build
```

Flash and monitor the board:

```bash
idf.py -p PORT flash monitor
```

Replace `PORT` with your serial port. Use `Ctrl-]` to exit the ESP-IDF serial
monitor.

## Build Other Projects

Every first-party example in this repository has its own `CMakeLists.txt` and
`main/` directory. The default example root is:

- `examples/esp-idf/<example>`

The maintained `firmware/` source tree is a separate delivery surface. It is
not part of the default example CI matrix; it uses only rev3.x `3_4c` and `4c`
profiles. See [Firmware Source Boundary](FIRMWARE.md) before changing it.

Use the same commands from inside the project directory, or use ESP-IDF's
project path option:

```bash
idf.py -C examples/esp-idf/08_lvgl_demo_v9 set-target esp32p4 build
```

## Configure Examples

Run `idf.py menuconfig` before building examples that require:

- Wi-Fi SSID and password.
- SD card filenames or media playback options.
- Display, touch, LVGL, camera, USB, or audio settings.
- Board-specific hardware options.

Commit shared defaults in `sdkconfig.defaults` or `sdkconfig.ci*` files. Do not
commit local `sdkconfig`, `build/`, `managed_components/`, or
`dependencies.lock` outputs.

## Arduino Notes

Arduino information is maintained in
[examples/arduino/README.md](../examples/arduino/README.md), including the
recommended Arduino-ESP32 core, bundled LVGL library, Arduino_GFX dependency,
and I2C driver compatibility note.
