| Supported Targets | ESP32-P4 |
| ----------------- | -------- |

# MP4/AVI Playlist Player

[中文](README_ZH.md)

This example scans the board microSD card for MP4 files, decodes supported
video frames, renders them through the Waveshare XC display BSP, and can play
the supported audio stream through the board codec and speaker path.

## Hardware and media

- ESP32-P4-WIFI6-Touch-LCD-XC with a 3.4C or 4C display;
- a FAT-formatted microSD card containing one or more test videos;
- a USB-C cable connected to the board's USB-UART interface;
- optional board speaker/audio path when audio playback is enabled.

The checked-in source and BSP configuration target the XC board's round display;
this example is not the ESP32-P4-Function-EV-Board HDMI example. Use the
repository [hardware audit](../../../docs/HARDWARE.md) and
[board schematic](../../../hardware/schematics/ESP32-P4-WIFI6-Touch-LCD-XC-Schematic.pdf)
for board-facing changes.

## Configure

Run `idf.py menuconfig` and review **MP4 Player Configuration**. Select the
display resolution and color format for the connected display, and configure
the video file and audio/video synchronization options as needed. The project
scans `/sdcard` for `.mp4` files; keep the media filename and format consistent
with the example's configuration.

The current extractor path supports MJPEG video. H.264 files are rejected by
the application, so convert test media when necessary. The upstream extractor
component README is kept at
[`components/esp_extractor/README.md`](components/esp_extractor/README.md) and
is not translated as product documentation.

## Test media

The upstream test file is an MJPEG video with AAC audio:
[test_video.mp4](https://dl.espressif.com/AE/esp-dev-kits/test_video.mp4).
For other media, use a compatible MJPEG MP4 and keep resolution/alignment within
the available display and PSRAM bandwidth.

## Build and flash

```bash
idf.py set-target esp32p4
idf.py build
idf.py -p PORT flash monitor
```

Replace `PORT` with the board's serial port. Type `Ctrl-]` to exit the monitor.
The first build may download registry components into the ignored
`managed_components/` directory.

The example is included in the repository's ESP-IDF `v5.5.5` and `v6.0.2`
matrix. CI validates compilation; playback and audio quality still require a
physical board, display, SD card, and compatible media file.
