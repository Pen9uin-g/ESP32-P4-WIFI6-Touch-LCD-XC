| 支持的 Target | ESP32-P4 |
| --- | --- |

# MP4/AVI 播放示例

[English](README.md)

本示例扫描开发板 microSD 卡中的 MP4 文件，解码支持的视频帧，通过 Waveshare
XC 显示 BSP 输出到圆形 LCD，并可通过开发板 Codec/扬声器路径播放支持的音频流。

## 硬件与媒体

- ESP32-P4-WIFI6-Touch-LCD-XC，配 3.4C 或 4C 显示屏；
- FAT 格式的 microSD 卡，卡中放置一个或多个测试视频；
- 连接开发板 USB-UART 接口的数据线；
- 启用音频播放时可使用开发板扬声器/音频通路。

当前源码和 BSP 配置面向 XC 圆形显示屏，并不是 ESP32-P4-Function-EV-Board 的
HDMI 示例。涉及开发板内容时，请参考仓库的[硬件审计](../../../docs/HARDWARE_ZH.md)
和[开发板原理图](../../../hardware/schematics/ESP32-P4-WIFI6-Touch-LCD-XC-Schematic.pdf)。

## 配置

运行 `idf.py menuconfig` 并检查 **MP4 Player Configuration**。按接入的显示屏
选择分辨率和色彩格式，并按需配置视频文件与音视频同步。程序会扫描 `/sdcard`
下的 `.mp4` 文件，媒体文件名和格式应与示例配置保持一致。

当前 extractor 路径支持 MJPEG 视频；应用会拒绝 H.264 文件，必要时请先转换测试
媒体。上游 extractor 组件说明保留在
[`components/esp_extractor/README.md`](components/esp_extractor/README.md)，不作为
产品文档翻译。

## 测试媒体

上游测试文件包含 MJPEG 视频和 AAC 音频：
[test_video.mp4](https://dl.espressif.com/AE/esp-dev-kits/test_video.mp4)。其他媒体
应使用兼容的 MJPEG MP4，并将分辨率/对齐控制在显示屏和 PSRAM 带宽能力内。

## 编译与烧录

```bash
idf.py set-target esp32p4
idf.py build
idf.py -p PORT flash monitor
```

将 `PORT` 替换为开发板串口。退出串口监视器请按 `Ctrl-]`。首次编译可能会把
注册表组件下载到被忽略的 `managed_components/` 目录。

该示例进入仓库 ESP-IDF `v5.5.5` 和 `v6.0.2` 矩阵。CI 验证可以编译；播放效果
和音频质量仍需实体开发板、显示屏、SD 卡及兼容媒体文件验证。
