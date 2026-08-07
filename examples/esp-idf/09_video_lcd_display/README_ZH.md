| 支持的 Target | ESP32-P4 |
| --- | --- |

# 摄像头到 LCD 视频示例

[English](README.md)

本示例使用 Waveshare 开发板支持组件和 Espressif 的 `esp_video` 组件，从
ESP32-P4-WIFI6-Touch-LCD-XC 的 MIPI-CSI 摄像头采集图像，并显示到圆形
MIPI-DSI LCD。

## 硬件

- ESP32-P4-WIFI6-Touch-LCD-XC，配 3.4C 或 4C 显示屏；
- 兼容的 MIPI-CSI 摄像头模块；仓库默认配置选择 OV5647 RAW8 路径；
- 连接开发板 USB-UART 接口的数据线。

修改摄像头、显示、复位或电源配置时，不要复制其他 ESP32-P4 开发板的引脚表，
请参考仓库的[硬件审计](../../../docs/HARDWARE_ZH.md)和[开发板原理图](../../../hardware/schematics/ESP32-P4-WIFI6-Touch-LCD-XC-Schematic.pdf)。

## 配置

默认 `sdkconfig.defaults` 选择 OV5647 MIPI 摄像头格式。若使用其他摄像头或
显示变体，请运行 `idf.py menuconfig` 检查摄像头传感器和显示选项。

## 编译与烧录

```bash
idf.py set-target esp32p4
idf.py build
idf.py -p PORT flash monitor
```

将 `PORT` 替换为开发板串口。退出串口监视器请按 `Ctrl-]`。首次编译可能会把
注册表组件下载到被忽略的 `managed_components/` 目录。

## 依赖与验证

工程 manifest 声明 `esp_video` 和 Waveshare XC BSP。该示例进入仓库 ESP-IDF
`v5.5.5` 与 `v6.0.2` 矩阵。CI 证明源码和配置可以编译，不能替代实体摄像头
与显示屏测试。
