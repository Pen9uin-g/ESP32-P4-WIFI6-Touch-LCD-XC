# 最小 ESP-IDF 工程

[English](README.md)

这是一个不使用外设的起始工程，包含空的 `app_main`。它支持
ESP32-P4-WIFI6-Touch-LCD-XC 3.4C 和 4C，以及 ESP-IDF `v5.5.5` 与 `v6.0.2`。

## 构建与运行

安装受支持的 ESP-IDF 环境并连接开发板；本工程不需要外设配置。

```bash
idf.py set-target esp32p4
idf.py build
idf.py -p PORT flash monitor
```

CI 在两个 ESP-IDF 版本上编译共享/default 配置。工程没有显示、触控、存储、音频或
无线功能可验证。

请参阅[入门指南](../../../docs/GETTING_STARTED_ZH.md)、[示例指南](../../README_ZH.md)
和[持续集成说明](../../../docs/CI_ZH.md)。
