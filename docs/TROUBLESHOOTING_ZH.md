# 故障排查

[English](TROUBLESHOOTING.md)

当示例无法编译、烧录或运行时，可以按下面的清单排查。

## 编译问题

- 确认已经激活支持 ESP32-P4 的 ESP-IDF。
- 运行 `idf.py --version`，并与示例说明对照。仓库 CI 当前测试 ESP-IDF
  `v5.5.5` 和 `v6.0.2`。
- 配置有较大变化时，删除生成的 `build/`、`managed_components/`、
  `dependencies.lock` 和本地 `sdkconfig` 后重新配置。
- 在工程第一次编译前运行 `idf.py set-target esp32p4`。
- 检查 `main/idf_component.yml` 中是否有需要首次联网下载的托管组件。

## 烧录与串口监视器问题

- 对 ESP-IDF，请确认 Type-C UART/USB-UART 串口，并使用
  `idf.py -p PORT flash monitor`。
- 对已测试 Arduino FQBN，示例 `Serial` 通过 Type-C USB 的 Hardware CDC
  输出，不经过 CH343P Type-C UART 接口。请参阅
  [Arduino 分段烧录](ARDUINO_FLASHING_ZH.md)。
- Arduino 示例必须能在监视器关闭或断开时启动。非阻塞日志封装丢弃启动日志属于
  预期行为。
- 只有在串口工具无法自动进入下载模式时，才按住或按下开发板的启动/复位控制。
- 更换支持数据传输的 USB-C 线缆，并尝试主机上的直连接口。
- 确认开发板已供电并打开电源开关。

## 显示与触控问题

- 重新编译与当前显示接口匹配的示例。
- 确认 FPC 排线完全插入且方向正确。
- 检查 `menuconfig` 中的显示、触控、LVGL 和帧缓冲选项。
- 对视频或 LVGL 示例，如果出现伪影，可先降低分辨率、色深或帧率，排查内存
  带宽压力。

## 存储与媒体问题

- 确认 SD 卡已经按示例要求格式化并成功挂载。
- `menuconfig` 中的文件名必须与 SD 卡上的文件名完全一致，包括大小写和扩展名。
- 使用示例文档支持的媒体格式；视频示例可能只支持特定容器、编码器和对齐方式。

## Wi-Fi 问题

- 确认已经在 `menuconfig` 或示例配置中设置凭据。
- 检查项目所需的 remote/hosted Wi-Fi 组件是否成功下载。
- 提交问题时保留从启动到连接失败的完整串口日志。
