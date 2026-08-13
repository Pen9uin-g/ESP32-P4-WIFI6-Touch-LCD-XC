# Hello World

[English](README.md)

此 ESP-IDF 示例输出芯片信息、倒计时后重启。它支持
ESP32-P4-WIFI6-Touch-LCD-XC 3.4C 和 4C，以及 ESP-IDF `v5.5.5` 与 `v6.0.2`。

## 构建与运行

安装受支持的 ESP-IDF 环境并连接开发板；不需要板级外设设置。

```bash
idf.py set-target esp32p4
idf.py build
idf.py -p PORT flash monitor
```

CI 在两个 ESP-IDF 版本上编译共享/default 配置；它不验证显示、触控、存储、音频或
无线硬件。

请参阅[入门指南](../../../docs/GETTING_STARTED_ZH.md)、[示例指南](../../README_ZH.md)
和[持续集成说明](../../../docs/CI_ZH.md)。
