# Examples Guide

[中文](README_ZH.md)

This directory contains first-party ESP-IDF projects, Arduino notes and
bundled libraries for the
ESP32-P4-WIFI6-Touch-LCD-XC board.

## ESP-IDF Examples

| Path | Area |
| --- | --- |
| [`examples/esp-idf/01_HowToCreateProject`](esp-idf/01_HowToCreateProject/README.md) | Minimal ESP-IDF project layout |
| [`examples/esp-idf/02_HelloWorld`](esp-idf/02_HelloWorld/README.md) | Basic ESP-IDF application |
| [`examples/esp-idf/03_i2c_tools`](esp-idf/03_i2c_tools/README.md) | I2C scan and command tools |
| [`examples/esp-idf/04_wifistation`](esp-idf/04_wifistation/README.md) | Wi-Fi station connection |
| [`examples/esp-idf/05_sdmmc`](esp-idf/05_sdmmc/README.md) | SD card and SDMMC |
| [`examples/esp-idf/06_I2SCodec`](esp-idf/06_I2SCodec/README.md) | I2S audio codec |
| [`examples/esp-idf/07_Displaycolorbar`](esp-idf/07_Displaycolorbar/README.md) | LCD display color bar |
| [`examples/esp-idf/08_lvgl_demo_v9`](esp-idf/08_lvgl_demo_v9/README.md) | LVGL v9 display demo |
| [`examples/esp-idf/09_video_lcd_display`](esp-idf/09_video_lcd_display/README.md) | Video display pipeline |
| [`examples/esp-idf/10_mp4_player`](esp-idf/10_mp4_player/README.md) | MP4/AVI playback |
| [`examples/esp-idf/11_esp_brookesia_phone`](esp-idf/11_esp_brookesia_phone/README.md) | ESP-Brookesia phone UI |
| [`examples/esp-idf/12_usb_extend_screen`](esp-idf/12_usb_extend_screen/README.md) | USB extended screen |

## Arduino

Arduino notes are maintained in [arduino/README.md](arduino/README.md). The
Arduino tree includes bundled libraries used by the board examples, including
LVGL and Arduino_GFX.

| Sketch | Area |
| --- | --- |
| `01_HelloWorld` | Display bring-up |
| `02_AsciiTable` | Text rendering |
| `03_Drawing_board` | GT911 polling drawing |
| `04_LVGLV9_Arduino` | LVGL 9 display and touch |
| `05_GFX_ESPWiFiAnalyzer` | Wi-Fi scan visualization |
| `06_Camera_Preview` | Camera preview |
| `07_Camera_ISP_Tuning` | Camera ISP controls |
| `08_SD_Card` | microSD access |
| `09_Audio_Playback` | ES8311 playback |
| `10_Mic_Record` | ES7210 recording |

All 10 sketches have 3.4C and 4C build variants. The Arduino display adapter
uses the rev3.x-safe DSI PHY source selection; the display DPI clock remains
80 MHz for both panels.

## Adding A Project

New ESP-IDF projects should be self-contained and build independently with:

```bash
idf.py set-target esp32p4
idf.py build
```

Also update this index, add project-specific setup notes where appropriate, and
ensure generated ESP-IDF outputs are not committed.

The maintained `firmware/` source project is documented separately in
[`docs/FIRMWARE.md`](../docs/FIRMWARE.md). It is intentionally not part of the
default example build matrix.
