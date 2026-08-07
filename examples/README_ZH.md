# 示例指南

[English](README.md)

本目录包含适用于 ESP32-P4-WIFI6-Touch-LCD-XC 的 ESP-IDF 一方工程、Arduino
说明和配套库。

## ESP-IDF 示例

| 路径 | 方向 |
| --- | --- |
| `examples/esp-idf/01_HowToCreateProject` | 最小 ESP-IDF 工程结构 |
| `examples/esp-idf/02_HelloWorld` | 基础 ESP-IDF 应用 |
| `examples/esp-idf/03_i2c_tools` | I2C 扫描和命令工具 |
| `examples/esp-idf/04_wifistation` | Wi-Fi station 连接 |
| `examples/esp-idf/05_sdmmc` | SD 卡与 SDMMC |
| `examples/esp-idf/06_I2SCodec` | I2S 音频编解码 |
| `examples/esp-idf/07_Displaycolorbar` | LCD 彩条显示 |
| `examples/esp-idf/08_lvgl_demo_v9` | LVGL v9 显示示例 |
| `examples/esp-idf/09_video_lcd_display` | 摄像头到显示屏视频链路 |
| `examples/esp-idf/10_mp4_player` | MP4/AVI 播放 |
| `examples/esp-idf/11_esp_brookesia_phone` | ESP-Brookesia 类手机界面 |
| `examples/esp-idf/12_usb_extend_screen` | USB 扩展屏 |

## Arduino

Arduino 说明位于[Arduino 说明](arduino/README_ZH.md)。Arduino 目录还包含开发板
示例使用的 LVGL 和 Arduino_GFX 等内置库；这些库自己的上游示例不会进入产品
CI 矩阵。

## 添加工程

新的 ESP-IDF 示例应能独立运行：

```bash
idf.py set-target esp32p4
idf.py build
```

同时更新本索引，必要时添加工程专用设置说明，并确保生成的 ESP-IDF 输出不会被
提交。

维护中的 `firmware/` 源码工程在[固件源码边界](../docs/FIRMWARE_ZH.md)中说明，
不会自动进入默认示例构建矩阵。
