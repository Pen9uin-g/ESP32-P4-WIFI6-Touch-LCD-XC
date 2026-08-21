# I2C 工具

[English](README.md)

此控制台示例配置并探测开发板共享 I2C 总线：SDA 为 GPIO7，SCL 为 GPIO8。它支持
ESP32-P4-WIFI6-Touch-LCD-XC 3.4C 和 4C，以及 ESP-IDF `v5.5.5` 与 `v6.0.2`。

## 配置与运行

仓库未提供外部客户端。只在共享总线上连接兼容的 I2C 硬件；如有需要，可通过
`menuconfig` 调整已记录的 I2C GPIO 默认值或控制台历史选项。

```bash
idf.py set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p PORT flash monitor
```

在 `i2c-tools>` 提示符输入 `help` 可查看命令；本工程注册 `i2cconfig`、`i2cdetect`、
`i2cget`、`i2cset` 和实验性的 `i2cdump`。CI 只在两个 ESP-IDF 版本编译共享/default
配置，不验证外接 I2C 设备。

请参阅[入门指南](../../../docs/GETTING_STARTED_ZH.md)、[硬件审计](../../../docs/HARDWARE_ZH.md)
和[持续集成说明](../../../docs/CI_ZH.md)。
