# ESP32-P4-WIFI6-Touch-LCD-XC ESP-Brookesia 固件

[English](README.md)

这是 ESP32-P4-WIFI6-Touch-LCD-3.4C 和 -4C 的默认固件源码。保留 Brookesia 手机桌面及配套应用：ESP-Hosted Wi-Fi、摄像头、音频、音乐、视频、绘图、频谱分析、设置和小智。

## 要求

- ESP-IDF v5.5.5
- 仅支持 ESP32-P4 Rev3.x

## 屏幕变体

| 变体 | 屏幕 | MIPI-DSI lane 数 | 单 lane 速率 | DPI 时钟 |
| --- | --- | ---: | ---: | ---: |
| `3_4c` | 3.4 英寸，800 x 800 | 2 | 1500 Mbps | 80 MHz |
| `4c` | 4 英寸，720 x 720 | 2 | 1500 Mbps | 80 MHz |

已发布的 XC BSP 使用 `phy_clk_src = 0`。ESP-IDF 会根据芯片最小 revision 选择兼容的 PHY 时钟源，因此本固件在基础 defaults 中直接设为 Rev3.x，不会选择 pre-v3 时钟路径。

## 触摸初始化

本固件中 GT911 的 INT 和 RST 均为 NC。BSP 依次探测 I2C 地址 `0x5D` 和 `0x14`，
使用实际探测到的地址创建 panel IO，并通过轮询读取触摸数据。除非另行变更
硬件约束，否则不要加入依赖 INT/RST 的地址选择时序。

## 编译

在本目录导出 ESP-IDF v5.5.5 环境后，按屏幕选择一条命令：

```bash
idf.py -B build-3_4c-v5.5.5-rev3_x -D SDKCONFIG="$PWD/build-3_4c-v5.5.5-rev3_x/sdkconfig" -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.rev3_x;sdkconfig.defaults.3_4c" build
idf.py -B build-4c-v5.5.5-rev3_x -D SDKCONFIG="$PWD/build-4c-v5.5.5-rev3_x/sdkconfig" -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.rev3_x;sdkconfig.defaults.4c" build
```

应用二进制命名为 `esp32-p4-lcd-xc-brookesia.bin`。

## 合并出厂固件

编译成功后运行对应命令。每条命令会生成一份 16 MiB 合并镜像，可从偏移 `0x0` 开始烧录：

```bash
(cd build-3_4c-v5.5.5-rev3_x && python -m esptool --chip esp32p4 merge_bin -o ../../ESP32-P4-WIFI6-Touch-LCD-3.4C-FactoryOnly-260821.bin @flash_args)
(cd build-4c-v5.5.5-rev3_x && python -m esptool --chip esp32p4 merge_bin -o ../../ESP32-P4-WIFI6-Touch-LCD-4C-FactoryOnly-260821.bin @flash_args)
```
