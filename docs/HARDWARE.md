# Hardware Reference and Audit

[中文](HARDWARE_ZH.md)

This repository includes the board schematic at
[`hardware/schematics/ESP32-P4-WIFI6-Touch-LCD-XC-Schematic.pdf`](../hardware/schematics/ESP32-P4-WIFI6-Touch-LCD-XC-Schematic.pdf).
It is the primary local reference for changes involving pins, connectors, power,
display, touch, camera, audio, storage, USB, or the ESP32-C6 wireless module.

## Evidence in this repository

The two-page schematic contains the ESP32-P4 and ESP32-C6 sections, Type-C and
USB-UART/USB-OTG interfaces, microSD, CSI, the 3.4/4-inch display connector,
codec/ADC, microphone, speaker amplifier, reset/boot controls, and power rails.
The following maintained sources provide the software-side contract:

| Surface | Repository evidence |
| --- | --- |
| ESP-IDF board support | `examples/esp-idf/*/components/waveshare__esp32_p4_wifi6_touch_lcd_xc/` and its `idf_component.yml` |
| Display variants | BSP headers plus `BSP_LCD_TYPE_800_800_3_4_INCH` / `BSP_LCD_TYPE_720_720_4_INCH` configuration |
| Arduino display variants | `examples/arduino/libraries/displays/displays_config.h` and `CURRENT_SCREEN` in the first-party sketches |
| Arduino I2C/touch | `examples/arduino/libraries/displays/i2c.h` and `gt911.h` |
| Camera example | `examples/esp-idf/09_video_lcd_display/sdkconfig.defaults` and the local `esp_video` manifest |
| Hosted Wi-Fi | `examples/esp-idf/04_wifistation/main/idf_component.yml` |

The examples use GT911-compatible touch APIs. The repository intentionally does
not duplicate a complete pin table in this document: the schematic, BSP headers,
and Arduino configuration are the sources to update together when a board-facing
change is made.

## Audit rules for future changes

Before changing a hardware constant or board-facing README:

1. Identify the affected board interface in the schematic.
2. Compare the schematic net names with the BSP header, Arduino configuration,
   `sdkconfig.defaults`, and example source.
3. Check both display resolutions and both Arduino `CURRENT_SCREEN` variants when
   the change affects the display path.
4. Record whether validation is static (source/schematic) or includes a physical
   board test. A successful CI build proves compilation, not pin correctness.

The current repository work is documentation and CI scoped. It does not change
the board pin definitions or any delivered firmware artifact; hardware validation
for a future pin change still requires this schematic cross-check and, where
possible, a physical board test.
