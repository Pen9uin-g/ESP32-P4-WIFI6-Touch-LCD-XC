# ESP32-P4 Arduino 支持

[English](README.md)

## Arduino-ESP32 core

### CI 已验证稳定版本

本仓库固定使用
[Arduino-ESP32 3.3.11](https://github.com/espressif/arduino-esp32/releases/tag/3.3.11)。
复现 CI 与烧录包时请使用该精确版本；更高版本需单独验证后才能修改兼容性矩阵。

### CI 测试配置

GitHub Actions 使用 Arduino-ESP32 `3.3.11` 编译 10 个一方示例。CI 使用以下
开发板配置：

```text
esp32:esp32:esp32p4:ChipVariant=postv3,PSRAM=enabled,FlashSize=32M,FlashMode=qio,FlashFreq=80,PartitionScheme=app13M_data7M_32MB,USBMode=hwcdc,CDCOnBoot=cdc,UploadMode=default,UploadSpeed=921600
```

该配置选择 post-v3 ESP32-P4 silicon，启用板载 32 MB PSRAM 和 32 MB Flash，
并为图形示例提供 13 MB 应用分区。对于已确认的 pre-v3 芯片，应显式把
`ChipVariant=postv3` 替换为 `ChipVariant=prev3`；该构建不属于默认 CI 矩阵，
其二进制文件也不能与 `rev3_x` 构建互换。

### Arduino IDE 配置

安装精确版本为 `3.3.11` 的 **ESP32 by Espressif Systems** 开发板包，然后将本仓库
`examples/arduino/libraries/` 目录下的四个直接内容复制到 Arduino sketchbook 的
`libraries/` 目录：

| 仓库内容 | sketchbook 目标位置 |
| --- | --- |
| `displays/` | `libraries/displays/` |
| `GFX_Library_for_Arduino/` | `libraries/GFX_Library_for_Arduino/` |
| `lvgl/` | `libraries/lvgl/` |
| `lv_conf.h` | `libraries/lv_conf.h` |

请复制仓库 `libraries/` 目录中的**内容**，不要复制其父目录本身；尤其不能形成
`libraries/libraries/`。上列四项即为这些示例完整的随仓库依赖集，请勿以不相关的
上游库替换。

`ESP_Video`、`SD_MMC`、`FS`、`Wire` 和 `I2S` 由安装的 Arduino-ESP32 3.3.11 core
提供，无需从本仓库复制。

`displays_config.h` 默认选择 3.4C 面板：`CURRENT_SCREEN` 为
`SCREEN_3INCH_4_DSI`。在 Arduino IDE 中构建 4C 时，请将
`libraries/displays/displays_config.h` 中的默认值改为 `SCREEN_4INCH_DSI`。CI
通过等效的 `CURRENT_SCREEN` 构建宏编译两种面板。

Arduino-ESP32 3.3.11 的 **工具 (Tools)** 菜单请使用下列对应选项：

| 工具菜单 | 选择项 |
| --- | --- |
| Board | `ESP32P4 Dev Module` |
| Chip Variant | `v3.00 or newer` |
| PSRAM | `Enabled` |
| Flash Size | `32MB (256Mb)` |
| Flash Mode | `QIO` |
| Flash Frequency | `80MHz` |
| Partition Scheme | `32M Flash (13MB APP/6.75MB SPIFFS)` |
| USB Mode | `Hardware CDC and JTAG` |
| CDC On Boot | `Enabled` |
| Upload Speed | `921600` |
| Upload Mode | `UART0 / Hardware CDC`（默认；UART0 上传使用 USB-UART bridge） |

以上为前述 CI FQBN 在 Arduino IDE 中对应的菜单名称。

### USB 接口与非阻塞日志

CI FQBN 选择 `USBMode=hwcdc,CDCOnBoot=cdc`，因此示例的 `Serial` 日志通过
开发板的 **Type-C USB** 接口和 ESP32-P4 Hardware USB Serial/JTAG CDC 输出。
另一个 **Type-C UART** 接口通过 CH343P USB 转串口芯片连接 UART0；受支持的
上传流程可使用它，但在当前 CI FQBN 下，该接口不会收到示例的 `Serial` 日志。

一方示例不会等待串口监视器。Hardware CDC 未连接或主机未及时读取时，诊断
日志会被丢弃，显示、触控及应用启动不会因此延迟。

每个示例都会为两种产品显示屏编译：

| 产品 | CI 定义 |
| --- | --- |
| ESP32-P4-WIFI6-Touch-LCD-3.4C | `CURRENT_SCREEN=SCREEN_3INCH_4_DSI` |
| ESP32-P4-WIFI6-Touch-LCD-4C | `CURRENT_SCREEN=SCREEN_4INCH_DSI` |

### 一方示例

Arduino 示例采用编号目录，使文档、CI 自动发现和 Arduino IDE 的 sketch 名称保持一致：

| 示例 | 功能 |
| --- | --- |
| `01_HelloWorld` | DSI 显示屏基础初始化和文本输出 |
| `02_AsciiTable` | 显示字符表 |
| `03_Drawing_board` | 基于 GT911 兼容轮询接口的触控画板 |
| `04_LVGLV9_Arduino` | LVGL v9 显示和触控示例 |
| `05_GFX_ESPWiFiAnalyzer` | 附近 Wi-Fi 扫描可视化 |
| `06_Camera_Preview` | 在所选 XC 显示屏上预览 OV5647 MIPI-CSI 相机 |
| `07_Camera_ISP_Tuning` | 带串口 ISP/3A 控制的 OV5647 预览 |
| `08_SD_Card` | SDIO microSD 读写检查 |
| `09_Audio_Playback` | ES8311 扬声器播放 |
| `10_Mic_Record` | ES7210 麦克风 PCM 采集 |

相机、存储卡和音频示例使用 XC 开发板的外设引脚。即使未连接相机、存储卡或
音频硬件，示例仍可编译；运行相应功能时则需要连接对应硬件。

### MIPI-DSI 时钟源

随仓库提供的 Arduino_GFX DSI panel 将 `phy_clk_src` 保持为 `0`，与已发布 BSP
一致，并由 ESP-IDF 的芯片修订 profile 自动选择正确的 PHY 时钟源。默认 CI 配置
使用 `ChipVariant=postv3`；不要将 pre-v3 构建烧录到 rev3.x 开发板，反之亦然。

### 触控行为

官方控制器为 GT9271，Arduino 库使用 GT911 兼容 API。驱动有意不配置 RST 和 INT，
不安装中断处理器，依次探测 `0x5D` 与 `0x14`，并轮询触控数据。尽管原理图经 R62 将
RST 路由至 GPIO23，INT 只到达 TP2；不由软件复位/设置地址 strap，可使轮询路径不依赖
这些信号。编译不能确认有响应地址、坐标或抬起事件；请在真实硬件上验证。

### 文档

分段烧录、接口选择和 HIL 检查请参阅
[Arduino 分段烧录与 Hardware CDC 验证](../../docs/ARDUINO_FLASHING_ZH.md)。
[Arduino-ESP32 文档](https://docs.espressif.com/projects/arduino-esp32/en/latest/)
当前说明的是仓库固定使用的 `3.3.11` core。

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
