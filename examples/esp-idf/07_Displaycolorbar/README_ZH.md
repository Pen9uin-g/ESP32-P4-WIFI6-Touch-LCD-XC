# 显示彩条

[English](README.md)

此示例初始化托管的板级显示屏并显示 MIPI-DSI 垂直彩条。它支持
ESP32-P4-WIFI6-Touch-LCD-XC 3.4C 和 4C，以及 ESP-IDF `v5.5.5` 与 `v6.0.2`；
默认配置为 3.4C（800 × 800）。

## 配置与运行

安装受支持的 ESP-IDF 环境并连接开发板。需要时在 `menuconfig` 选择 4C（720 × 720）
BSP 显示类型。

```bash
idf.py set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p PORT flash monitor
```

CI 在两个 ESP-IDF 版本上构建显式的 3.4C 和 4C overlay。构建成功不能证明面板在实体
硬件上正常工作。

请参阅[入门指南](../../../docs/GETTING_STARTED_ZH.md)、[硬件审计](../../../docs/HARDWARE_ZH.md)
和[持续集成说明](../../../docs/CI_ZH.md)。
