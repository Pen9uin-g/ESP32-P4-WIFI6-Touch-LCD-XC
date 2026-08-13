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

CI 在两个 ESP-IDF 版本上编译显式的 3.4C 和 4C 变体。托管触控 API 保留已记录的 BSP
`3.0.1` 触控复位边界：静态证据与其中断选择一致，但与其 `GPIO_NUM_NC` 复位选择不一致。
编译覆盖不等同于触控 HIL；仍必须在真实 3.4C 和 4C 上验证。

请参阅[入门指南](../../../docs/GETTING_STARTED_ZH.md)、[组件归属](../../../docs/COMPONENTS_ZH.md)、
[硬件审计](../../../docs/HARDWARE_ZH.md)和[持续集成说明](../../../docs/CI_ZH.md)。
