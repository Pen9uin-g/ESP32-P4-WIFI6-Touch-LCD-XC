# ESP32-P4 Arduino 支持

[English](README.md)

## Arduino-ESP32 core

### 最新稳定版本

[![Release Version](https://img.shields.io/github/release/espressif/arduino-esp32.svg)](https://github.com/espressif/arduino-esp32/releases/latest/)
[![Release Date](https://img.shields.io/github/release-date/espressif/arduino-esp32.svg)](https://github.com/espressif/arduino-esp32/releases/latest/)
[![Downloads](https://img.shields.io/github/downloads/espressif/arduino-esp32/latest/total.svg)](https://github.com/espressif/arduino-esp32/releases/latest/)

本地实验建议使用 Arduino-ESP32 的最新稳定版本。仓库 CI 使用的固定版本记录
在下方；只有兼容性矩阵确认后才会更新该版本。

### CI 测试配置

GitHub Actions 使用 Arduino-ESP32 `3.3.11` 编译 5 个一方示例。CI 使用以下
开发板配置：

```text
esp32:esp32:esp32p4:ChipVariant=prev3,PSRAM=enabled,FlashSize=32M,FlashMode=qio,FlashFreq=80,PartitionScheme=app13M_data7M_32MB,USBMode=hwcdc,CDCOnBoot=cdc,UploadMode=default,UploadSpeed=921600
```

该配置选择 pre-v3 ESP32-P4 silicon，启用板载 32 MB PSRAM 和 32 MB Flash，
并为图形示例提供 13 MB 应用分区。

每个示例都会为两种产品显示屏编译：

| 产品 | CI 定义 |
| --- | --- |
| ESP32-P4-WIFI6-Touch-LCD-3.4C | `CURRENT_SCREEN=SCREEN_3INCH_4_DSI` |
| ESP32-P4-WIFI6-Touch-LCD-4C | `CURRENT_SCREEN=SCREEN_4INCH_DSI` |

### 文档

请参阅 [Arduino-ESP32 在线文档](https://docs.espressif.com/projects/arduino-esp32/en/latest/)。

## 其他依赖

### [lvgl v9.3.0](https://github.com/lvgl/lvgl)

仓库使用 `examples/arduino/libraries/lvgl` 中的内置 LVGL 副本。其上游文档、
许可证和示例保持在上游边界内，不在产品文档中批量翻译。

### [Arduino_GFX v1.6.0](https://github.com/moononournation/Arduino_GFX)

Arduino GFX 提供 ESP32-P4 MIPI-DSI 封装。仓库使用
`examples/arduino/libraries/GFX_Library_for_Arduino` 中的产品所需版本。

## 需要注意的 I2C 驱动

仓库内置库提供了对 `i2c_master.h` 的封装。原因是 ESP-IDF 更新后，
Arduino-ESP32 v3.2.0 使用新的 `i2c_master`（也称 driver_ng）驱动，可能与部分
旧版传感器、触控和扩展 IO 库不兼容。修改这些接口前，请同时检查仓库内置库、
Arduino-ESP32 core 和两种显示配置。
