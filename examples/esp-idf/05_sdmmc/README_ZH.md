# SDMMC 存储卡

[English](README.md)

此 SDMMC 示例支持 ESP32-P4-WIFI6-Touch-LCD-XC 3.4C 和 4C，以及 ESP-IDF
`v5.5.5` 与 `v6.0.2`。其 P4 默认引脚为 D0..D3 GPIO39..GPIO42、CLK GPIO43 和
CMD GPIO44；默认使用四线模式。

## 配置与运行

插入兼容的 microSD 卡，并在 `menuconfig` 选择一线或四线模式和可选诊断。挂载失败时
格式化和显式格式化存储卡均为可选项，默认关闭。

```bash
idf.py set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p PORT flash monitor
```

CI 只在两个 ESP-IDF 版本编译共享/default 配置；它不验证存储卡，也不授权格式化介质。

请参阅[入门指南](../../../docs/GETTING_STARTED_ZH.md)、[硬件审计](../../../docs/HARDWARE_ZH.md)
和[持续集成说明](../../../docs/CI_ZH.md)。
