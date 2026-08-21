# LVGL 9 示例

[English](README.md)

此 LVGL 9 示例启动托管显示屏、打开背光并运行 LVGL widgets 示例。它支持
ESP32-P4-WIFI6-Touch-LCD-XC 3.4C 和 4C，以及 ESP-IDF `v5.5.5` 与 `v6.0.2`。

## 配置与运行

安装受支持的 ESP-IDF 环境，并在构建前通过 `menuconfig` 选择匹配的 BSP 显示类型。

```bash
idf.py set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p PORT flash monitor
```

CI 在两个 ESP-IDF 版本上编译显式的 3.4C 和 4C 变体。已发布的 BSP `3.0.1` 不配置
触控 RST 与 INT，依次探测 `0x5D` 和 `0x14`，并在不安装 ISR 的情况下轮询。编译覆盖
不等同于触控 HIL；仍须在真实 3.4C 和 4C 上验证有响应地址、坐标、抬起事件和轮询行为。

请参阅[入门指南](../../../docs/GETTING_STARTED_ZH.md)、[组件归属](../../../docs/COMPONENTS_ZH.md)、
[硬件审计](../../../docs/HARDWARE_ZH.md)和[持续集成说明](../../../docs/CI_ZH.md)。
