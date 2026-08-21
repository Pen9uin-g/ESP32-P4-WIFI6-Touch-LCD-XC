# ESP-Brookesia Phone-Style UI Example

[中文](README_ZH.md)

This product-specific example runs an ESP-Brookesia phone-style interface on
the ESP32-P4-WIFI6-Touch-LCD-XC. It uses the local XC board-support component
and the repository's Brookesia integration, with the display resolution selected
by the board configuration.

## Hardware

- ESP32-P4-WIFI6-Touch-LCD-XC with either the 3.4C or 4C display;
- a USB-C cable connected to the board's USB-UART interface;
- any optional audio, storage, camera, or hosted-Wi-Fi peripherals enabled by
  the selected configuration.

Use the repository [hardware audit](../../../docs/HARDWARE.md) and
[board schematic](../../../hardware/schematics/ESP32-P4-WIFI6-Touch-LCD-XC-Schematic.pdf)
when changing display, touch, audio, storage, or coprocessor settings. This
example is not the 1024 × 600 ESP32-P4-Function-EV-Board example from the
upstream project.

## Configure, build, and flash

The checked-in default selects the 3.4C 800 × 800 display and the board's
32 MB NOR flash. Select **Board Support Package Configuration → LCD → Select
LCD type → 720 × 720 4-inch Display** for the 4C variant. Run
`idf.py menuconfig` to review the ESP-Brookesia and board settings, then:

```bash
idf.py set-target esp32p4
idf.py build
idf.py -p PORT flash monitor
```

Replace `PORT` with the board's serial port. Type `Ctrl-]` to exit the monitor.
The repository includes the product example integration and declares its
managed dependencies; a separate clone of the upstream example is not required
for this project build.

The example is included in the repository's ESP-IDF `v5.5.5` and `v6.0.2`
matrix for both the 3.4C and 4C display configurations. CI validates
compilation; it does not replace a physical display, touch, audio, or Wi-Fi
compatibility test.
