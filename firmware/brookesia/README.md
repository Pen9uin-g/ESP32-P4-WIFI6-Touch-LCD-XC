# ESP32-P4-WIFI6-Touch-LCD-XC ESP-Brookesia Firmware

[中文](README_ZH.md)

Default firmware source for the ESP32-P4-WIFI6-Touch-LCD-3.4C and -4C boards. It keeps the Brookesia phone launcher and bundled applications, including Wi-Fi through ESP-Hosted, camera, audio, music, video, drawing, spectrum analysis, settings, and Xiaozhi.

## Requirements

- ESP-IDF v5.5.5
- ESP32-P4 Rev3.x only

## Display variants

| Variant | Panel | MIPI-DSI lanes | Lane rate | DPI clock |
| --- | --- | ---: | ---: | ---: |
| `3_4c` | 3.4 inch, 800 x 800 | 2 | 1500 Mbps | 80 MHz |
| `4c` | 4 inch, 720 x 720 | 2 | 1500 Mbps | 80 MHz |

The released XC BSP sets `phy_clk_src = 0`. ESP-IDF selects the compatible PHY clock source from the chip's minimum revision, so this firmware sets Rev3.x directly in its base defaults; it does not select the pre-v3 clock path.

## Touch initialization

GT911 INT and RST are NC for this firmware. The BSP probes I2C address `0x5D`
and then `0x14`, creates panel IO with the detected address, and reads touch
data by polling. Do not add an INT/RST address-selection sequence unless the
hardware contract changes separately.

## Build

Run one command from this directory after exporting ESP-IDF v5.5.5:

```bash
idf.py -B build-3_4c-v5.5.5-rev3_x -D SDKCONFIG="$PWD/build-3_4c-v5.5.5-rev3_x/sdkconfig" -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.rev3_x;sdkconfig.defaults.3_4c" build
idf.py -B build-4c-v5.5.5-rev3_x -D SDKCONFIG="$PWD/build-4c-v5.5.5-rev3_x/sdkconfig" -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.rev3_x;sdkconfig.defaults.4c" build
```

The application binary is named `esp32-p4-lcd-xc-brookesia.bin`.

## Merge factory images

Run the matching command after a successful build. Each command creates a 16 MiB image that is ready to flash at offset `0x0`:

```bash
(cd build-3_4c-v5.5.5-rev3_x && python -m esptool --chip esp32p4 merge_bin -o ../../ESP32-P4-WIFI6-Touch-LCD-3.4C-FactoryOnly-260821.bin @flash_args)
(cd build-4c-v5.5.5-rev3_x && python -m esptool --chip esp32p4 merge_bin -o ../../ESP32-P4-WIFI6-Touch-LCD-4C-FactoryOnly-260821.bin @flash_args)
```
