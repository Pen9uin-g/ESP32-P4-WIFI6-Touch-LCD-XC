# ESP32-P4 Arduino Support

[中文](README_ZH.md)

## Arduino-ESP32 core

### Latest Stable Release:

[![Release Version](https://img.shields.io/github/release/espressif/arduino-esp32.svg)](https://github.com/espressif/arduino-esp32/releases/latest/)
[![Release Date](https://img.shields.io/github/release-date/espressif/arduino-esp32.svg)](https://github.com/espressif/arduino-esp32/releases/latest/)
[![Downloads](https://img.shields.io/github/downloads/espressif/arduino-esp32/latest/total.svg)](https://github.com/espressif/arduino-esp32/releases/latest/)

Use the latest stable Arduino-ESP32 release for local experiments. The
repository CI pin is recorded above and is updated deliberately when the
compatibility matrix changes.

### CI-Tested Configuration

GitHub Actions compiles the five first-party sketches with Arduino-ESP32
`3.3.11`. The CI board configuration is:

```text
esp32:esp32:esp32p4:ChipVariant=prev3,PSRAM=enabled,FlashSize=32M,FlashMode=qio,FlashFreq=80,PartitionScheme=app13M_data7M_32MB,USBMode=hwcdc,CDCOnBoot=cdc,UploadMode=default,UploadSpeed=921600
```

This selects pre-v3 ESP32-P4 silicon at the board-supported frequency, enables
the onboard 32 MB PSRAM and 32 MB flash, and provides a 13 MB application
partition for the larger graphics examples.

Every sketch is compiled for both product displays:

| Product | CI definition |
| --- | --- |
| ESP32-P4-WIFI6-Touch-LCD-3.4C | `CURRENT_SCREEN=SCREEN_3INCH_4_DSI` |
| ESP32-P4-WIFI6-Touch-LCD-4C | `CURRENT_SCREEN=SCREEN_4INCH_DSI` |

### Documentation

You can use the [Arduino-ESP32 Online Documentation](https://docs.espressif.com/projects/arduino-esp32/en/latest/) to get all information about this project.

## Other Dependencies

### [lvgl v9.3.0](https://github.com/lvgl/lvgl)

<p align="center">
  <img src="https://lvgl.io/github-assets/logo-colored.png" width=300px>
</p>

  <h1 align="center">Light and Versatile Graphics Library</h1>
  <br>
<div align="center">
  <img src="https://lvgl.io/github-assets/smartwatch-demo.gif">
  &nbsp;
  <img border="1px" src="https://lvgl.io/github-assets/widgets-demo.gif">
</div>

### [Arduino_GFX v1.6.0](https://github.com/moononournation/Arduino_GFX)

Arduino GFX provides the encapsulated ESP32-P4 MIPI DSI function

## Special points to pay attention

### I2C Drivers

In libraries, we provide a way to wrap i2c_master.h ourselves and then provide some basic functions. The main reason is that after the esp-idf update, arduino-esp32 v3.2.0 uses a new version of i2c_master driver also known as i2c driver_ng, which is not compatible with some older libraries, including but not limited to some sensor libraries, touch libraries, and extended IO libraries.
