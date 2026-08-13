# USB 扩展屏

[English](README.md)

此 ESP32-P4-WIFI6-Touch-LCD-XC 3.4C/4C 示例仅使用 USB OTG 设备模式，并支持
ESP-IDF `v5.5.5` 与 `v6.0.2`。默认配置启用 vendor 传输、HID 触控报告和 UAC 音频。

## 配置与运行

将 USB OTG 接口作为设备连接，并在构建前通过 `menuconfig` 选择匹配的显示类型。本仓库
不包含 PC 端发送器或客户端实现。

```bash
idf.py set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p PORT flash monitor
```

CI 在两个 ESP-IDF 版本上构建两个显示变体的 default 和仅供 CI 使用的 `vendor-only`
配置。vendor-only 禁用 HID 触控和 UAC 音频，并省略托管 UAC 组件；它不是常规设备配置。
构建覆盖不能替代 USB、显示、触控或音频 HIL。

请参阅[入门指南](../../../docs/GETTING_STARTED_ZH.md)、[组件归属](../../../docs/COMPONENTS_ZH.md)、
[硬件审计](../../../docs/HARDWARE_ZH.md)和[持续集成说明](../../../docs/CI_ZH.md)。
