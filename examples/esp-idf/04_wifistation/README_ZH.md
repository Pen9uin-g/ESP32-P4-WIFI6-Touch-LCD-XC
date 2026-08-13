# Wi-Fi Station

[English](README.md)

此示例通过开发板的 ESP32-C6 Hosted 运行时依赖以 Wi-Fi station 模式连接。它支持
ESP32-P4-WIFI6-Touch-LCD-XC 3.4C 和 4C，以及 ESP-IDF `v5.5.5` 与 `v6.0.2`。

## 配置与运行

构建前在 `idf.py menuconfig` 设置 SSID 和密码。manifest 对 IDF 低于 6.0 选择
`esp_wifi_remote` `0.14.*` 和 `esp_hosted` `1.4.*`；对 IDF 6.0 或更高版本选择
remote `>=1.6,<2.0` 和 hosted `>=2.12,<3.0`。

```bash
idf.py set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p PORT flash monitor
```

CI 只在两个 ESP-IDF 版本编译共享/default 配置。C6 镜像是运行时依赖；仓库未记录其
确切镜像、版本、哈希、源码或构建元数据。扩大任一范围前，必须获得这些确切元数据、
完成双 IDF 编译并进行真实 Wi-Fi HIL 验证。

请参阅[入门指南](../../../docs/GETTING_STARTED_ZH.md)、[组件归属](../../../docs/COMPONENTS_ZH.md)
和[持续集成说明](../../../docs/CI_ZH.md)。
