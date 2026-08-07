# 硬件参考与审计

[English](HARDWARE.md)

本仓库包含开发板原理图：
[`hardware/schematics/ESP32-P4-WIFI6-Touch-LCD-XC-Schematic.pdf`](../hardware/schematics/ESP32-P4-WIFI6-Touch-LCD-XC-Schematic.pdf)。
涉及引脚、连接器、电源、显示、触控、摄像头、音频、存储、USB 或 ESP32-C6
无线模块的修改，都应以它作为本地主要参考。

## 仓库内证据

两页原理图包含 ESP32-P4、ESP32-C6、Type-C、USB-UART、USB-OTG、microSD、
CSI、3.4/4 英寸显示屏连接器、Codec/ADC、麦克风、扬声器功放、复位/启动控制
和电源部分。以下维护中的源码提供软件侧约定：

| 范围 | 仓库证据 |
| --- | --- |
| ESP-IDF 板级支持 | `examples/esp-idf/*/components/waveshare__esp32_p4_wifi6_touch_lcd_xc/` 及其中的 `idf_component.yml` |
| 显示屏变体 | BSP 头文件和 `BSP_LCD_TYPE_800_800_3_4_INCH` / `BSP_LCD_TYPE_720_720_4_INCH` 配置 |
| Arduino 显示变体 | `examples/arduino/libraries/displays/displays_config.h` 和一方示例中的 `CURRENT_SCREEN` |
| Arduino I2C/触控 | `examples/arduino/libraries/displays/i2c.h` 和 `gt911.h` |
| 摄像头示例 | `examples/esp-idf/09_video_lcd_display/sdkconfig.defaults` 及本地 `esp_video` manifest |
| Hosted Wi-Fi | `examples/esp-idf/04_wifistation/main/idf_component.yml` |

示例使用 GT911 兼容触控 API。本文档不重复维护完整引脚表；如果修改开发板
相关内容，应同时更新和核对原理图、BSP 头文件及 Arduino 配置。

## 后续修改的审计规则

修改硬件常量或面向开发板的 README 前：

1. 在原理图中定位受影响的板级接口。
2. 将原理图网络名与 BSP 头文件、Arduino 配置、`sdkconfig.defaults` 和示例源码
   对照。
3. 影响显示路径时，同时检查两个显示分辨率和两个 Arduino `CURRENT_SCREEN` 变体。
4. 记录验证是静态的（源码/原理图）还是包含实体开发板测试。CI 通过只说明可以
   编译，不能单独证明引脚正确。

当前仓库工作范围是文档和 CI，不会修改板级引脚定义或交付固件文件。未来涉及
   引脚的改动仍需完成原理图交叉核对，并在条件允许时进行实体开发板测试。
