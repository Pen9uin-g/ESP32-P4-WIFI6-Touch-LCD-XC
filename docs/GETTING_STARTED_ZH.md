# 入门指南

[English](GETTING_STARTED.md)

本指南说明如何从一个干净的仓库开始，在 ESP32-P4-WIFI6-Touch-LCD-XC
开发板上编译并运行 ESP-IDF 示例。

## 环境要求

- ESP-IDF `v5.5.5` 或 `v6.0.2`；这两个版本也是仓库示例 CI 的覆盖范围。
- ESP-IDF 所需的 Python 和 Git 环境。
- 连接开发板 USB-UART 接口的数据线。
- 示例所需的可选外设，例如 SD 卡或摄像头模块。

开发板原理图位于
[`hardware/schematics/ESP32-P4-WIFI6-Touch-LCD-XC-Schematic.pdf`](../hardware/schematics/ESP32-P4-WIFI6-Touch-LCD-XC-Schematic.pdf)。
如果修改开发板引脚、显示、触控、摄像头、音频、存储或 USB 相关内容，请同时
参考[硬件审计](HARDWARE_ZH.md)和原理图。

## 编译 ESP-IDF 示例

先从基础 Hello World 示例开始：

```bash
cd examples/esp-idf/02_HelloWorld
idf.py set-target esp32p4
idf.py build
```

烧录并打开串口监视器：

```bash
idf.py -p PORT flash monitor
```

将 `PORT` 替换为开发板对应的串口。退出 ESP-IDF 串口监视器请按
`Ctrl-]`。

## 编译其他工程

仓库中的每个一方示例都包含自己的 `CMakeLists.txt` 和 `main/` 目录。默认
示例路径为：

- `examples/esp-idf/<example>`

`firmware/` 是单独维护的源码/交付面，不会进入默认示例 CI 矩阵；它只使用
rev3.x 的 `3_4c` 和 `4c` profile。修改前请阅读[固件源码边界](FIRMWARE_ZH.md)。

也可以使用 ESP-IDF 的工程路径参数：

```bash
idf.py -C examples/esp-idf/08_lvgl_demo_v9 set-target esp32p4 build
```

## 配置示例

使用以下功能的示例通常需要先运行 `idf.py menuconfig`：

- Wi-Fi SSID 和密码；
- SD 卡文件名或媒体播放选项；
- 显示、触控、LVGL、摄像头、USB 或音频选项；
- 开发板相关硬件选项。

共享默认值应写入 `sdkconfig.defaults` 或 `sdkconfig.ci*`。不要提交本地
`sdkconfig`、`build/`、`managed_components/` 或 `dependencies.lock` 输出。

## Arduino 说明

Arduino 信息维护在
[Arduino 说明](../examples/arduino/README_ZH.md)，其中包括推荐的
Arduino-ESP32 core、仓库内置 LVGL、Arduino_GFX 依赖和 I2C 驱动兼容性说明。
