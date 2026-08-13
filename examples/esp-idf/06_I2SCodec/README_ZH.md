# I2S ES8311 编解码器

[English](README.md)

此 ES8311 编解码器示例支持 ESP32-P4-WIFI6-Touch-LCD-XC 3.4C 和 4C，以及
ESP-IDF `v5.5.5` 与 `v6.0.2`。在 P4 上，它使用 I2C SCL GPIO8/SDA GPIO7、I2S
MCLK GPIO13、BCLK GPIO12、WS GPIO10、DOUT GPIO9、DIN GPIO11，以及 PA 使能 GPIO53。

## 配置与运行

通过 `menuconfig` 选择音乐（默认）或回声模式；回声模式仅在禁用 BSP 支持时可用。音乐
模式嵌入随工程提供的 `main/canon.pcm`。

```bash
idf.py set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p PORT flash monitor
```

CI 只在两个 ESP-IDF 版本编译共享/default 配置，不能替代播放、麦克风或功放的 HIL 测试。

请参阅[入门指南](../../../docs/GETTING_STARTED_ZH.md)、[硬件审计](../../../docs/HARDWARE_ZH.md)
和[持续集成说明](../../../docs/CI_ZH.md)。
